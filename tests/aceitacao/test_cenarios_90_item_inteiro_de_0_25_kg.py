"""Cenário 90 (§16), inteiro, pela ocorrência real: um item de 0,25 kg a R$ 7,99/kg cobrado R$ 2,00
(com serviço de R$ 0,10 e frete de R$ 0,40); o preço do produto muda para R$ 8,99/kg; o
administrador registra a ocorrência da quantidade inteira e o reembolso devolve R$ 2,00 de
produtos, R$ 0,10 de serviço e R$ 0,40 de frete, sobre os valores registrados (E16-07 regra 2-J)."""

from decimal import Decimal
from typing import Any

import pytest

from apps.catalogo.models import Unidade
from apps.catalogo.servicos import editar_produto
from apps.pedidos.models import ItemDoPedido, OcorrenciaDeEntrega
from tests.apoio.entrega import arranjo_unico, item_de, ocorrer
from tests.conftest import RelogioControlado

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado(
    relogio: RelogioControlado, sim: Any
) -> None:
    a, pedido, _pf = arranjo_unico(
        relogio,
        sim,
        preco="7.99",
        quantidade="0.25",
        frete="0.40",
        minimo="1.00",
        unidade=Unidade.KG,
        incremento="0.25",
    )
    item = item_de(pedido, a.p1)
    assert (item.unidade, item.quantidade, item.preco_unitario, item.subtotal) == (
        Unidade.KG,
        D("0.250"),
        D("7.99"),
        D("2.00"),
    )
    assert (pedido.produtos, pedido.servico, pedido.frete) == (D("2.00"), D("0.10"), D("0.40"))
    editar_produto(a.admin, a.p1, preco="8.99")
    a.p1.refresh_from_db()
    assert a.p1.preco == D("8.99")
    resultado = ocorrer(a.admin, item, D("0.25"), "faltante")
    reembolso = resultado.reembolso.reembolso
    assert (reembolso.produtos, reembolso.servico, reembolso.frete) == (
        D("2.00"),
        D("0.10"),
        D("0.40"),
    )
    (linha,) = reembolso.itens.all()
    assert (linha.item_id, linha.quantidade, linha.valor) == (item.pk, D("0.250"), D("2.00"))
    (ocorrencia,) = OcorrenciaDeEntrega.objects.all()
    assert (ocorrencia.item_id, ocorrencia.quantidade, ocorrencia.reembolso_id) == (
        item.pk,
        D("0.250"),
        reembolso.pk,
    )
    assert ItemDoPedido.objects.get(pk=item.pk).preco_unitario == D("7.99")
