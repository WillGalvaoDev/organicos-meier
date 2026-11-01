"""E12-06: o que o comprador vê da rodada cancelada (acceptance A-14 a A-17 e A-19)."""

import re
from typing import Any

import pytest
from django.test import Client

from tests.apoio.apuracao import arranjo_ap, pagar
from tests.apoio.cancelamento import Ci
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _como(conta: Any) -> Client:
    cliente = Client()
    cliente.force_login(conta)
    return cliente


def _cancelada(relogio: RelogioControlado, sim: Any, **cancelamento: Any) -> tuple[Any, Any, Any]:
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    cancelar_rodada(a.admin, a.rodada, **cancelamento)
    return a, x, y


def test_pedido_pago_com_reembolso(relogio: RelogioControlado, sim: Any) -> None:  # A-14
    a, x, _y = _cancelada(relogio, sim, com_reembolso=True, mensagem="Fornecedor sem colheita")
    texto = _texto(_como(a.a).get(f"/pedidos/{x.pk}/"))
    assert (
        "A rodada foi cancelada pelo administrador. O valor será devolvido integralmente." in texto
    )
    assert "Fornecedor sem colheita" in texto
    assert "Estornos" in texto
    assert "Cancelamento da rodada" in texto
    assert "Estorno solicitado à plataforma de pagamento" in texto
    assert "Pagar" not in texto


def test_pedido_cancelado_pela_rodada(relogio: RelogioControlado, sim: Any) -> None:  # A-15
    a, _x, y = _cancelada(relogio, sim, com_reembolso=True)
    texto = _texto(_como(a.b).get(f"/pedidos/{y.pk}/"))
    assert "Cancelado (rodada cancelada)" in texto
    assert "Nada foi cobrado neste pedido." in texto
    assert "Pagar" not in texto


def test_pedido_pago_sem_reembolso(relogio: RelogioControlado, sim: Any) -> None:  # A-16
    a, x, _y = _cancelada(relogio, sim, com_reembolso=False)
    texto = _texto(_como(a.a).get(f"/pedidos/{x.pk}/"))
    assert "A rodada foi cancelada pelo administrador." in texto
    assert "O cancelamento não inicia novas devoluções." in texto
    assert "será devolvido integralmente" not in texto


def test_outro_comprador_nao_ve_o_pedido(relogio: RelogioControlado, sim: Any) -> None:  # A-17
    a, x, _y = _cancelada(relogio, sim, com_reembolso=True)
    assert _como(a.b).get(f"/pedidos/{x.pk}/").status_code == 404


def test_carrinho_sem_a_rodada_cancelada_e_com_o_pendente(relogio: RelogioControlado) -> None:
    # A-19
    ci = Ci()
    ci.cancelar(com_reembolso=False)
    texto = _texto(_como(ci.d).get("/carrinho/"))
    assert f"Rodada {ci.rodada.pk}" not in texto
    assert "Pendente: 3" in texto
    assert "Remover" in texto
