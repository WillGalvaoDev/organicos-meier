"""T-40 da infraestrutura: reembolso do item inteiro depois de mudar o preço no catálogo (E16-07).

O reembolso usa o subtotal registrado no pedido congelado, não o preço atual do produto. Teste de
caracterização: o comportamento já existia (E10-02), então passou na primeira execução.
"""

from decimal import Decimal

import pytest

from apps.financeiro.models import ItemReembolsado
from tests.apoio.devolucoes import K, componentes, parcial, pedido_pago_com_itens
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal


def test_t40_reembolso_do_item_inteiro_depois_de_mudar_o_preco(
    relogio: RelogioControlado,
) -> None:
    _, (item,) = pedido_pago_com_itens(K)  # 1,000 kg a R$ 7,99, subtotal registrado de R$ 7,99
    item.produto.preco = D("9.99")
    item.produto.save()
    registrado = parcial(item, "1")  # a quantidade inteira do item
    assert componentes(registrado) == (D("7.99"), D("0.40"), D("1.60"))
    assert componentes(registrado)[0] != D("9.99") * item.quantidade
    (linha,) = ItemReembolsado.objects.filter(reembolso=registrado.reembolso)
    assert (linha.item_id, linha.quantidade, linha.valor) == (item.pk, D("1.000"), D("7.99"))
