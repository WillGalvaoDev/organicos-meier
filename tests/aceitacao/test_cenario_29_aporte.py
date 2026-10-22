"""Cenário 29 (E09-05, A-1): o aporte do administrador não é receita."""

from decimal import Decimal

import pytest
from apps.financeiro.reserva import registrar_aporte, situacao_da_reserva

from apps.financeiro.livro import saldo
from apps.financeiro.models import ContaFinanceira
from tests.apoio.financeiro import montar_mundo, reserva

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal


def test_o_aporte_inicial_vai_so_para_a_reserva() -> None:
    mundo = montar_mundo()
    registrar_aporte(mundo.admin, D("1000.00"), "sim-mov-1", "Aporte inicial")
    assert saldo(reserva()) == D("1000.00")
    assert situacao_da_reserva().livre == D("1000.00")
    receitas = ContaFinanceira.objects.filter(destinacao="receita_servico")
    assert [c for c in receitas if saldo(c) != 0] == []
    fornecedores = ContaFinanceira.objects.filter(destinacao="obrigacao_fornecedor")
    assert [c for c in fornecedores if saldo(c) != 0] == []
