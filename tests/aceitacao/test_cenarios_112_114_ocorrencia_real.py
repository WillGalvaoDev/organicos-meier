"""Cenários 112, 113 e 114 (§16), pela ocorrência real (E16-07 regra 2-J): um item de 1,000 kg a
R$ 7,99/kg (subtotal 7,99, serviço 0,40 e frete 1,60), no pedido formal e apurado. O
administrador registra a ocorrência de 0,25 kg, que reembolsa 2,00 de produtos pelo valor
registrado; o preço do catálogo muda para R$ 9,99/kg depois e o reembolso não muda (C112). O
cancelamento da rodada com reembolso devolve para o item exatamente o saldo, 5,99 (C114)."""

from decimal import Decimal
from typing import Any

import pytest

from apps.catalogo.models import Unidade
from apps.catalogo.servicos import editar_produto
from apps.financeiro.models import ItemReembolsado, ObrigacaoComComprador, Reembolso
from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
from apps.pedidos.models import OcorrenciaDeEntrega
from tests.apoio.entrega import arranjo_unico, item_de, ocorrer
from tests.conftest import RelogioControlado

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _arranjo(relogio: RelogioControlado, sim: Any) -> tuple[Any, Any, Any]:
    a, pedido, _pf = arranjo_unico(
        relogio,
        sim,
        preco="7.99",
        quantidade="1.000",
        frete="1.60",
        minimo="1.00",
        unidade=Unidade.KG,
        incremento="0.25",
    )
    return a, pedido, item_de(pedido, a.p1)


def test_cenario_112_a_ocorrencia_de_0_25_kg_usa_o_valor_registrado(
    relogio: RelogioControlado, sim: Any
) -> None:
    a, _pedido, item = _arranjo(relogio, sim)
    assert (item.unidade, item.quantidade, item.preco_unitario) == (
        Unidade.KG,
        D("1.000"),
        D("7.99"),
    )
    assert item.subtotal == D("7.99")
    resultado = ocorrer(a.admin, item, D("0.25"), "faltante")
    registrado = resultado.reembolso.reembolso
    assert registrado.produtos == D("2.00")
    (ocorrencia,) = OcorrenciaDeEntrega.objects.all()
    assert (ocorrencia.item_id, ocorrencia.quantidade) == (item.pk, D("0.250"))
    editar_produto(a.admin, a.p1, preco="9.99")
    a.p1.refresh_from_db()
    assert a.p1.preco == D("9.99")
    registrado.refresh_from_db()
    assert registrado.produtos == D("2.00")
    (linha,) = registrado.itens.all()
    assert (linha.quantidade, linha.valor) == (D("0.250"), D("2.00"))


def test_cenario_113_quatro_ocorrencias_de_0_25_kg_somam_o_subtotal(
    relogio: RelogioControlado, sim: Any
) -> None:
    a, _pedido, item = _arranjo(relogio, sim)
    produtos = [
        ocorrer(a.admin, item, D("0.25"), "faltante").reembolso.reembolso.produtos for _ in range(4)
    ]
    assert produtos == [D("2.00"), D("2.00"), D("2.00"), D("1.99")]
    assert sum(produtos, D("0.00")) == D("7.99")
    assert OcorrenciaDeEntrega.objects.count() == 4


def test_cenario_114_o_cancelamento_depois_da_parcial_devolve_o_saldo_do_item(
    relogio: RelogioControlado, sim: Any
) -> None:
    a, pedido, item = _arranjo(relogio, sim)
    parcial = ocorrer(a.admin, item, D("0.25"), "faltante").reembolso.reembolso
    assert (parcial.produtos, parcial.servico, parcial.frete) == (D("2.00"), D("0.10"), D("0.40"))
    cancelar_rodada(a.admin, a.rodada, com_reembolso=True)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=pedido, motivo="cancelamento_da_rodada")
    do_cancelamento = Reembolso.objects.get(pedido=pedido, motivo="cancelamento_da_rodada")
    (linha,) = do_cancelamento.itens.filter(item=item)
    assert (linha.quantidade, linha.valor) == (D("0.750"), D("5.99"))
    assert do_cancelamento.produtos == D("5.99")
    assert sum((i.valor for i in ItemReembolsado.objects.filter(item=item)), D("0.00")) == D("7.99")
    assert OcorrenciaDeEntrega.objects.count() == 1
    assert (do_cancelamento.produtos, do_cancelamento.servico, do_cancelamento.frete) == (
        D("5.99"),
        D("0.30"),
        D("1.20"),
    )
    assert obrigacao.devido == D("7.49")
    assert parcial.produtos + do_cancelamento.produtos == pedido.produtos
