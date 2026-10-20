"""E08-03: tentativas de pagamento e cobrança Pix (acceptance A-1 a A-13 e A-18)."""

import logging
from datetime import timedelta
from typing import Any

import pytest
from django.db import DatabaseError, connection, transaction
from django.db.models import Q
from django.db.transaction import TransactionManagementError

from apps.contas.models import Situacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.chamadas import (
    OPERACOES,
    FalhaDefinitiva,
    Operacao,
    agendar_chamada,
    processar_chamadas,
    registrar_operacao,
)
from apps.pagamentos.models import ChamadaAoProvedor, PagamentoNoProvedor, SituacaoDaChamada
from apps.pedidos.models import Pedido, SituacaoDoPedido, TentativaDePagamento
from apps.pedidos.pagamento import PagamentoRecusado, agendar_cancelamento, pedir_pagamento
from apps.simulador_pagamentos.models import CobrancaSimulada
from tests.apoio.pedidos import (
    T0,
    Arranjo,
    cancelar_direto,
    marcar_pago,
    pedido_aberto,
)
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

MS = timedelta(milliseconds=1)
MIN = timedelta(minutes=1)
PRAZO = T0 + timedelta(hours=24)


@pytest.fixture
def cenario(relogio: RelogioControlado, simulador_pagamentos: Any) -> tuple[Arranjo, Pedido, Any]:
    arranjo, pedido = pedido_aberto(relogio)
    return arranjo, pedido, simulador_pagamentos


def _chamadas(operacao: str) -> list[ChamadaAoProvedor]:
    return list(ChamadaAoProvedor.objects.filter(operacao=operacao).order_by("pk"))


def _tentativas(pedido: Pedido) -> list[TentativaDePagamento]:
    return list(TentativaDePagamento.objects.filter(pedido=pedido).order_by("numero"))


def _unica(pedido: Pedido) -> TentativaDePagamento:
    tentativas = _tentativas(pedido)
    assert len(tentativas) == 1, f"tentativas: {len(tentativas)}"
    return tentativas[0]


def _criada(arranjo: Arranjo, pedido: Pedido) -> TentativaDePagamento:
    pedir_pagamento(arranjo.a, pedido)
    assert processar_chamadas() == 1
    tentativa = _unica(pedido)
    assert tentativa.situacao == "criada"
    return tentativa


def test_pedir_pagamento_cria_a_tentativa_e_agenda_a_cobranca(
    cenario: tuple[Arranjo, Pedido, Any],
) -> None:  # A-1
    arranjo, x, _ = cenario
    tentativa = pedir_pagamento(arranjo.a, x)
    gravada = _unica(x)
    assert gravada.pk == tentativa.pk
    assert (gravada.numero, gravada.situacao) == (1, "solicitada")
    assert gravada.chave_idempotencia == f"om-p{x.pk}-t1"
    assert gravada.referencia_externa == f"om-c{arranjo.ciclo.pk}-p{x.pk}"
    assert (gravada.id_externo, gravada.dados_para_pagar, gravada.codigo_da_falha) == (
        None,
        {},
        "",
    )
    assert gravada.criada_em is None
    (chamada,) = _chamadas("criar_cobranca")
    assert chamada.alvo == f"t{gravada.pk}"
    assert chamada.chave_idempotencia == gravada.chave_idempotencia
    assert chamada.parametros == {"tentativa": gravada.pk}
    assert chamada.situacao == SituacaoDaChamada.PENDENTE
    assert CobrancaSimulada.objects.count() == 0
    (entrada,) = EntradaAuditoria.objects.filter(acao="pedido.pedir_pagamento")
    assert entrada.autor_id == str(arranjo.a.pk)
    assert entrada.alteracoes == {"pedido": x.pk, "numero": 1}


