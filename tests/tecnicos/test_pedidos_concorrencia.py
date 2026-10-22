"""E08: concorrência da abertura, das tentativas, da quitação e da moderação.

E08-02: A-20 e A-21. E08-03: A-19 e A-20 (tentativas). E08-04: A-16 e A-17.
E08-05: A-20 e A-21. E08-06: A-11 e A-12.
"""

from datetime import timedelta
from decimal import Decimal
from threading import Event
from typing import Any

import pytest
from django.db import DatabaseError, transaction
from django.test import Client

from apps.catalogo.servicos import editar_produto
from apps.contas.moderacao import reativar, remover, suspender
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.tempo import agora
from apps.pagamentos.chamadas import OPERACOES, Operacao, agendar_chamada, processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor, PagamentoNoProvedor
from apps.pedidos.abertura import abrir_pagamento
from apps.pedidos.models import (
    AberturaDoPagamento,
    DestinoDoPagamento,
    ItemDoPedido,
    Pedido,
    SituacaoDoPedido,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import PagamentoRecusado, agendar_cancelamento, pedir_pagamento
from apps.pedidos.tarefas import (
    bloquear_tentativas_vencidas_agora,
    reconsultar_pagamentos_da_margem_agora,
)
from apps.rodadas.fechamento import TransicaoRecusada
from apps.simulador_pagamentos.models import CobrancaSimulada
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.pedidos import (
    T0,
    Arranjo,
    administrador,
    montar_arranjo,
    pedido_aberto,
    recuperacao_de_dois_pagamentos,
    sincronizar,
    tentativa_criada,
)
from tests.apoio.trava import esperando, segurando
from tests.conftest import RelogioControlado

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]

D = Decimal


@pytest.fixture
def arranjo(relogio: RelogioControlado) -> Arranjo:
    relogio.congelar(T0)
    return montar_arranjo()


def _abrir(arranjo: Arranjo) -> object:
    return abrir_pagamento(administrador(), arranjo.rodada, D("22.00"))


def test_duas_aberturas_ao_mesmo_tempo_abrem_uma_so(arranjo: Arranjo) -> None:  # A-20
    resultados = executar_em_paralelo(
        segurando(lambda: _abrir(arranjo)),
        esperando(lambda: _abrir(arranjo)),
    )
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, TransicaoRecusada), resultados[1].excecao
    assert resultados[1].excecao.codigo == "fora_de_fechamento_encerrado_para_pagamento"
    assert AberturaDoPagamento.objects.count() == 1
    assert Pedido.objects.count() == 2


def _precos_de_p1(arranjo: Arranjo) -> set[Decimal]:
    return set(
        ItemDoPedido.objects.filter(produto=arranjo.p1).values_list("preco_unitario", flat=True)
    )


def _preco_alterado(arranjo: Arranjo) -> list[int]:
    return [
        n.conta_id
        for n in Notificacao.objects.filter(evento="preco_alterado")
        if n.conta_id in (arranjo.a.pk, arranjo.b.pk)
    ]


