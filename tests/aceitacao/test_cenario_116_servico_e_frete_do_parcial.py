"""Cenário 116 da especificação funcional, com os números do cenário (E16-07, lacuna).

Pedido de R$ 100,00 de produtos, R$ 5,00 de serviço e R$ 20,00 de frete: um reembolso parcial de
R$ 2,00 de produtos devolve também R$ 0,10 de serviço e R$ 0,40 de frete, e o acumulado de cada
componente nunca passa do valor registrado. Teste de caracterização: o comportamento já existia
(E10-02), então ele passou na primeira execução.
"""

from decimal import Decimal

import pytest

from apps.financeiro.reembolsos import acumulado_do_pedido
from tests.apoio.devolucoes import Item, componentes, integral, parcial, pedido_pago_com_itens
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
# R$ 100,00 de produtos em 50 unidades de R$ 2,00; serviço de R$ 5,00 e frete de R$ 20,00
PEDIDO_DO_CENARIO = ("100.00", "5.00", "20.00", [Item("100.00", "50", "1")])


def test_cenario_116_numeros_do_cenario(relogio: RelogioControlado) -> None:
    pedido, (item,) = pedido_pago_com_itens(PEDIDO_DO_CENARIO)
    assert componentes(parcial(item, "1")) == (D("2.00"), D("0.10"), D("0.40"))
    assert acumulado_do_pedido(pedido) == (D("2.00"), D("0.10"), D("0.40"))
    integral(pedido)
    # depois da devolução integral do restante, o acumulado é exatamente o registrado
    assert acumulado_do_pedido(pedido) == (D("100.00"), D("5.00"), D("20.00"))
