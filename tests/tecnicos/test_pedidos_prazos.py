"""E08-05: prazo de pagamento, bloqueio, margem e improrrogabilidade (acceptance A-1 a A-15,
A-18 e A-19)."""

import importlib
import logging
import re
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django import forms
from django.db import DatabaseError, connection, transaction
from django.test import Client
from django.urls import get_resolver

from apps.contas.permissoes import _rotas
from apps.interesses.servicos import adicionar_interesse
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from apps.pagamentos.chamadas import OPERACOES, Operacao, agendar_chamada, processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor, PagamentoNoProvedor, SituacaoDaChamada
from apps.pagamentos.provedor import NovaCobranca, RecusaDoProvedor, obter_provedor
from apps.pagamentos.sinais import situacao_do_pagamento_mudou
from apps.pedidos import tarefas
from apps.pedidos.models import (
    AberturaDoPagamento,
    DestinoDoPagamento,
    Pedido,
    SituacaoDoPedido,
)
from apps.pedidos.pagamento import PagamentoRecusado, agendar_cancelamento, pedir_pagamento
from apps.pedidos.prazos import (
    aceita_tentativas,
    em_margem,
    fim_da_margem,
    pode_iniciar_apuracao,
    prazo_de_pagamento,
)
from apps.pedidos.tarefas import (
    bloquear_tentativas_vencidas_agora,
    reconsultar_pagamentos_da_margem_agora,
)
from apps.rodadas.condicoes import InteressesBloqueados
from apps.rodadas.models import Etapa, Rodada
from apps.simulador_pagamentos.models import CobrancaSimulada
from tests.apoio.admin_fluxos import administrador_logado
from tests.apoio.pedidos import (
    T0,
    Arranjo,
    abertura_unica,
    cancelar_direto,
    marcar_pago,
    pedido_aberto,
    pedido_avulso,
    pedido_de,
    pedido_na_abertura,
    sincronizar,
    tentativa_criada,
)
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)
MS = timedelta(milliseconds=1)
MIN = timedelta(minutes=1)
PRAZO = T0 + 24 * H
MARGEM = T0 + 48 * H


@pytest.fixture
def cenario(relogio: RelogioControlado, simulador_pagamentos: Any) -> tuple[Arranjo, Pedido, Any]:
    arranjo, x = pedido_aberto(relogio)
    return arranjo, x, simulador_pagamentos


def _chamadas(operacao: str = "cancelar_cobranca") -> list[ChamadaAoProvedor]:
    return list(ChamadaAoProvedor.objects.filter(operacao=operacao).order_by("pk"))


def _situacao(pedido: Pedido) -> SituacaoDoPedido:
    return SituacaoDoPedido.objects.get(pedido=pedido)


def test_as_fronteiras_da_linha_do_tempo(cenario: tuple[Arranjo, Pedido, Any]) -> None:  # A-1
    _, x, _ = cenario
    abertura = x.abertura
    assert prazo_de_pagamento(abertura) == PRAZO
    assert fim_da_margem(abertura) == MARGEM
    instantes = [PRAZO - MS, PRAZO, MARGEM - MS, MARGEM, MARGEM + MS]
    assert [aceita_tentativas(abertura, t) for t in instantes] == [True, False, False, False, False]
    assert [em_margem(abertura, t) for t in instantes] == [False, True, True, True, False]
    assert [pode_iniciar_apuracao(abertura, t) for t in instantes] == [
        False,
        False,
        False,
        True,
        True,
    ]


@pytest.mark.acceptance
def test_a_apuracao_so_pode_comecar_em_48_horas(
    cenario: tuple[Arranjo, Pedido, Any],
) -> None:  # A-2, cenário 27 (verificação de tempo)
    arranjo, x, _ = cenario
    y = pedido_de(arranjo.b)
    marcar_pago(x, T0 + 30 * MIN)
    marcar_pago(y, T0 + 40 * MIN)
    abertura = x.abertura
    assert pode_iniciar_apuracao(abertura, MARGEM - MS) is False
    assert pode_iniciar_apuracao(abertura, MARGEM) is True
    assert Rodada.objects.get(pk=arranjo.rodada.pk).etapa == Etapa.PAGAMENTO
    assert not EntradaAuditoria.objects.filter(acao__startswith="rodada.apurar").exists()