def test_preco_gravado_antes_da_abertura_entra_nos_itens(arranjo: Arranjo) -> None:
    # A-21 (a): o preço vem antes
    resultados = executar_em_paralelo(
        segurando(lambda: editar_produto(administrador(), arranjo.p1, preco="11.00")),
        esperando(lambda: _abrir(arranjo)),
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert _precos_de_p1(arranjo) == {D("11.00")}
    arranjo.p1.refresh_from_db()
    assert arranjo.p1.preco == D("11.00")
    # O aviso de preço (E05-06) é devido: as parcelas ainda estavam `ativa` quando o preço mudou.
    assert sorted(_preco_alterado(arranjo)) == sorted([arranjo.a.pk, arranjo.b.pk])


def test_preco_gravado_depois_da_abertura_nao_muda_os_itens(arranjo: Arranjo) -> None:
    # A-21 (b): o preço vem depois
    resultados = executar_em_paralelo(
        segurando(lambda: _abrir(arranjo)),
        esperando(lambda: editar_produto(administrador(), arranjo.p1, preco="11.00")),
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert _precos_de_p1(arranjo) == {D("10.00")}
    arranjo.p1.refresh_from_db()
    assert arranjo.p1.preco == D("11.00")
    assert _preco_alterado(arranjo) == []


# --- E08-03: tentativas de pagamento (A-19 e A-20) -----------------------------------------


@pytest.fixture
def cenario(relogio: RelogioControlado, simulador_pagamentos: Any) -> tuple[Arranjo, Pedido]:
    return pedido_aberto(relogio)


def test_dois_cliques_em_pagar_geram_uma_tentativa(cenario: tuple[Arranjo, Pedido]) -> None:
    # A-19
    arranjo, x = cenario
    resultados = executar_em_paralelo(
        segurando(lambda: pedir_pagamento(arranjo.a, x)),
        esperando(lambda: pedir_pagamento(arranjo.a, x)),
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert TentativaDePagamento.objects.filter(pedido=x).count() == 1
    assert ChamadaAoProvedor.objects.filter(operacao="criar_cobranca").count() == 1
    assert resultados[0].valor.pk == resultados[1].valor.pk


def test_cancelamento_em_execucao_nao_trava_a_moderacao(
    cenario: tuple[Arranjo, Pedido], monkeypatch: pytest.MonkeyPatch
) -> None:  # A-20
    arranjo, x = cenario
    pedir_pagamento(arranjo.a, x)
    assert processar_chamadas() == 1
    tentativa = TentativaDePagamento.objects.get(pedido=x)
    with transaction.atomic():
        agendar_cancelamento(tentativa, "prazo")
    original = OPERACOES["cancelar_cobranca"]
    entrou, liberar, primeira_terminou = Event(), Event(), Event()

    def parada(provedor: Any, chamada: ChamadaAoProvedor) -> Any:
        entrou.set()
        assert liberar.wait(20), "a segunda thread não terminou: esperou a chamada em andamento"
        return original.executar(provedor, chamada)

    monkeypatch.setitem(
        OPERACOES, "cancelar_cobranca", Operacao(parada, original.concluir, original.falhou)
    )

    def executa_a_chamada(barreira: Any) -> int:
        barreira.wait(timeout=10)
        try:
            return processar_chamadas()
        finally:
            primeira_terminou.set()

    def modera(barreira: Any) -> bool:
        barreira.wait(timeout=10)
        assert entrou.wait(10), "a chamada não entrou em execução"
        with transaction.atomic():
            SituacaoDoPedido.objects.select_for_update().get(pedido_id=x.pk)
            agendar_cancelamento(tentativa, "suspensao")
        terminou_antes = not primeira_terminou.is_set()
        liberar.set()
        return terminou_antes

    resultados = executar_em_paralelo(executa_a_chamada, modera)
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert resultados[1].valor is True
    alvos = sorted(
        ChamadaAoProvedor.objects.filter(operacao="cancelar_cobranca").values_list(
            "alvo", flat=True
        )
    )
    assert alvos == [f"t{tentativa.pk}:prazo", f"t{tentativa.pk}:suspensao"]


# --- E08-04: quitação (A-16 e A-17) --------------------------------------------------------


def _com_duas_cobrancas_aprovadas(
    relogio: RelogioControlado, sim: Any
) -> tuple[Arranjo, Pedido, str, str]:
    arranjo, x = pedido_aberto(relogio)
    primeira = tentativa_criada(x).id_externo
    assert primeira is not None
    sim.expirar(primeira)
    sincronizar(primeira)
    relogio.congelar(T0 + timedelta(hours=1, minutes=10))
    segunda = tentativa_criada(x).id_externo
    assert segunda is not None
    relogio.congelar(T0 + timedelta(hours=2))
    sim.aprovar(primeira, em=T0 + timedelta(minutes=110))
    sim.aprovar(segunda, em=T0 + timedelta(minutes=115))
    return arranjo, x, primeira, segunda


def test_dois_pagamentos_ao_mesmo_tempo_um_quita_e_o_outro_duplica(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-16, T-7
    arranjo, x, primeira, segunda = _com_duas_cobrancas_aprovadas(relogio, simulador_pagamentos)
    resultados = executar_em_paralelo(
        segurando(lambda: sincronizar(primeira)),
        esperando(lambda: sincronizar(segunda)),
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    destinos = {d.pagamento.id_externo: d for d in DestinoDoPagamento.objects.all()}
    assert sorted(d.destino for d in destinos.values()) == ["devolucao", "quita"]
    assert [d.motivo for d in destinos.values() if d.destino == "devolucao"] == ["duplicidade"]
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "pago"
    avisos = Notificacao.objects.filter(conta=arranjo.a, evento="pagamento_confirmado")
    assert avisos.count() == 1


def test_aviso_e_tarefa_ao_mesmo_tempo_decidem_uma_vez(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-17, T-6
    arranjo, x = pedido_aberto(relogio)
    p = tentativa_criada(x).id_externo
    assert p is not None
    relogio.congelar(T0 + timedelta(hours=2))
    simulador_pagamentos.aprovar(p, em=T0 + timedelta(minutes=110))
    resultados = executar_em_paralelo(
        segurando(lambda: sincronizar(p, "aviso")),
        esperando(lambda: sincronizar(p, "tarefa")),
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert DestinoDoPagamento.objects.count() == 1
    assert EntradaAuditoria.objects.filter(acao="pedido.quitar").count() == 1
    avisos = Notificacao.objects.filter(conta=arranjo.a, evento="pagamento_confirmado")
    assert avisos.count() == 1
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "pago"


# --- E08-05: prazo, bloqueio e margem (A-20 e A-21) ----------------------------------------


def _aprovada_as_23h59(relogio: RelogioControlado, sim: Any) -> tuple[Arranjo, Pedido, str]:
    arranjo, x = pedido_aberto(relogio)
    p = tentativa_criada(x).id_externo
    assert p is not None
    relogio.congelar(T0 + timedelta(hours=23, minutes=59))
    sim.aprovar(p)
    relogio.congelar(T0 + timedelta(hours=24))
    return arranjo, x, p


def _bloquear_e_processar() -> None:
    bloquear_tentativas_vencidas_agora()
    processar_chamadas()


def _aviso_e_processar(sim: Any) -> None:
    sim.entregar_avisos()
    processar_chamadas()


def _confere_quitado(arranjo: Arranjo, x: Pedido) -> None:
    situacao = SituacaoDoPedido.objects.get(pedido=x)
    assert (situacao.situacao, situacao.quitado_em) == (
        "pago",
        T0 + timedelta(hours=23, minutes=59),
    )
    assert DestinoDoPagamento.objects.filter(pedido=x, destino="quita").count() == 1
    assert DestinoDoPagamento.objects.exclude(destino="quita").count() == 0
    assert Notificacao.objects.filter(conta=arranjo.a, evento="pagamento_confirmado").count() == 1


@pytest.mark.acceptance
@pytest.mark.parametrize("ordem", ["bloqueio_e_depois_aviso", "aviso_e_depois_bloqueio"])
def test_bloqueio_e_aviso_em_qualquer_ordem_quitam_uma_vez(
    relogio: RelogioControlado, simulador_pagamentos: Any, ordem: str
) -> None:  # A-20 (i) e (ii), T-7
    arranjo, x, _ = _aprovada_as_23h59(relogio, simulador_pagamentos)
    if ordem == "bloqueio_e_depois_aviso":
        _bloquear_e_processar()
        _aviso_e_processar(simulador_pagamentos)
    else:
        _aviso_e_processar(simulador_pagamentos)
        _bloquear_e_processar()
    _confere_quitado(arranjo, x)


@pytest.mark.acceptance
def test_bloqueio_e_aviso_ao_mesmo_tempo_quitam_uma_vez(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-20 (iii), T-7
    arranjo, x, _ = _aprovada_as_23h59(relogio, simulador_pagamentos)

    def bloqueia(barreira: Any) -> None:
        barreira.wait(timeout=10)
        _bloquear_e_processar()

    def avisa(barreira: Any) -> None:
        barreira.wait(timeout=10)
        _aviso_e_processar(simulador_pagamentos)

    resultados = executar_em_paralelo(bloqueia, avisa)
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    processar_chamadas()  # o que a corrida deixou pendente, na próxima execução da tarefa
    _confere_quitado(arranjo, x)


def test_bloqueio_e_aviso_de_outra_mudanca_ao_mesmo_tempo(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-21, T-7
    _, x = pedido_aberto(relogio)
    p = tentativa_criada(x).id_externo
    assert p is not None
    simulador_pagamentos.reemitir_aviso(p)
    relogio.congelar(T0 + timedelta(hours=24))

    def bloqueia(barreira: Any) -> None:
        barreira.wait(timeout=10)
        _bloquear_e_processar()

    def avisa(barreira: Any) -> None:
        barreira.wait(timeout=10)
        _aviso_e_processar(simulador_pagamentos)

    resultados = executar_em_paralelo(bloqueia, avisa)
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    processar_chamadas()
    assert PagamentoNoProvedor.objects.get(id_externo=p).situacao == "cancelado"
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "aguardando_pagamento"
    assert DestinoDoPagamento.objects.count() == 0


# --- E08-06: moderação (A-11 e A-12) -------------------------------------------------------


@pytest.mark.parametrize("ordem", ["pagamento_antes", "suspensao_antes"])
def test_suspensao_e_pagamento_ao_mesmo_tempo(
    relogio: RelogioControlado, simulador_pagamentos: Any, ordem: str
) -> None:  # A-11, reescrito pela correção R02
    arranjo, x = pedido_aberto(relogio)
    administrador_ = administrador()
    if ordem == "pagamento_antes":
        resultados = executar_em_paralelo(
            segurando(lambda: pedir_pagamento(arranjo.a, x)),
            esperando(lambda: suspender(administrador_, arranjo.a)),
        )
        assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
        tentativa = TentativaDePagamento.objects.get(pedido=x)
        assert tentativa.situacao == "solicitada"
        assert ChamadaAoProvedor.objects.filter(operacao="cancelar_cobranca").count() == 0
        processar_chamadas()  # só depois das duas threads, fora de qualquer transação de teste
        tentativa.refresh_from_db()
        assert (tentativa.situacao, tentativa.codigo_da_falha) == ("nao_criada", "pedido_cancelado")
        assert CobrancaSimulada.objects.count() == 0
    else:
        resultados = executar_em_paralelo(
            segurando(lambda: suspender(administrador_, arranjo.a)),
            esperando(lambda: pedir_pagamento(arranjo.a, x)),
        )
        assert resultados[0].excecao is None, resultados[0].excecao
        assert isinstance(resultados[1].excecao, PagamentoRecusado), resultados[1].excecao
        assert resultados[1].excecao.codigo in ("pedido_cancelado", "conta_inativa")
        assert TentativaDePagamento.objects.filter(pedido=x).count() == 0
        assert ChamadaAoProvedor.objects.count() == 0
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "cancelado"
    assert not CobrancaSimulada.objects.filter(situacao="pendente").exists()


def _criacao_parada_no_provedor(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Event, Event]:
    """A criação chama o simulador de verdade e depois fica parada até `liberar` (com prazo)."""
    original = OPERACOES["criar_cobranca"]
    entrou, liberar = Event(), Event()

    def parada(provedor: Any, chamada: ChamadaAoProvedor) -> Any:
        resultado = original.executar(provedor, chamada)
        entrou.set()
        assert liberar.wait(20), "a outra thread esperou a criação parada"
        return resultado

    monkeypatch.setitem(
        OPERACOES,
        "criar_cobranca",
        Operacao(parada, original.concluir, original.falhou, original.combinar),
    )
    return entrou, liberar


@pytest.mark.parametrize("moderar", [suspender, remover], ids=["suspensao", "remocao"])
def test_moderacao_durante_a_criacao_nao_espera_e_a_cobranca_e_cancelada(
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    monkeypatch: pytest.MonkeyPatch,
    moderar: Any,
) -> None:  # A-14 (i) e (ii), correção R02
    arranjo, x = pedido_aberto(relogio)
    tentativa = pedir_pagamento(arranjo.a, x)
    entrou, liberar = _criacao_parada_no_provedor(monkeypatch)
    primeira_terminou = Event()
    administrador_ = administrador()

    def executa_a_criacao(barreira: Any) -> int:
        barreira.wait(timeout=10)
        try:
            return processar_chamadas()
        finally:
            primeira_terminou.set()

    def modera(barreira: Any) -> bool:
        barreira.wait(timeout=10)
        assert entrou.wait(10), "a criação não entrou em execução"
        moderar(administrador_, arranjo.a)
        terminou_antes = not primeira_terminou.is_set()
        liberar.set()
        return terminou_antes

    resultados = executar_em_paralelo(executa_a_criacao, modera)
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert resultados[1].valor is True  # a moderação terminou sem esperar a criação
    motivo = "suspensao" if moderar is suspender else "remocao_da_conta"
    tentativa.refresh_from_db()
    assert tentativa.situacao == "criada"
    (cancelamento,) = ChamadaAoProvedor.objects.filter(operacao="cancelar_cobranca")
    assert cancelamento.alvo == f"t{tentativa.pk}:{motivo}"
    processar_chamadas()
    (cobranca,) = CobrancaSimulada.objects.all()
    assert cobranca.situacao == "cancelado"
    assert PagamentoNoProvedor.objects.get(id_externo=cobranca.id_externo).situacao == "cancelado"
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "cancelado"
    assert DestinoDoPagamento.objects.count() == 0
    if moderar is suspender:  # A-15
        reativar(administrador_, arranjo.a)
        cliente = Client()
        cliente.force_login(arranjo.a)
        resposta = cliente.post(f"/pedidos/{x.pk}/pagar/")
        assert resposta.status_code == 409
        assert "Este pedido foi cancelado e não pode mais ser pago." in resposta.content.decode()
        assert TentativaDePagamento.objects.filter(pedido=x).count() == 1
        assert CobrancaSimulada.objects.count() == 1


def test_a_suspensao_nao_espera_o_cancelamento_em_andamento(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-12, correção E07-R01
    arranjo, x = pedido_aberto(relogio)
    tentativa = tentativa_criada(x)
    with transaction.atomic():
        agendar_cancelamento(tentativa, "prazo")
    original = OPERACOES["cancelar_cobranca"]
    entrou, liberar, primeira_terminou = Event(), Event(), Event()

    def parada(provedor: Any, chamada: ChamadaAoProvedor) -> Any:
        entrou.set()
        assert liberar.wait(20), "a suspensão esperou a chamada em andamento"
        return original.executar(provedor, chamada)

    monkeypatch.setitem(
        OPERACOES, "cancelar_cobranca", Operacao(parada, original.concluir, original.falhou)
    )
    administrador_ = administrador()

    def executa_a_chamada(barreira: Any) -> int:
        barreira.wait(timeout=10)
        try:
            return processar_chamadas()
        finally:
            primeira_terminou.set()

    def suspende(barreira: Any) -> bool:
        barreira.wait(timeout=10)
        assert entrou.wait(10), "a chamada não entrou em execução"
        suspender(administrador_, arranjo.a)
        terminou_antes = not primeira_terminou.is_set()
        liberar.set()
        return terminou_antes

    resultados = executar_em_paralelo(executa_a_chamada, suspende)
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert resultados[1].valor is True
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "cancelado"
    alvos = sorted(
        ChamadaAoProvedor.objects.filter(operacao="cancelar_cobranca").values_list(
            "alvo", flat=True
        )
    )
    assert alvos == [f"t{tentativa.pk}:prazo", f"t{tentativa.pk}:suspensao"]


# --- E08-03, correção R02: pedido quitado com a criação em andamento (A-27) -----------------


def test_pedido_quitado_durante_a_criacao_cancela_a_cobranca_nova(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-27
    arranjo, x = pedido_aberto(relogio)
    primeira = tentativa_criada(x)
    id_primeira = primeira.id_externo
    assert id_primeira is not None
    simulador_pagamentos.expirar(id_primeira)
    sincronizar(id_primeira)
    segunda = pedir_pagamento(arranjo.a, x)
    entrou, liberar = _criacao_parada_no_provedor(monkeypatch)
    criacao_terminou = Event()

    def executa_a_criacao(barreira: Any) -> int:
        barreira.wait(timeout=10)
        try:
            return processar_chamadas()
        finally:
            criacao_terminou.set()

    def quita(barreira: Any) -> bool:
        barreira.wait(timeout=10)
        assert entrou.wait(10), "a criação não entrou em execução"
        simulador_pagamentos.aprovar(id_primeira)
        sincronizar(id_primeira)
        terminou_antes = not criacao_terminou.is_set()
        liberar.set()
        return terminou_antes

    resultados = executar_em_paralelo(executa_a_criacao, quita)
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert resultados[1].valor is True  # a quitação terminou sem esperar a criação
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "pago"
    segunda.refresh_from_db()
    assert segunda.situacao == "criada"
    (cancelamento,) = ChamadaAoProvedor.objects.filter(operacao="cancelar_cobranca")
    assert cancelamento.alvo == f"t{segunda.pk}:pedido_pago"
    processar_chamadas()
    assert segunda.id_externo is not None
    cobranca = CobrancaSimulada.objects.get(pk=int(segunda.id_externo.removeprefix("sim-")))
    assert cobranca.situacao == "cancelado"


# --- Correção E08-R08: a recuperação de vários pagamentos não inverte as travas ---------------


def _recuperacao_parada(monkeypatch: pytest.MonkeyPatch) -> tuple[Event, Event]:
    """O ponto de pausa Π: a recuperação (`falhou` da criação) roda inteira e fica parada, com a
    transação da chamada aberta, até `liberar` (com prazo). O ponto existe antes e depois da
    correção; o que mudou é o que a transação segura quando ela chega aqui."""
    original = OPERACOES["criar_cobranca"]
    parou, liberar = Event(), Event()

    def falhou_e_para(chamada: ChamadaAoProvedor, erro: Exception) -> None:
        assert original.falhou is not None
        original.falhou(chamada, erro)
        parou.set()
        assert liberar.wait(30), "ninguém liberou a recuperação"

    monkeypatch.setitem(
        OPERACOES,
        "criar_cobranca",
        Operacao(original.executar, original.concluir, falhou_e_para, original.combinar),
    )
    return parou, liberar


def _destinos_do(pedido: Pedido) -> list[tuple[str, str]]:
    return sorted(DestinoDoPagamento.objects.filter(pedido=pedido).values_list("destino", "motivo"))


def _outra_thread_termina_enquanto_a_recuperacao_para(
    monkeypatch: pytest.MonkeyPatch,
    trabalho: Any,
    conferir_as_travas: Any = None,
) -> tuple[list[Any], Event]:
    """Roda a recuperação parada em Π, o `trabalho` numa segunda thread e um controle que só
    libera a recuperação depois de ver o `trabalho` terminar. Se ele não termina, o controle
    falha por asserção (nunca por deadlock ou tempo esgotado da infraestrutura)."""
    parou, liberar = _recuperacao_parada(monkeypatch)
    terminou = Event()

    def recupera(barreira: Any) -> int:
        barreira.wait(timeout=10)
        return processar_chamadas()

    def outra(barreira: Any) -> None:
        barreira.wait(timeout=10)
        assert parou.wait(15), "a recuperação não chegou ao ponto de pausa"
        trabalho()
        terminou.set()

    def controle(barreira: Any) -> None:
        barreira.wait(timeout=10)
        try:
            assert parou.wait(15), "a recuperação não chegou ao ponto de pausa"
            assert terminou.wait(8), (
                "a outra thread não terminou enquanto a recuperação estava parada: "
                "a transação da recuperação a segura"
            )
            if conferir_as_travas is not None:
                conferir_as_travas()
        finally:
            liberar.set()

    resultados = executar_em_paralelo(recupera, outra, controle)
    return resultados, terminou


def test_aviso_de_um_pagamento_nao_espera_a_recuperacao_dos_outros(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-29, correção R08
    _, x, primeira, segunda, terceira = recuperacao_de_dois_pagamentos(
        relogio, simulador_pagamentos
    )
    assert primeira.id_externo is not None
    assert segunda.id_externo is not None

    def aviso_da_segunda() -> None:
        sincronizar(segunda.id_externo or "", "aviso")

    def travas_livres() -> None:
        try:
            with transaction.atomic():
                PagamentoNoProvedor.objects.select_for_update(nowait=True).get(
                    id_externo=primeira.id_externo
                )
                SituacaoDoPedido.objects.select_for_update(nowait=True).get(pedido=x)
        except DatabaseError as erro:
            raise AssertionError(
                f"a recuperação segura a trava do pagamento 1 ou do pedido: {erro}"
            ) from None

    resultados, _ = _outra_thread_termina_enquanto_a_recuperacao_para(
        monkeypatch, aviso_da_segunda, travas_livres
    )
    assert all(r.excecao is None for r in resultados), [repr(r.excecao) for r in resultados]
    assert _destinos_do(x) == [("devolucao", "duplicidade"), ("quita", "")]
    terceira.refresh_from_db()
    assert (terceira.situacao, terceira.codigo_da_falha) == ("nao_criada", "prazo_encerrado")
    assert not CobrancaSimulada.objects.filter(
        chave_idempotencia=terceira.chave_idempotencia
    ).exists()


def test_reconsulta_da_margem_nao_espera_a_recuperacao_e_nao_duplica(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-30, correção R08, E08-05
    arranjo, x, _, _, terceira = recuperacao_de_dois_pagamentos(relogio, simulador_pagamentos)
    destinos_durante: list[list[tuple[str, str]]] = []

    def reconsulta() -> None:
        reconsultar_pagamentos_da_margem_agora()
        destinos_durante.append(_destinos_do(x))

    resultados, _ = _outra_thread_termina_enquanto_a_recuperacao_para(monkeypatch, reconsulta)
    assert all(r.excecao is None for r in resultados), [repr(r.excecao) for r in resultados]
    assert destinos_durante == [[("devolucao", "duplicidade"), ("quita", "")]]
    assert _destinos_do(x) == [("devolucao", "duplicidade"), ("quita", "")]
    assert DestinoDoPagamento.objects.filter(pedido=x).count() == 2
    avisos = Notificacao.objects.filter(conta=arranjo.a, evento="pagamento_confirmado")
    assert avisos.count() == 1
    terceira.refresh_from_db()
    assert (terceira.situacao, terceira.codigo_da_falha) == ("nao_criada", "prazo_encerrado")


def test_aviso_novo_antes_da_recuperacao_fica_com_uma_consulta_so(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-33, E07-06
    _, x, primeira, segunda, terceira = recuperacao_de_dois_pagamentos(
        relogio, simulador_pagamentos
    )
    assert segunda.id_externo is not None
    with transaction.atomic():
        agendar_chamada(
            "consultar_pagamento",
            segunda.id_externo,
            parametros={"origem": "aviso", "aviso_recebido_em": agora().isoformat()},
        )
    processar_chamadas()
    consultas = ChamadaAoProvedor.objects.filter(
        operacao="consultar_pagamento", alvo=segunda.id_externo
    )
    assert consultas.count() == 1
    assert _destinos_do(x) == [("devolucao", "duplicidade"), ("quita", "")]
    assert DestinoDoPagamento.objects.filter(pedido=x).count() == 2
    terceira.refresh_from_db()
    assert (terceira.situacao, terceira.codigo_da_falha) == ("nao_criada", "prazo_encerrado")
    assert (
        ChamadaAoProvedor.objects.filter(
            operacao="consultar_pagamento", alvo=primeira.id_externo
        ).count()
        == 1
    )