def test_a_tarefa_cria_a_cobranca_no_provedor(cenario: tuple[Arranjo, Pedido, Any]) -> None:
    # A-2
    arranjo, x, _ = cenario
    pedir_pagamento(arranjo.a, x)
    assert processar_chamadas() == 1
    (cobranca,) = CobrancaSimulada.objects.all()
    gravada = _unica(x)
    assert cobranca.chave_idempotencia == f"om-p{x.pk}-t1"
    assert cobranca.referencia_externa == f"om-c{arranjo.ciclo.pk}-p{x.pk}"
    assert str(cobranca.valor) == "94.35"
    assert cobranca.descricao == f"Orgânicos Méier — pedido {x.pk}"
    assert cobranca.expira_em == PRAZO
    assert gravada.situacao == "criada"
    assert gravada.id_externo == cobranca.id_externo
    assert gravada.dados_para_pagar["pix_copia_e_cola"].startswith("SIMULADO-")
    assert gravada.criada_em == T0 + timedelta(hours=1)
    (pagamento,) = PagamentoNoProvedor.objects.all()
    assert (pagamento.id_externo, pagamento.situacao) == (cobranca.id_externo, "pendente")
    (chamada,) = _chamadas("criar_cobranca")
    assert chamada.situacao == SituacaoDaChamada.CONCLUIDA


def test_com_tentativa_aberta_devolve_a_mesma(cenario: tuple[Arranjo, Pedido, Any]) -> None:
    # A-3
    arranjo, x, _ = cenario
    primeira = _criada(arranjo, x)
    de_novo = pedir_pagamento(arranjo.a, x)
    assert de_novo.pk == primeira.pk
    assert len(_tentativas(x)) == 1
    assert len(_chamadas("criar_cobranca")) == 1


def test_solicitada_conta_como_aberta(cenario: tuple[Arranjo, Pedido, Any]) -> None:  # A-3
    arranjo, x, _ = cenario
    primeira = pedir_pagamento(arranjo.a, x)
    segunda = pedir_pagamento(arranjo.a, x)
    assert segunda.pk == primeira.pk
    assert len(_chamadas("criar_cobranca")) == 1


