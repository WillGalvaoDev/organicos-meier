"""Cenário 34 (E09-05, A-4 a A-6, no nível do livro-razão): a reserva insuficiente alerta."""

from decimal import Decimal

import pytest

from apps.financeiro.models import AlertaFinanceiro
from apps.financeiro.reserva import (
    ReservaInsuficiente,
    avaliar_reserva,
    designar_reserva,
    registrar_aporte,
    situacao_da_reserva,
)
from tests.apoio.financeiro import montar_mundo, obrigacao_de_teste, reserva, semear

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal


def test_reserva_que_nao_cobre_alerta_e_o_aporte_do_administrador_resolve() -> None:
    mundo = montar_mundo()
    semear(mundo, reserva(), "30.00")
    obrigacao = obrigacao_de_teste("50.00")
    with pytest.raises(ReservaInsuficiente):
        designar_reserva(mundo.admin, obrigacao, D("50.00"), "devolução depois do repasse")
    avaliar_reserva()
    assert (
        AlertaFinanceiro.objects.filter(tipo="reserva_insuficiente", resolvido_em=None).count() == 1
    )
    # o sistema não recompõe a reserva sozinho (P-4): só o aporte do administrador a recompõe
    assert situacao_da_reserva().saldo == D("30.00")
    registrar_aporte(mundo.admin, D("40.00"), "sim-mov-2", "Aporte para cobrir a devolução")
    assert (
        AlertaFinanceiro.objects.filter(tipo="reserva_insuficiente", resolvido_em=None).count() == 0
    )
    designar_reserva(mundo.admin, obrigacao, D("50.00"), "devolução depois do repasse")
    assert situacao_da_reserva().livre == D("20.00")