def _duas_tentativas(arranjo: Arranjo, x: Pedido, sim: Any) -> tuple[Any, Any]:
    """X com a cobrança pendente; Y (de B) com a cobrança aprovada e o pedido pago."""
    ta = tentativa_criada(x)
    y = pedido_de(arranjo.b)
    tb = tentativa_criada(y)
    assert tb.id_externo is not None
    sim.aprovar(tb.id_externo)
    sincronizar(tb.id_externo)
    assert _situacao(y).situacao == "pago"
    return ta, tb


def test_bloqueio_cancela_so_o_que_esta_pendente(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-3, Infra 4.3, L-2
    arranjo, x, sim = cenario
    ta, tb = _duas_tentativas(arranjo, x, sim)
    relogio.congelar(PRAZO)
    assert bloquear_tentativas_vencidas_agora() == 1
    (chamada,) = _chamadas()
    assert chamada.alvo == f"t{ta.pk}:prazo"
    assert processar_chamadas() == 1
    from apps.simulador_pagamentos.models import CobrancaSimulada

    assert CobrancaSimulada.objects.get(chave_idempotencia=ta.chave_idempotencia).situacao == (
        "cancelado"
    )
    assert not ChamadaAoProvedor.objects.filter(alvo__startswith=f"t{tb.pk}:").exists()


def test_bloqueio_nao_repete_o_que_ja_foi_agendado(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-4
    arranjo, x, sim = cenario
    _duas_tentativas(arranjo, x, sim)
    relogio.congelar(PRAZO)
    assert bloquear_tentativas_vencidas_agora() == 1
    processar_chamadas()
    relogio.congelar(PRAZO + MIN)
    assert bloquear_tentativas_vencidas_agora() == 0
    assert len(_chamadas()) == 1


def test_cancelamento_recusado_nao_e_reagendado(
    cenario: tuple[Arranjo, Pedido, Any],
    relogio: RelogioControlado,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-5
    _, x, _ = cenario
    ta = tentativa_criada(x)
    original = OPERACOES["cancelar_cobranca"]

    def recusa(provedor: Any, chamada: ChamadaAoProvedor) -> Any:
        raise RecusaDoProvedor("recusado")

    monkeypatch.setitem(OPERACOES, "cancelar_cobranca", Operacao(recusa, original.concluir))
    relogio.congelar(PRAZO)
    assert bloquear_tentativas_vencidas_agora() == 1
    assert processar_chamadas() == 1
    (chamada,) = _chamadas()
    assert chamada.situacao == SituacaoDaChamada.FALHOU
    from apps.simulador_pagamentos.models import CobrancaSimulada

    assert CobrancaSimulada.objects.get(chave_idempotencia=ta.chave_idempotencia).situacao == (
        "pendente"
    )
    relogio.congelar(PRAZO + H)
    assert bloquear_tentativas_vencidas_agora() == 0
    (mesma,) = _chamadas()
    assert (mesma.pk, mesma.situacao) == (chamada.pk, SituacaoDaChamada.FALHOU)


def test_antes_do_prazo_o_bloqueio_nao_faz_nada(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-6
    _, x, _ = cenario
    tentativa_criada(x)
    relogio.congelar(PRAZO - MS)
    assert bloquear_tentativas_vencidas_agora() == 0
    assert _chamadas() == []


@pytest.mark.acceptance
def test_com_o_bloqueio_parado_o_servidor_recusa_a_tentativa(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-7, cenário 12, T-1
    arranjo, x, _ = cenario
    relogio.congelar(PRAZO + 5 * MIN)
    with pytest.raises(PagamentoRecusado) as erro:
        pedir_pagamento(arranjo.a, x)
    assert erro.value.codigo == "prazo_encerrado"
    assert x.tentativas.count() == 0


@pytest.mark.acceptance
def test_na_margem_nada_se_reabre(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-8, cenário 12
    arranjo, x, _ = cenario
    relogio.congelar(T0 + 30 * H)
    antes = list(Pedido.objects.order_by("pk").values())
    c = ContaFactory.create()
    with pytest.raises(InteressesBloqueados):
        adicionar_interesse(c, arranjo.p1, "1")
    cliente = Client()
    cliente.force_login(arranjo.a)
    for quantidade in ("7", "5"):
        resposta = cliente.post(
            "/interesses/", {"produto": arranjo.p1.pk, "quantidade": quantidade}
        )
        assert resposta.status_code == 409
    with pytest.raises(PagamentoRecusado) as erro:
        pedir_pagamento(arranjo.a, x)
    assert erro.value.codigo == "prazo_encerrado"
    assert list(Pedido.objects.order_by("pk").values()) == antes
    assert x.tentativas.count() == 0


@pytest.mark.acceptance
def test_depois_de_48_horas_nada_acontece_sozinho(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-9, cenário 12
    arranjo, x, _ = cenario
    tentativa_criada(x)
    relogio.congelar(T0 + 49 * H)
    bloquear_tentativas_vencidas_agora()
    reconsultar_pagamentos_da_margem_agora()
    processar_chamadas()
    assert Rodada.objects.get(pk=arranjo.rodada.pk).etapa == Etapa.PAGAMENTO
    for comprador in (arranjo.a, arranjo.b):
        assert _situacao(pedido_de(comprador)).situacao == "aguardando_pagamento"
    acoes = EntradaAuditoria.objects.values_list("acao", flat=True)
    assert not [a for a in acoes if a.startswith(("rodada.apurar", "pedido.cancelar"))]


def _aprovada_por_fora(x: Pedido, sim: Any, relogio: RelogioControlado) -> str:
    """Uma cobrança de X aprovada às T0 + 23h, sem aviso entregue e sem registro no sistema."""
    criada = obter_provedor().criar_cobranca(
        NovaCobranca(
            chave_idempotencia="por-fora-1",
            referencia_externa=x.referencia_externa,
            valor=x.total,
            descricao="Cobrança de apoio",
            expira_em=T0 + 30 * H,
        )
    )
    id_externo = criada.pagamento.id_externo
    relogio.congelar(T0 + 23 * H)
    sim.aprovar(id_externo)
    return str(id_externo)


@pytest.mark.acceptance
def test_a_margem_reconsulta_e_encontra_o_pagamento_sem_aviso(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-10, Infra 4.3, L-6
    arranjo, x, sim = cenario
    _aprovada_por_fora(x, sim, relogio)
    relogio.congelar(T0 + 25 * H)
    assert reconsultar_pagamentos_da_margem_agora() == 2
    situacao = _situacao(x)
    assert (situacao.situacao, situacao.quitado_em) == ("pago", T0 + 23 * H)
    avisos = Notificacao.objects.filter(conta=arranjo.a, evento="pagamento_confirmado")
    assert avisos.count() == 1


@pytest.mark.parametrize("instante", [T0 + 23 * H + 59 * MIN, MARGEM + MS])
def test_fora_da_margem_a_reconsulta_nao_consulta_nada(
    cenario: tuple[Arranjo, Pedido, Any],
    relogio: RelogioControlado,
    monkeypatch: pytest.MonkeyPatch,
    instante: Any,
) -> None:  # A-11
    _, x, sim = cenario
    _aprovada_por_fora(x, sim, relogio)

    def nunca(referencia: str) -> Any:
        raise AssertionError("não devia consultar")

    monkeypatch.setattr(tarefas, "consultar_antes_de_decidir", nunca)
    relogio.congelar(instante)
    assert reconsultar_pagamentos_da_margem_agora() == 0
    assert _situacao(x).situacao == "aguardando_pagamento"


def test_provedor_fora_do_ar_na_margem_registra_o_motivo(
    cenario: tuple[Arranjo, Pedido, Any],
    relogio: RelogioControlado,
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-12
    arranjo, _, sim = cenario
    antes = list(SituacaoDoPedido.objects.order_by("pk").values())
    relogio.congelar(T0 + 25 * H)
    sim.indisponivel()
    caplog.set_level(logging.WARNING)
    assert reconsultar_pagamentos_da_margem_agora() == 0
    avisos = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    for comprador in (arranjo.a, arranjo.b):
        pedido = pedido_de(comprador)
        assert any(f"pedido={pedido.pk}" in m and "indisponivel" in m for m in avisos), avisos
    assert list(SituacaoDoPedido.objects.order_by("pk").values()) == antes


def test_a_margem_decide_o_destino_que_ficou_pendente(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-13
    _, x, sim = cenario
    tentativa = tentativa_criada(x)
    assert tentativa.id_externo is not None
    sim.aprovar(tentativa.id_externo)
    situacao_do_pagamento_mudou.disconnect(dispatch_uid="pedidos.quitacao")
    try:
        sincronizar(tentativa.id_externo)
    finally:
        from apps.pedidos.receptores import decidir_destino_do_pagamento_aprovado

        situacao_do_pagamento_mudou.connect(
            decidir_destino_do_pagamento_aprovado, dispatch_uid="pedidos.quitacao"
        )
    assert _situacao(x).situacao == "aguardando_pagamento"
    relogio.congelar(T0 + 25 * H)
    reconsultar_pagamentos_da_margem_agora()
    assert _situacao(x).situacao == "pago"


NOMES_DE_PRAZO = {"t0", "prazo_de_pagamento", "fim_da_margem", "margem"}


def _campos_dos_formularios() -> set[str]:
    nomes: set[str] = set()
    for modulo in ("forms", "formularios"):
        for app in ("catalogo", "contas", "fornecedores", "interesses", "notificacoes", "rodadas"):
            try:
                carregado = importlib.import_module(f"apps.{app}.{modulo}")
            except ModuleNotFoundError:
                continue
            for valor in vars(carregado).values():
                if isinstance(valor, type) and issubclass(valor, forms.BaseForm):
                    nomes.update(getattr(valor, "base_fields", {}))
    return nomes


@pytest.mark.acceptance
def test_nenhuma_rota_formulario_ou_servico_altera_os_prazos(
    client: Client, webauthn: Any, relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-14, T-5, cenário 28, P-7
    relogio.congelar(T0)
    administrador_logado(client)
    arranjo, x = pedido_aberto(relogio)
    suspeitas = [
        (caminho, nome)
        for caminho, nome, _ in _rotas(get_resolver().url_patterns)
        if re.search(r"t0|margem|prazo_de_pagamento|prazo-de-pagamento", f"{caminho} {nome}")
    ]
    assert suspeitas == []
    assert _campos_dos_formularios() & NOMES_DE_PRAZO == set()
    antes = (x.abertura.t0, list(AberturaDoPagamento.objects.values()))
    resposta = client.post(
        f"/administracao/rodadas/{arranjo.rodada.pk}/fechamento/prorrogar/",
        {"termino": "2026-12-31T10:00"},
    )
    assert resposta.status_code == 409
    assert "Só um fechamento em andamento pode ser prorrogado." in resposta.content.decode()
    assert (
        AberturaDoPagamento.objects.get(pk=x.abertura_id).t0,
        list(AberturaDoPagamento.objects.values()),
    ) == antes


@pytest.mark.acceptance
def test_o_t0_nao_muda_nem_por_sql(cenario: tuple[Arranjo, Pedido, Any]) -> None:  # A-15, T-5
    _, x, _ = cenario
    abertura = x.abertura
    abertura.t0 = T0 + H
    with pytest.raises(RegistroImutavel):
        abertura.save()
    with pytest.raises(RegistroImutavel):
        AberturaDoPagamento.objects.filter(pk=abertura.pk).update(t0=T0 + H)
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE pedidos_aberturadopagamento SET t0 = t0 + interval '1 hour'")
    atual = AberturaDoPagamento.objects.get(pk=abertura.pk)
    assert (prazo_de_pagamento(atual), fim_da_margem(atual)) == (PRAZO, MARGEM)


def test_as_tarefas_estao_registradas_como_periodicas() -> None:  # A-18
    from procrastinate.contrib.django import app

    esperadas = {
        "bloquear_tentativas_vencidas": "* * * * *",
        "reconsultar_pagamentos_da_margem": "*/10 * * * *",
    }
    for nome, cron in esperadas.items():
        candidatas = [
            pt for pt in app.periodic_registry.periodic_tasks.values() if pt.task.name == nome
        ]
        assert len(candidatas) == 1, nome
        assert candidatas[0].cron == cron
        assert candidatas[0].task.queueing_lock == nome


def test_falha_numa_abertura_nao_impede_as_outras(
    cenario: tuple[Arranjo, Pedido, Any],
    relogio: RelogioControlado,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-19
    arranjo, x, _ = cenario
    avulso = pedido_avulso(arranjo.a, "G", "50.00")
    tentativa_criada(x)
    tentativa_criada(avulso)
    primeira = x.abertura_id
    original = agendar_cancelamento

    def falha_na_primeira(tentativa: Any, motivo: str) -> Any:
        if tentativa.pedido.abertura_id == primeira:
            raise RuntimeError("falha de teste")
        return original(tentativa, motivo)

    monkeypatch.setattr(tarefas, "agendar_cancelamento", falha_na_primeira)
    relogio.congelar(PRAZO)
    caplog.set_level(logging.ERROR)
    assert bloquear_tentativas_vencidas_agora() == 1
    mensagens = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any(f"abertura={primeira}" in m and "RuntimeError" in m for m in mensagens), mensagens
    assert [c.alvo.split(":")[0] for c in _chamadas()] == [f"t{avulso.tentativas.get().pk}"]


# --- Correção E08-R01 e E08-R03: reconsulta de todos os pedidos e bloqueio por pagamento -----


def _orfa(pedido: Pedido, chave: str) -> str:
    """Cobrança criada direto no simulador, com a referência do pedido e uma chave que não é de
    nenhuma tentativa: é a resposta de criação que se perdeu."""
    criada = obter_provedor().criar_cobranca(
        NovaCobranca(
            chave_idempotencia=chave,
            referencia_externa=pedido.referencia_externa,
            valor=pedido.total,
            descricao="Cobrança órfã de apoio",
            expira_em=PRAZO,
        )
    )
    return str(criada.pagamento.id_externo)


def _pagamento(id_externo: str) -> PagamentoNoProvedor:
    return PagamentoNoProvedor.objects.get(id_externo=id_externo)


def _destinos(pedido: Pedido) -> list[tuple[str, str]]:
    return sorted(DestinoDoPagamento.objects.filter(pedido=pedido).values_list("destino", "motivo"))


@pytest.mark.acceptance
def test_a_margem_reconsulta_o_pedido_ja_pago_e_devolve_a_duplicidade(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-22, §8.3 duplicidade na margem
    arranjo, x, sim = cenario
    primeira = tentativa_criada(x)
    assert primeira.id_externo is not None
    sim.expirar(primeira.id_externo)
    sincronizar(primeira.id_externo)
    relogio.congelar(T0 + 2 * H)
    segunda = tentativa_criada(x)
    assert segunda.id_externo is not None
    relogio.congelar(T0 + 3 * H)
    sim.aprovar(segunda.id_externo)
    sincronizar(segunda.id_externo)
    assert _situacao(x).situacao == "pago"
    quitado_em = _situacao(x).quitado_em
    relogio.congelar(T0 + 25 * H)
    sim.aprovar(primeira.id_externo)  # sem aviso entregue
    reconsultar_pagamentos_da_margem_agora()
    assert _destinos(x) == [("devolucao", "duplicidade"), ("quita", "")]
    situacao = _situacao(x)
    assert (situacao.situacao, situacao.quitado_em) == ("pago", quitado_em)
    avisos = Notificacao.objects.filter(conta=arranjo.a, evento="pagamento_confirmado")
    assert avisos.count() == 1


def test_a_margem_reconsulta_pagos_aguardando_e_cancelados(
    cenario: tuple[Arranjo, Pedido, Any],
    relogio: RelogioControlado,
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-23
    _arranjo, x, sim = cenario
    paga = tentativa_criada(x)
    assert paga.id_externo is not None
    sim.aprovar(paga.id_externo)
    sincronizar(paga.id_externo)
    v = pedido_na_abertura(abertura_unica(), ContaFactory.create(), "40.00")
    cancelar_direto(v, "suspensao", T0 + 2 * H)
    relogio.congelar(T0 + 25 * H)
    caplog.set_level(logging.INFO, logger="apps.simulador_pagamentos")
    assert reconsultar_pagamentos_da_margem_agora() == 3
    buscas = [r for r in caplog.records if "buscar_por_referencia" in r.getMessage()]
    assert len(buscas) == 3
    assert {_situacao(x).situacao, _situacao(v).situacao} == {"pago", "cancelado"}


def test_o_bloqueio_cancela_a_cobranca_orfa_encontrada_na_margem(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-24, Infra 4.3
    arranjo, _, _ = cenario
    y = pedido_de(arranjo.b)
    relogio.congelar(T0 + 23 * H)
    id_externo = _orfa(y, "orfa-y")
    relogio.congelar(T0 + 25 * H)
    reconsultar_pagamentos_da_margem_agora()
    pagamento = _pagamento(id_externo)
    assert pagamento.situacao == "pendente"
    assert bloquear_tentativas_vencidas_agora() == 1
    (chamada,) = _chamadas()
    assert chamada.alvo == f"p{pagamento.pk}:prazo"
    assert chamada.parametros == {"id_externo": id_externo}
    assert processar_chamadas() == 1
    assert CobrancaSimulada.objects.get(chave_idempotencia="orfa-y").situacao == "cancelado"
    assert _pagamento(id_externo).situacao == "cancelado"
    assert bloquear_tentativas_vencidas_agora() == 0


@pytest.mark.parametrize("situacao_da_chamada", ["pendente", "falhou"])
def test_o_bloqueio_pula_a_orfa_que_ja_tem_cancelamento(
    cenario: tuple[Arranjo, Pedido, Any],
    relogio: RelogioControlado,
    monkeypatch: pytest.MonkeyPatch,
    situacao_da_chamada: str,
) -> None:  # A-25
    arranjo, _, _ = cenario
    y = pedido_de(arranjo.b)
    relogio.congelar(T0 + 23 * H)
    id_externo = _orfa(y, "orfa-y")
    relogio.congelar(T0 + 25 * H)
    reconsultar_pagamentos_da_margem_agora()
    with transaction.atomic():
        agendar_chamada(
            "cancelar_cobranca", "t999:recuperacao:1", parametros={"id_externo": id_externo}
        )
    if situacao_da_chamada == "falhou":
        original = OPERACOES["cancelar_cobranca"]

        def recusa(provedor: Any, chamada: ChamadaAoProvedor) -> Any:
            raise RecusaDoProvedor("recusado")

        monkeypatch.setitem(OPERACOES, "cancelar_cobranca", Operacao(recusa, original.concluir))
        processar_chamadas()
        (chamada,) = _chamadas()
        assert chamada.situacao == SituacaoDaChamada.FALHOU
    assert bloquear_tentativas_vencidas_agora() == 0
    assert len(_chamadas()) == 1


def test_o_bloqueio_cancela_a_orfa_de_pedido_pago_ou_cancelado(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-26
    _arranjo, x, sim = cenario
    paga = tentativa_criada(x)
    assert paga.id_externo is not None
    sim.aprovar(paga.id_externo)
    sincronizar(paga.id_externo)
    v = pedido_na_abertura(abertura_unica(), ContaFactory.create(), "40.00")
    cancelar_direto(v, "suspensao", T0 + 2 * H)
    relogio.congelar(T0 + 23 * H)
    orfa_x = _orfa(x, "orfa-x")
    orfa_v = _orfa(v, "orfa-v")
    destinos_antes = DestinoDoPagamento.objects.count()
    relogio.congelar(T0 + 25 * H)
    reconsultar_pagamentos_da_margem_agora()
    assert bloquear_tentativas_vencidas_agora() == 2
    assert sorted(c.alvo for c in _chamadas()) == sorted(
        [f"p{_pagamento(orfa_x).pk}:prazo", f"p{_pagamento(orfa_v).pk}:prazo"]
    )
    processar_chamadas()
    assert (_pagamento(orfa_x).situacao, _pagamento(orfa_v).situacao) == ("cancelado", "cancelado")
    assert (_situacao(x).situacao, _situacao(v).situacao) == ("pago", "cancelado")
    assert DestinoDoPagamento.objects.count() == destinos_antes


def test_resposta_perdida_no_prazo_e_cancelada_uma_vez_so(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-27, prova do parecer
    arranjo, x, sim = cenario
    relogio.congelar(T0 + 24 * H - 30 * timedelta(seconds=1))
    tentativa = pedir_pagamento(arranjo.a, x)
    sim.falhar_proximas(1, operacao="criar_cobranca", depois_de_executar=True)
    processar_chamadas()
    (cobranca,) = CobrancaSimulada.objects.all()
    relogio.congelar(T0 + 24 * H + MIN)
    assert processar_chamadas(limite=1) == 1  # a recusa; o cancelamento fica para depois
    reconsultar_pagamentos_da_margem_agora()
    assert bloquear_tentativas_vencidas_agora() == 0  # a recuperação já agendou o cancelamento
    processar_chamadas()
    cobranca.refresh_from_db()
    assert cobranca.situacao == "cancelado"
    tentativa.refresh_from_db()
    assert (tentativa.situacao, tentativa.codigo_da_falha) == ("nao_criada", "prazo_encerrado")
    assert _pagamento(cobranca.id_externo).situacao == "cancelado"
    (so,) = _chamadas()
    assert so.alvo == f"t{tentativa.pk}:recuperacao:1"


def test_antes_do_prazo_nem_a_margem_nem_o_bloqueio_agem(
    cenario: tuple[Arranjo, Pedido, Any],
    relogio: RelogioControlado,
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-28
    arranjo, _, _ = cenario
    y = pedido_de(arranjo.b)
    relogio.congelar(T0 + 23 * H)
    _orfa(y, "orfa-y")
    relogio.congelar(T0 + 23 * H + 59 * MIN)
    caplog.set_level(logging.INFO, logger="apps.simulador_pagamentos")
    assert reconsultar_pagamentos_da_margem_agora() == 0
    assert not any("buscar_por_referencia" in r.getMessage() for r in caplog.records)
    assert bloquear_tentativas_vencidas_agora() == 0
    assert _chamadas() == []
