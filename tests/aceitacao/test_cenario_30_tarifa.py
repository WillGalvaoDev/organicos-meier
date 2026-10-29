"""Cenário 30 (E09-04, A-2): a tarifa do provedor é despesa, e não muda valor nenhum."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from apps.financeiro.livro import saldo
from apps.financeiro.models import Componente, Despesa, MovimentoFinanceiro, TipoDeMovimento
from apps.pedidos.models import ItemDoPedido, Pedido
from tests.apoio.financeiro import custodia, despesas, pedido_composto
from tests.apoio.pedidos import T0, sincronizar, tentativa_criada
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal


def _um(itens: Any) -> Any:
    achados = list(itens)
    assert len(achados) == 1, f"esperava 1 registro, há {len(achados)}"
    return achados[0]


def test_a_tarifa_e_registrada_como_despesa_e_nao_chega_ao_comprador(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    relogio.congelar(T0 + timedelta(hours=1))
    simulador_pagamentos.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    comprador = ContaFactory.create()
    pedido = pedido_composto(comprador)
    valores_do_pedido = Pedido.objects.filter(pk=pedido.pk).values().get()
    itens = list(ItemDoPedido.objects.filter(pedido=pedido).values())
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    simulador_pagamentos.aprovar(id_externo)
    sincronizar(id_externo)
    despesa = _um(Despesa.objects.all())
    assert (despesa.tipo, despesa.valor) == ("tarifa", D("1.25"))
    assert MovimentoFinanceiro.objects.filter(tipo=TipoDeMovimento.TARIFA).count() == 1
    assert saldo(despesas()) == D("-1.25")
    rodada, ciclo = pedido.abertura.rodada, pedido.abertura.ciclo
    assert [
        saldo(custodia(rodada, ciclo, comprador, componente))
        for componente in (Componente.PRODUTOS, Componente.SERVICO, Componente.FRETE)
    ] == [D("100.00"), D("5.00"), D("20.00")]
    assert Pedido.objects.filter(pk=pedido.pk).values().get() == valores_do_pedido
    assert list(ItemDoPedido.objects.filter(pedido=pedido).values()) == itens
