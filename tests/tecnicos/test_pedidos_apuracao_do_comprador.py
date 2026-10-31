"""E11-07: o que o comprador vê da apuração (acceptance A-13 a A-16)."""

import re
from typing import Any

import pytest
from django.test import Client

from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

PRAZO = T0 + 48 * H


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _como(conta: Any) -> Client:
    cliente = Client()
    cliente.force_login(conta)
    return cliente


def _apurada(relogio: RelogioControlado, sim: Any, **arranjo: Any) -> tuple[Any, Any, Any]:
    from apps.pedidos.apuracao import iniciar_apuracao

    a, x, y = arranjo_ap(relogio, **arranjo)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    return a, x, y


def test_pedido_cancelado_por_falta_de_pagamento(relogio: RelogioControlado, sim: Any) -> None:
    # A-13
    a, _x, y = _apurada(relogio, sim)
    resposta = _como(a.b).get(f"/pedidos/{y.pk}/")
    texto = _texto(resposta)
    assert "Cancelado por falta de pagamento" in texto
    assert "Nada foi cobrado neste pedido" in texto
    assert "O pagamento não foi identificado até o fim do prazo" in texto


def test_unidades_em_caixa_incompleta_com_o_estorno_e_a_fila(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-14
    a, x, _y = _apurada(relogio, sim)
    cliente = _como(a.a)
    texto = _texto(cliente.get(f"/pedidos/{x.pk}/"))
    assert "4 un em caixa que ficou incompleta" in texto
    assert "estorno proporcional e unidades na fila de pendentes do fornecedor" in texto
    assert "R$ 23,59" in texto
    assert "Caixa incompleta" in texto
    carrinho = _texto(cliente.get("/carrinho/"))
    assert "Pendente: 4" in carrinho


def test_pedido_pago_de_rodada_que_voltou_para_interesse(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-15
    a, x, _y = _apurada(relogio, sim, minimo="100.00")
    texto = _texto(_como(a.a).get(f"/pedidos/{x.pk}/"))
    assert "A rodada voltou para interesse. O valor pago será devolvido integralmente" in texto
    assert "seus interesses continuam reservados na rodada" in texto


def test_o_comprador_nao_ve_dados_de_outro_nem_o_minimo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-16
    a, x, y = _apurada(relogio, sim)
    cliente = _como(a.a)
    texto = _texto(cliente.get(f"/pedidos/{x.pk}/"))
    assert "Comprador B" not in texto
    assert "50,00" not in texto
    assert cliente.get(f"/pedidos/{y.pk}/").status_code == 404
