"""E12-05: aviso `rodada_cancelada` aos compradores (acceptance A-1 a A-7)."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction

from apps.financeiro.models import Reembolso
from apps.notificacoes.models import Envio, Notificacao
from apps.pedidos.models import Pedido
from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.cancelamento import Ci
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
EVENTO = "rodada_cancelada"
PRAZO = T0 + 48 * H


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _cancelar(a: Any, **kwargs: Any) -> Any:
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    return cancelar_rodada(a.admin, a.rodada, **kwargs)


def _aviso(conta: Any) -> Notificacao:
    return Notificacao.objects.get(conta=conta, evento=EVENTO)


def _avisos() -> list[Notificacao]:
    return list(Notificacao.objects.filter(evento=EVENTO).order_by("pk"))


def _x_pago_cancelado(
    relogio: RelogioControlado, sim: Any, **cancelamento: Any
) -> tuple[Any, Pedido, Pedido, Any]:
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    return a, x, y, _cancelar(a, **cancelamento)


def test_aviso_com_reembolso_e_mensagem(relogio: RelogioControlado, sim: Any) -> None:  # A-1
    a, x, _y, cancelamento = _x_pago_cancelado(
        relogio, sim, com_reembolso=True, mensagem="Fornecedor sem colheita"
    )
    nome = a.rodada.fornecedor.nome
    do_a = _aviso(a.a)
    assert do_a.titulo == f"Rodada cancelada: {nome}"
    assert f"A rodada de {nome} foi cancelada pelo administrador." in do_a.corpo
    assert "94,35" in do_a.corpo
    assert "devolvido integralmente" in do_a.corpo
    assert "Mensagem do administrador: Fornecedor sem colheita" in do_a.corpo
    assert do_a.link == f"/pedidos/{x.pk}/"
    assert do_a.chave == f"rodada_cancelada:{cancelamento.pk}:{a.a.pk}"
    do_b = _aviso(a.b)
    assert "Seu pedido foi cancelado e nada foi cobrado." in do_b.corpo
    assert "Reembolso integral para quem pagou." in do_b.corpo


def test_aviso_sem_reembolso_e_sem_mensagem(relogio: RelogioControlado, sim: Any) -> None:
    # A-2
    a, _x, _y, _c = _x_pago_cancelado(relogio, sim, com_reembolso=False)
    do_a = _aviso(a.a)
    assert (
        "O cancelamento não inicia novas devoluções. As devoluções já devidas continuam em "
        "andamento." in do_a.corpo
    )
    assert "devolvido integralmente" not in do_a.corpo
    assert "Mensagem do administrador" not in do_a.corpo
    assert "Sem novas devoluções." in _aviso(a.b).corpo


def test_destinatarios_pelo_efeito_do_cancelamento(relogio: RelogioControlado) -> None:  # A-3
    ci = Ci()
    ci.cancelar(com_reembolso=False)
    for comprador in (ci.a, ci.b, ci.d):
        aviso = _aviso(comprador)
        assert "Seus interesses nesta rodada foram removidos." in aviso.corpo
        assert aviso.link == "/carrinho/"
    fila = "Suas quantidades pendentes continuam na fila do fornecedor para as próximas rodadas."
    assert fila in _aviso(ci.d).corpo
    assert fila not in _aviso(ci.a).corpo
    assert not Notificacao.objects.filter(conta=ci.c, evento=EVENTO).exists()


def test_pedido_sem_saldo_novo_diz_que_as_devolucoes_continuam(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    from apps.interesses.servicos import adicionar_interesse
    from apps.pedidos.apuracao import iniciar_apuracao
    from apps.rodadas.fechamento import iniciar_fechamento
    from tests.fabricas import ContaFactory

    a, x, _y = arranjo_ap(relogio, minimo="100.00", limites=(11, 12))
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    adicionar_interesse(ContaFactory.create(nome="Comprador C"), a.p1, "5")
    iniciar_fechamento(a.admin, a.rodada)
    _cancelar(a, com_reembolso=True)
    assert not Reembolso.objects.filter(motivo="cancelamento_da_rodada").exists()
    corpo = _aviso(a.a).corpo
    assert "As devoluções já devidas do seu pedido continuam em andamento." in corpo
    assert "devolvido integralmente" not in corpo


def test_emitir_de_novo_com_a_mesma_chave_nao_duplica(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    from apps.pedidos import cancelamento_da_rodada as modulo

    a, _x, _y, cancelamento = _x_pago_cancelado(relogio, sim, com_reembolso=True)
    antes = len(_avisos())
    original = _aviso(a.a)
    with transaction.atomic():
        modulo._emitir_o_aviso(cancelamento, a.a, corpo=original.corpo, link=original.link or "")
    assert len(_avisos()) == antes == 2
    assert _aviso(a.a) == original


def test_o_aviso_nao_traz_dado_de_outro_comprador(relogio: RelogioControlado, sim: Any) -> None:
    # A-6
    from apps.catalogo.templatetags.catalogo import reais

    a, _x, _y, _c = _x_pago_cancelado(relogio, sim, com_reembolso=True)
    minimo = reais(a.rodada.fornecedor.minimo)
    do_a, do_b = _aviso(a.a).corpo, _aviso(a.b).corpo
    assert "Comprador B" not in do_a
    assert "106,15" not in do_a
    assert "Comprador A" not in do_b
    assert "94,35" not in do_b
    assert minimo not in do_a
    assert minimo not in do_b


def test_falha_do_email_nao_afeta_o_cancelamento_nem_o_aviso_no_site(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-7
    from apps.notificacoes.processamento import processar_envios
    from apps.rodadas.models import Rodada

    settings.EMAIL_BACKEND = "tests.apoio.email_falho.BackendQueFalha"
    a, x, _y, _c = _x_pago_cancelado(relogio, sim, com_reembolso=True)
    processar_envios()
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "cancelada"
    assert Reembolso.objects.filter(pedido=x, motivo="cancelamento_da_rodada").count() == 1
    aviso = _aviso(a.a)
    envio = Envio.objects.get(notificacao=aviso, canal="email")
    assert envio.situacao != "enviado"
    assert envio.tentativas >= 1
