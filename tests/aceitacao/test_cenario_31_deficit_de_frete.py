"""Cenário 31 (E09-06, A-3 e A-4): o déficit de frete é do administrador, e nunca do comprador."""

from decimal import Decimal
from typing import Any

import pytest
from apps.financeiro.apuracao import cobrir_despesa, frete_do_ciclo, registrar_apuracao_no_livro

from apps.financeiro.livro import EXTERIOR, saldo
from apps.financeiro.models import Despesa, TipoDeMovimento
from apps.nucleo.auditoria import SISTEMA
from apps.pedidos.models import Pedido
from tests.apoio.financeiro import frete_de, montar_ap, mover, pagar_pedido, receita_de, reserva
from tests.conftest import RelogioControlado

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal


def test_o_deficit_aparece_na_apuracao_e_o_administrador_o_cobre(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    from datetime import timedelta

    simulador_pagamentos.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    ap = montar_ap()
    pagar_pedido(ap, ap.x, simulador_pagamentos, relogio, timedelta(hours=1))
    mover(TipoDeMovimento.APORTE, EXTERIOR, reserva(), "1000.00", autor=ap.admin, justificativa="A")
    valores_cobrados = list(Pedido.objects.order_by("pk").values("produtos", "servico", "frete"))
    registrar_apuracao_no_livro(ap.ciclo, [ap.x], autor=SISTEMA)
    relatorio = frete_do_ciclo(ap.ciclo)
    assert (relatorio.efetivo, relatorio.arrecadado, relatorio.deficit) == (
        D("30.00"),
        D("20.00"),
        D("10.00"),
    )
    deficit = Despesa.objects.get(tipo="deficit_frete", ciclo=ap.ciclo)
    cobrir_despesa(
        ap.admin, deficit, fonte=("receita", ap.rodada), valor=D("3.75"), justificativa="r"
    )
    cobrir_despesa(ap.admin, deficit, fonte="reserva", valor=D("6.25"), justificativa="reserva")
    assert saldo(frete_de(ap.rodada)) == D("30.00")
    assert saldo(receita_de(ap.rodada)) == D("0.00")
    assert saldo(reserva()) == D("993.75")
    assert frete_do_ciclo(ap.ciclo).deficit_coberto == D("10.00")
    assert list(Pedido.objects.order_by("pk").values("produtos", "servico", "frete")) == (
        valores_cobrados
    )
