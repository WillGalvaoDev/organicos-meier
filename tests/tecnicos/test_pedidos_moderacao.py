"""E08-06: pedidos de comprador suspenso ou removido (acceptance A-1 a A-10)."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError
from django.test import Client

from apps.contas.models import Conta, Situacao
from apps.contas.moderacao import conta_suspensa, reativar, remover, suspender
from apps.interesses.models import ParcelaDeInteresse
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor, PagamentoNoProvedor
from apps.pedidos.cancelamento import cancelar_pedidos_nao_pagos
from apps.pedidos.models import (
    DestinoDoPagamento,
    ItemDoPedido,
    ParcelaNoPedido,
    Pedido,
    SituacaoDoPedido,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import pedir_pagamento
from apps.simulador_pagamentos.models import CobrancaSimulada
from tests.apoio.pedidos import (
    T0,
    Arranjo,
    cancelar_direto,
    marcar_pago,
    pedido_aberto,
    pedido_avulso,
    pedido_de,
    tentativa_criada,
)
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

H = timedelta(hours=1)
MIN = timedelta(minutes=1)


@dataclass
class Cenario:
    arranjo: Arranjo
    x: Pedido  # aguardando_pagamento, com a cobrança P pendente
    z: Pedido  # pago, em outro fornecedor
    sim: Any
    p: str


@pytest.fixture
def cenario(relogio: RelogioControlado, simulador_pagamentos: Any) -> Cenario:
    arranjo, x = pedido_aberto(relogio)
    tentativa = tentativa_criada(x)
    z = pedido_avulso(arranjo.a, "G", "50.00")
    marcar_pago(z)
    relogio.congelar(T0 + 3 * H)
    assert tentativa.id_externo is not None
    return Cenario(arranjo, x, z, simulador_pagamentos, tentativa.id_externo)


def _situacao(pedido: Pedido) -> SituacaoDoPedido:
    return SituacaoDoPedido.objects.get(pedido=pedido)


def _chamadas() -> list[ChamadaAoProvedor]:
    return list(ChamadaAoProvedor.objects.filter(operacao="cancelar_cobranca").order_by("pk"))


def _composicao() -> tuple[Any, ...]:
    return (
        list(ItemDoPedido.objects.order_by("pk").values()),
        list(ParcelaNoPedido.objects.order_by("pk").values()),
        list(
            ParcelaDeInteresse.objects.order_by("pk").values(
                "id", "situacao", "quantidade_reservada", "quantidade_pendente"
            )
        ),
    )


def _avisos(conta: Conta) -> list[Notificacao]:
    return list(Notificacao.objects.filter(conta=conta, evento="pagamento_confirmado"))


@pytest.mark.acceptance
def test_suspensao_cancela_o_pedido_nao_pago(cenario: Cenario) -> None:
    # A-1, Spec §2, cenário 19 (pedidos)
    c = cenario
    antes = _composicao()
    suspender(c.arranjo.admin, c.arranjo.a)
    situacao = _situacao(c.x)
    assert situacao.situacao == "cancelado"
    assert situacao.cancelado_em == T0 + 3 * H
    assert situacao.motivo_do_cancelamento == "suspensao"
    assert _situacao(c.z).situacao == "pago"
    (chamada,) = _chamadas()
    assert chamada.alvo == f"t{c.x.tentativas.get().pk}:suspensao"
    (entrada,) = EntradaAuditoria.objects.filter(acao="pedido.cancelar")
    assert entrada.autor_tipo == "sistema"
    assert entrada.alteracoes == {
        "pedido": c.x.pk,
        "motivo": "suspensao",
        "cancelado_em": "2026-11-02T16:00:00+00:00",
    }
    assert _composicao() == antes


def test_a_cobranca_pendente_e_cancelada_no_provedor(cenario: Cenario) -> None:  # A-2
    c = cenario
    suspender(c.arranjo.admin, c.arranjo.a)
    assert processar_chamadas() == 1
    assert CobrancaSimulada.objects.get().situacao == "cancelado"
    assert PagamentoNoProvedor.objects.get(id_externo=c.p).situacao == "cancelado"
    assert _situacao(c.x).situacao == "cancelado"
    assert DestinoDoPagamento.objects.count() == 0


def test_remocao_da_conta_cancela_com_o_proprio_motivo(cenario: Cenario) -> None:  # A-3
    c = cenario
    remover(c.arranjo.admin, c.arranjo.a)
    situacao = _situacao(c.x)
    assert (situacao.situacao, situacao.motivo_do_cancelamento) == (
        "cancelado",
        "remocao_da_conta",
    )
    (chamada,) = _chamadas()
    assert chamada.alvo == f"t{c.x.tentativas.get().pk}:remocao_da_conta"
    assert _situacao(c.z).situacao == "pago"


def test_pago_no_provedor_antes_da_suspensao_quita_mesmo_assim(
    cenario: Cenario, relogio: RelogioControlado
) -> None:  # A-4, Spec §8.3
    c = cenario
    relogio.congelar(T0 + 2 * H + 30 * MIN)
    c.sim.aprovar(c.p)  # aprovado no provedor às 15:30, sem aviso entregue
    relogio.congelar(T0 + 3 * H)
    suspender(c.arranjo.admin, c.arranjo.a)
    relogio.congelar(T0 + 3 * H + 5 * MIN)
    c.sim.entregar_avisos()
    processar_chamadas()
    situacao = _situacao(c.x)
    assert situacao.situacao == "pago"
    (auditoria,) = EntradaAuditoria.objects.filter(acao="pedido.quitar")
    assert auditoria.alteracoes["cancelamento_sem_efeito"] == "suspensao"
    assert len(_avisos(c.arranjo.a)) == 1


def test_pago_no_provedor_depois_da_suspensao_gera_devolucao(
    cenario: Cenario, relogio: RelogioControlado
) -> None:  # A-5, Spec §8.3
    c = cenario
    suspender(c.arranjo.admin, c.arranjo.a)
    relogio.congelar(T0 + 3 * H + 10 * MIN)
    c.sim.aprovar(c.p, em=T0 + 3 * H + 10 * MIN)  # antes de o cancelamento ser processado
    c.sim.entregar_avisos()
    processar_chamadas()
    destino = DestinoDoPagamento.objects.get()
    assert (destino.destino, destino.motivo) == ("devolucao", "pedido_cancelado")
    assert _situacao(c.x).situacao == "cancelado"
    assert _avisos(c.arranjo.a) == []


def test_reativar_nao_restaura_o_pedido(cenario: Cenario) -> None:  # A-6
    c = cenario
    suspender(c.arranjo.admin, c.arranjo.a)
    reativar(c.arranjo.admin, c.arranjo.a)
    c.arranjo.a.refresh_from_db()
    assert c.arranjo.a.situacao == Situacao.ATIVA
    cliente = Client()
    cliente.force_login(c.arranjo.a)
    assert "Cancelado" in cliente.get(f"/pedidos/{c.x.pk}/").content.decode()
    resposta = cliente.post(f"/pedidos/{c.x.pk}/pagar/")
    assert resposta.status_code == 409
    assert "Este pedido foi cancelado e não pode mais ser pago." in resposta.content.decode()
    assert _situacao(c.x).situacao == "cancelado"


def test_o_suspenso_ve_o_cancelado_e_o_pago(cenario: Cenario) -> None:  # A-7
    c = cenario
    suspender(c.arranjo.admin, c.arranjo.a)
    cliente = Client()
    cliente.force_login(c.arranjo.a)
    html = cliente.get("/pedidos/").content.decode()
    assert "Cancelado" in html
    assert "Pago" in html
    for pedido in (c.x, c.z):
        pagina = cliente.get(f"/pedidos/{pedido.pk}/").content.decode()
        assert "Pagar com Pix" not in pagina


@pytest.mark.django_db(transaction=True)
def test_o_servico_exige_transacao(relogio: RelogioControlado, simulador_pagamentos: Any) -> None:
    # A-8 (parte 1)
    arranjo, _ = pedido_aberto(relogio)
    assert not connection.in_atomic_block
    with pytest.raises(TransactionManagementError):
        cancelar_pedidos_nao_pagos(arranjo.a, motivo="suspensao")
    assert not SituacaoDoPedido.objects.filter(situacao="cancelado").exists()


def test_motivo_invalido_e_conta_de_fornecedor(cenario: Cenario) -> None:  # A-8 (parte 2)
    c = cenario
    fornecedor = ContaFactory.create(fornecedor=True)
    with transaction.atomic():
        with pytest.raises(ValueError):  # noqa: PT011
            cancelar_pedidos_nao_pagos(c.arranjo.a, motivo="outro")
        assert cancelar_pedidos_nao_pagos(fornecedor, motivo="suspensao") == 0
    assert _situacao(c.x).situacao == "aguardando_pagamento"
    assert _chamadas() == []


def test_falha_de_outro_receptor_desfaz_a_suspensao(cenario: Cenario) -> None:  # A-9
    c = cenario

    def falha(sender: Any, **kwargs: Any) -> None:
        raise RuntimeError("falha de teste")

    conta_suspensa.connect(falha, weak=False, dispatch_uid="teste.moderacao")
    try:
        with pytest.raises(RuntimeError):
            suspender(c.arranjo.admin, c.arranjo.a)
    finally:
        conta_suspensa.disconnect(dispatch_uid="teste.moderacao")
    c.arranjo.a.refresh_from_db()
    assert c.arranjo.a.situacao == Situacao.ATIVA
    assert _situacao(c.x).situacao == "aguardando_pagamento"
    assert _chamadas() == []


def test_sem_pedidos_ou_com_pedido_cancelado_nada_muda(cenario: Cenario) -> None:  # A-10
    c = cenario
    y = pedido_de(c.arranjo.b)
    cancelar_direto(y, "suspensao", T0 + 2 * H)
    antes = list(SituacaoDoPedido.objects.filter(pedido=y).values())
    sem_pedidos = ContaFactory.create()
    with transaction.atomic():
        assert cancelar_pedidos_nao_pagos(sem_pedidos, motivo="suspensao") == 0
    suspender(c.arranjo.admin, sem_pedidos)
    suspender(c.arranjo.admin, c.arranjo.b)
    reativar(c.arranjo.admin, c.arranjo.b)
    suspender(c.arranjo.admin, c.arranjo.b)
    assert list(SituacaoDoPedido.objects.filter(pedido=y).values()) == antes
    assert EntradaAuditoria.objects.filter(acao="pedido.cancelar").count() == 0


# --- Correção E08-R02: a cobrança que estava só enfileirada (A-13 e A-15) --------------------


@pytest.mark.parametrize(
    ("moderar", "motivo"),
    [(suspender, "suspensao"), (remover, "remocao_da_conta")],
    ids=["suspensao", "remocao"],
)
def test_tentativa_so_solicitada_nao_deixa_cobranca_pendente(
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    caplog: pytest.LogCaptureFixture,
    moderar: Any,
    motivo: str,
) -> None:  # A-13, prova do parecer
    arranjo, x = pedido_aberto(relogio)
    tentativa = pedir_pagamento(arranjo.a, x)
    assert tentativa.situacao == "solicitada"
    moderar(arranjo.admin, arranjo.a)
    caplog.set_level(logging.INFO, logger="apps.simulador_pagamentos")
    processar_chamadas()
    processar_chamadas()
    situacao = _situacao(x)
    assert (situacao.situacao, situacao.motivo_do_cancelamento) == ("cancelado", motivo)
    tentativa.refresh_from_db()
    assert (tentativa.situacao, tentativa.codigo_da_falha) == ("nao_criada", "pedido_cancelado")
    assert not CobrancaSimulada.objects.filter(situacao="pendente").exists()
    assert not any("criar_cobranca" in r.getMessage() for r in caplog.records)


def test_reativar_depois_da_criacao_recusada_nao_reabre_o_pedido(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-15 (estado do A-13; a variante concorrente fecha o A-14)
    arranjo, x = pedido_aberto(relogio)
    pedir_pagamento(arranjo.a, x)
    suspender(arranjo.admin, arranjo.a)
    processar_chamadas()
    reativar(arranjo.admin, arranjo.a)
    cliente = Client()
    cliente.force_login(arranjo.a)
    resposta = cliente.post(f"/pedidos/{x.pk}/pagar/")
    assert resposta.status_code == 409
    assert "Este pedido foi cancelado e não pode mais ser pago." in resposta.content.decode()
    assert TentativaDePagamento.objects.filter(pedido=x).count() == 1
    assert CobrancaSimulada.objects.count() == 0