def test_apos_expirar_uma_nova_tentativa_e_permitida(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-4
    arranjo, x, sim = cenario
    primeira = _criada(arranjo, x)
    assert primeira.id_externo is not None
    sim.expirar(primeira.id_externo)
    with transaction.atomic():
        agendar_chamada("consultar_pagamento", primeira.id_externo)
    assert processar_chamadas() == 1
    assert PagamentoNoProvedor.objects.get().situacao == "expirado"
    segunda = pedir_pagamento(arranjo.a, x)
    assert segunda.pk != primeira.pk
    assert (segunda.numero, segunda.situacao) == (2, "solicitada")
    assert segunda.chave_idempotencia == f"om-p{x.pk}-t2"
    assert segunda.referencia_externa == primeira.referencia_externa
    assert len(_chamadas("criar_cobranca")) == 2


@pytest.mark.acceptance
def test_fronteira_de_24_horas_para_pedir_pagamento(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-5, T-1
    arranjo, x, _ = cenario
    relogio.congelar(PRAZO - MS)
    pedir_pagamento(arranjo.a, x)
    assert len(_tentativas(x)) == 1
    assert len(_chamadas("criar_cobranca")) == 1
    for instante in (PRAZO, PRAZO + MS):
        relogio.congelar(instante)
        with pytest.raises(PagamentoRecusado) as erro:
            pedir_pagamento(arranjo.a, x)
        assert erro.value.codigo == "prazo_encerrado"
        assert str(erro.value) == (
            "O prazo para pagar este pedido terminou em 03/11/2026 às 10:00 (horário de Brasília)."
        )
    assert len(_tentativas(x)) == 1
    assert len(_chamadas("criar_cobranca")) == 1


def test_tarefa_depois_do_prazo_nao_cria_cobranca(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado, client: Any
) -> None:  # A-6
    arranjo, x, _ = cenario
    relogio.congelar(PRAZO - MS)
    pedir_pagamento(arranjo.a, x)
    relogio.congelar(PRAZO)
    assert processar_chamadas() == 1
    (chamada,) = _chamadas("criar_cobranca")
    assert chamada.situacao == SituacaoDaChamada.FALHOU
    assert chamada.ultimo_erro == "prazo_encerrado"
    assert chamada.concluida_em == PRAZO
    tentativa = _unica(x)
    assert (tentativa.situacao, tentativa.codigo_da_falha) == ("nao_criada", "prazo_encerrado")
    assert CobrancaSimulada.objects.count() == 0
    client.force_login(arranjo.a)
    pagina = client.get(f"/pedidos/{x.pk}/").content.decode()
    assert "Não foi possível gerar a cobrança antes do fim do prazo." in pagina


@pytest.mark.parametrize("estado", ["pago", "cancelado", "suspenso", "de_outro"])
def test_recusas_do_pedido_e_da_conta(
    cenario: tuple[Arranjo, Pedido, Any], estado: str
) -> None:  # A-7
    arranjo, x, _ = cenario
    comprador = arranjo.a
    if estado == "pago":
        marcar_pago(x)
        esperado = ("pedido_pago", "Este pedido já está pago.")
    elif estado == "cancelado":
        cancelar_direto(x)
        esperado = ("pedido_cancelado", "Este pedido foi cancelado e não pode mais ser pago.")
    elif estado == "suspenso":
        type(comprador).objects.filter(pk=comprador.pk).update(situacao=Situacao.SUSPENSA)
        comprador.refresh_from_db()
        esperado = ("conta_inativa", "Sua conta não pode fazer pagamentos no momento.")
    else:
        comprador = arranjo.b
        esperado = ("nao_e_seu", "")
    with pytest.raises(PagamentoRecusado) as erro:
        pedir_pagamento(comprador, x)
    assert erro.value.codigo == esperado[0]
    if esperado[1]:
        assert str(erro.value) == esperado[1]
    assert _tentativas(x) == []
    assert _chamadas("criar_cobranca") == []
    assert not EntradaAuditoria.objects.filter(acao="pedido.pedir_pagamento").exists()


def test_provedor_fora_do_ar_repete_com_a_mesma_chave(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-8
    arranjo, x, sim = cenario
    pedir_pagamento(arranjo.a, x)
    sim.indisponivel()
    assert processar_chamadas() == 1
    (chamada,) = _chamadas("criar_cobranca")
    assert chamada.situacao == SituacaoDaChamada.PENDENTE
    assert _unica(x).situacao == "solicitada"
    sim.normalizar()
    relogio.congelar(T0 + timedelta(hours=1) + MIN)
    assert processar_chamadas() == 1
    assert _unica(x).situacao == "criada"
    (cobranca,) = CobrancaSimulada.objects.all()
    assert cobranca.chave_idempotencia == f"om-p{x.pk}-t1"


def test_falha_depois_de_o_provedor_criar_devolve_a_mesma_cobranca(
    cenario: tuple[Arranjo, Pedido, Any], relogio: RelogioControlado
) -> None:  # A-9, E07-R03
    arranjo, x, sim = cenario
    pedir_pagamento(arranjo.a, x)
    sim.falhar_proximas(1, operacao="criar_cobranca", depois_de_executar=True)
    assert processar_chamadas() == 1
    assert _unica(x).situacao == "solicitada"
    assert CobrancaSimulada.objects.count() == 1
    relogio.congelar(T0 + timedelta(hours=1) + MIN)
    assert processar_chamadas() == 1
    (cobranca,) = CobrancaSimulada.objects.all()
    tentativa = _unica(x)
    assert (tentativa.situacao, tentativa.id_externo) == ("criada", cobranca.id_externo)


def test_agendar_cancelamento_uma_vez_por_motivo(
    cenario: tuple[Arranjo, Pedido, Any],
) -> None:  # A-10
    arranjo, x, _ = cenario
    tentativa = _criada(arranjo, x)
    with transaction.atomic():
        primeira = agendar_cancelamento(tentativa, "prazo")
        segunda = agendar_cancelamento(tentativa, "prazo")
    assert primeira is not None
    assert segunda is not None
    assert primeira.pk == segunda.pk
    (chamada,) = _chamadas("cancelar_cobranca")
    assert chamada.alvo == f"t{tentativa.pk}:prazo"
    assert chamada.parametros == {"id_externo": tentativa.id_externo}
    assert processar_chamadas() == 1
    assert CobrancaSimulada.objects.get().situacao == "cancelado"
    assert PagamentoNoProvedor.objects.get().situacao == "cancelado"
    with transaction.atomic():
        assert agendar_cancelamento(tentativa, "prazo") is None
    assert len(_chamadas("cancelar_cobranca")) == 1


def test_so_tentativa_criada_tem_cancelamento(cenario: tuple[Arranjo, Pedido, Any]) -> None:
    # A-10 (negativo)
    arranjo, x, _ = cenario
    solicitada = pedir_pagamento(arranjo.a, x)
    with transaction.atomic():
        assert agendar_cancelamento(solicitada, "suspensao") is None
    assert _chamadas("cancelar_cobranca") == []


@pytest.mark.django_db(transaction=True)
def test_agendar_cancelamento_exige_transacao(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-10 (regra)
    arranjo, x = pedido_aberto(relogio)
    tentativa = _criada(arranjo, x)
    assert not connection.in_atomic_block
    with pytest.raises(TransactionManagementError):
        agendar_cancelamento(tentativa, "prazo")
    assert _chamadas("cancelar_cobranca") == []


@pytest.mark.acceptance
def test_aprovacao_no_instante_do_cancelamento_vale_o_que_o_provedor_registrou(
    cenario: tuple[Arranjo, Pedido, Any],
) -> None:  # A-11, infraestrutura 4.3, L-2
    arranjo, x, sim = cenario
    tentativa = _criada(arranjo, x)
    assert tentativa.id_externo is not None
    sim.aprovar_no_cancelamento(tentativa.id_externo)
    with transaction.atomic():
        agendar_cancelamento(tentativa, "prazo")
    assert processar_chamadas() == 1
    pagamento = PagamentoNoProvedor.objects.get()
    assert pagamento.situacao == "aprovado"
    assert pagamento.aprovado_no_provedor_em == T0 + timedelta(hours=1)
    assert CobrancaSimulada.objects.get().situacao == "aprovado"


def test_falha_definitiva_encerra_a_chamada_sem_repetir() -> None:  # A-12
    vistos: list[str] = []

    def executar(provedor: Any, chamada: ChamadaAoProvedor) -> Any:
        raise FalhaDefinitiva("x")

    def concluir(chamada: ChamadaAoProvedor, resultado: Any) -> None:
        raise AssertionError("não deve concluir")

    def falhou(chamada: ChamadaAoProvedor, erro: Exception) -> None:
        vistos.append(getattr(erro, "codigo", ""))

    registrar_operacao("falha_definitiva_de_teste", Operacao(executar, concluir, falhou))
    try:
        with transaction.atomic():
            agendar_chamada("falha_definitiva_de_teste", "alvo")
        assert processar_chamadas() == 1
        chamada = ChamadaAoProvedor.objects.get()
        assert chamada.situacao == SituacaoDaChamada.FALHOU
        assert chamada.ultimo_erro == "x"
        assert chamada.concluida_em is not None
        assert chamada.tentativas == 1
        assert vistos == ["x"]
        assert processar_chamadas() == 0
        assert vistos == ["x"]
    finally:
        OPERACOES.pop("falha_definitiva_de_teste", None)


def _jobs() -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM procrastinate_jobs "
            "WHERE task_name = 'processar_chamadas_ao_provedor' AND status = 'todo'"
        )
        (total,) = cursor.fetchone()
    return int(total)


def test_disparo_imediato_depois_do_commit(
    cenario: tuple[Arranjo, Pedido, Any], django_capture_on_commit_callbacks: Any
) -> None:  # A-13
    arranjo, x, _ = cenario
    y = Pedido.objects.get(comprador=arranjo.b)

    class Desfeita(Exception):
        pass

    with django_capture_on_commit_callbacks(execute=True) as desfeitos:
        try:
            with transaction.atomic():
                pedir_pagamento(arranjo.a, x)
                raise Desfeita
        except Desfeita:
            pass
    assert desfeitos == []
    assert _jobs() == 0
    with django_capture_on_commit_callbacks(execute=True) as primeiro:
        pedir_pagamento(arranjo.a, x)
    assert len(primeiro) == 1
    assert _jobs() == 1
    with django_capture_on_commit_callbacks(execute=True) as segundo:
        pedir_pagamento(arranjo.b, y)  # a tarefa já está na fila: a recusa é ignorada
    assert len(segundo) == 1
    assert _jobs() == 1


def test_log_e_auditoria_nao_levam_dados_do_pagador(
    cenario: tuple[Arranjo, Pedido, Any],
    relogio: RelogioControlado,
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-18
    caplog.set_level(logging.DEBUG)
    arranjo, x, sim = cenario
    tentativa = _criada(arranjo, x)
    assert tentativa.id_externo is not None
    with transaction.atomic():
        agendar_chamada("consultar_pagamento", tentativa.id_externo)
        agendar_cancelamento(tentativa, "prazo")
    processar_chamadas()
    sim.indisponivel()
    relogio.congelar(T0 + timedelta(hours=1) + MIN)
    pedir_pagamento(arranjo.b, Pedido.objects.get(comprador=arranjo.b))
    processar_chamadas()
    textos = [caplog.text]
    textos += [
        str(e.alteracoes)
        for e in EntradaAuditoria.objects.filter(
            Q(acao__startswith="pedido.") | Q(acao__startswith="pagamento.")
        )
    ]
    for texto in textos:
        for proibido in ("SIMULADO-", arranjo.a.email_normalizado, arranjo.a.nome):
            assert proibido not in texto
    assert "SIMULADO-" in str(TentativaDePagamento.objects.get(pk=tentativa.pk).dados_para_pagar)
    assert SituacaoDoPedido.objects.count() == 2


def _nova(x: Pedido, **campos: Any) -> TentativaDePagamento:
    base: dict[str, Any] = {
        "pedido": x,
        "numero": 1,
        "chave_idempotencia": f"om-p{x.pk}-t1",
        "referencia_externa": x.referencia_externa,
        "situacao": "nao_criada",
        "codigo_da_falha": "x",
    }
    return TentativaDePagamento.objects.create(**{**base, **campos})


def test_o_banco_recusa_tentativa_incoerente(cenario: tuple[Arranjo, Pedido, Any]) -> None:
    _, x, _ = cenario
    _nova(x, situacao="solicitada", codigo_da_falha="")
    recusas: list[dict[str, Any]] = [
        {"numero": 2, "chave_idempotencia": "outra-a", "situacao": "solicitada"},  # 2ª aberta
        {"chave_idempotencia": "outra-b"},  # mesmo número
        {"numero": 3},  # mesma chave
        {"numero": 4, "chave_idempotencia": "outra-c", "situacao": "criada", "codigo_da_falha": ""},
        {"numero": 5, "chave_idempotencia": "outra-d", "codigo_da_falha": ""},
    ]
    for campos in recusas:
        with pytest.raises(DatabaseError), transaction.atomic():
            _nova(x, **campos)
    _nova(
        x,
        numero=6,
        chave_idempotencia="ok-1",
        situacao="criada",
        id_externo="sim-77",
        codigo_da_falha="",
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        _nova(
            x,
            numero=7,
            chave_idempotencia="ok-2",
            situacao="criada",
            id_externo="sim-77",
            codigo_da_falha="",
        )
    assert TentativaDePagamento.objects.filter(pedido=x).count() == 2
