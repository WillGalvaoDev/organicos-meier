"""Cenários 90, 91 e 112 a 117 da especificação funcional, no nível do serviço de reembolso
(E10-02): o serviço é chamado direto; cada etapa seguinte repete o cenário pelo seu fluxo real."""

from decimal import Decimal

import pytest

from apps.financeiro.models import Reembolso
from apps.financeiro.reembolsos import ReembolsoRecusado, acumulado_do_pedido
from apps.pedidos.models import ItemDoPedido
from tests.apoio.devolucoes import K, M, N, componentes, integral, parcial, pedido_pago_com_itens
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal


def test_cenario_112_parcial_usa_o_valor_registrado(relogio: RelogioControlado) -> None:
    _, (item,) = pedido_pago_com_itens(K)
    assert componentes(parcial(item, "0.25"))[0] == D("2.00")


def test_cenario_113_quatro_parciais_somam_o_pago(relogio: RelogioControlado) -> None:
    pedido, (item,) = pedido_pago_com_itens(K)
    produtos = [componentes(parcial(item, "0.25"))[0] for _ in range(4)]
    assert produtos == [D("2.00"), D("2.00"), D("2.00"), D("1.99")]
    assert acumulado_do_pedido(pedido) == (D("7.99"), D("0.40"), D("1.60"))


def test_cenario_114_integral_depois_do_parcial_completa_exatamente(
    relogio: RelogioControlado,
) -> None:
    pedido, (item,) = pedido_pago_com_itens(K)
    parcial(item, "0.25")
    integral(pedido)
    assert acumulado_do_pedido(pedido) == (D("7.99"), D("0.40"), D("1.60"))


def test_cenario_115_centavos_nao_passam_do_pago(relogio: RelogioControlado) -> None:
    _, (item,) = pedido_pago_com_itens(M)
    produtos = [componentes(parcial(item, "0.1"))[0] for _ in range(6)]
    assert sum(produtos, D("0.00")) == D("0.09")
    with pytest.raises(ReembolsoRecusado):
        parcial(item, "0.1")


def test_cenario_116_servico_e_frete_proporcionais(relogio: RelogioControlado) -> None:
    pedido, (i1, i2) = pedido_pago_com_itens(N)
    assert componentes(parcial(i2, "1")) == (D("25.00"), D("1.25"), D("5.00"))
    assert componentes(parcial(i1, "1")) == (D("25.00"), D("1.25"), D("5.00"))
    assert acumulado_do_pedido(pedido) == (D("50.00"), D("2.50"), D("10.00"))


def test_cenarios_90_e_91_integral_devolve_exatamente_o_cobrado(
    relogio: RelogioControlado,
) -> None:
    pedido, (_, i2) = pedido_pago_com_itens(N)
    parcial(i2, "1")
    integral(pedido)
    assert acumulado_do_pedido(pedido) == (D("100.00"), D("5.00"), D("20.00"))


def test_cenario_117_cada_devolucao_e_registrada_separadamente(relogio: RelogioControlado) -> None:
    pedido, (item,) = pedido_pago_com_itens(K)
    for _ in range(4):
        parcial(item, "0.25")
    assert Reembolso.objects.filter(pedido=pedido).count() == 4
    assert ItemDoPedido.objects.get(pk=item.pk).quantidade == D("1.000")
    assert ItemDoPedido.objects.get(pk=item.pk).subtotal == D("7.99")
