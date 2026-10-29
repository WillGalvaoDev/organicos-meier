"""Cenário 40 (E09-07, A-2 e A-3, no nível do livro-razão): o repasse sai só do liberado."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from apps.financeiro.liquidez import LiquidezInsuficiente, registrar_saida
from apps.financeiro.livro import saldo
from tests.apoio.financeiro import montar_l, obrigacao_de
from tests.apoio.pedidos import T0, administrador
from tests.conftest import RelogioControlado

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal


def _repassar(a: Any) -> Any:
    return registrar_saida(
        administrador(),
        tipo="repasse",
        conta=obrigacao_de(a.fornecedor, a.rodada),
        valor=D("50.00"),
        identificacao="sim-mov-9",
        justificativa="Repasse manual por Pix",
    )


def test_o_repasse_espera_a_liberacao_e_depois_baixa_so_a_obrigacao_do_fornecedor(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    a, b = montar_l(simulador_pagamentos, relogio)
    with pytest.raises(LiquidezInsuficiente):
        _repassar(a)  # o pagamento de XA só é liberado às T0 + 25h
    relogio.congelar(T0 + timedelta(hours=25))
    _repassar(a)
    assert saldo(obrigacao_de(a.fornecedor, a.rodada)) == D("50.00")
    assert saldo(obrigacao_de(b.fornecedor, b.rodada)) == D("80.00")
