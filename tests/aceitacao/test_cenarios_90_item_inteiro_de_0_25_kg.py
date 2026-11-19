"""Cenário 90 (§16), inteiro: 0,25 kg a R$ 7,99/kg cobrados R$ 2,00; o preço do produto muda para
R$ 8,99/kg; uma ocorrência da quantidade inteira reembolsa R$ 2,00 de produtos mais serviço e frete
proporcionais sobre os valores registrados, sem recalcular com o preço atual (E16-07 regra 2-G)."""

from decimal import Decimal

import pytest

from apps.catalogo.models import Unidade
from apps.catalogo.servicos import editar_produto
from apps.pedidos.models import ItemDoPedido
from tests.apoio.devolucoes import componentes, parcial
from tests.apoio.financeiro import pedido_composto
from tests.apoio.pedidos import administrador, marcar_pago
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, ProdutoFactory

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal


def test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado(
    relogio: RelogioControlado,
) -> None:
    pedido = pedido_composto(ContaFactory.create(), produtos="2.00", servico="0.10", frete="0.40")
    marcar_pago(pedido)
    produto = ProdutoFactory.create(
        fornecedor=pedido.abertura.rodada.fornecedor,
        unidade=Unidade.KG,
        incremento=D("0.25"),
        preco=D("7.99"),
    )
    item = ItemDoPedido.objects.create(
        pedido=pedido,
        produto=produto,
        nome=produto.nome,
        unidade=Unidade.KG,
        incremento=D("0.25"),
        preco_unitario=D("7.99"),
        quantidade=D("0.250"),
        subtotal=D("2.00"),
    )
    assert (item.unidade, item.quantidade, item.preco_unitario, item.subtotal) == (
        Unidade.KG,
        D("0.250"),
        D("7.99"),
        D("2.00"),
    )
    assert (pedido.produtos, pedido.servico, pedido.frete) == (D("2.00"), D("0.10"), D("0.40"))
    editar_produto(administrador(), produto, preco="8.99")
    produto.refresh_from_db()
    assert produto.preco == D("8.99")
    registrado = parcial(item, "0.25")
    assert componentes(registrado) == (D("2.00"), D("0.10"), D("0.40"))
    (linha,) = registrado.reembolso.itens.all()
    assert (linha.item_id, linha.quantidade, linha.valor) == (item.pk, D("0.250"), D("2.00"))
    assert ItemDoPedido.objects.get(pk=item.pk).preco_unitario == D("7.99")
