"""Cenário 32 (E09-01, A-3 a A-6): o dinheiro de um fornecedor não paga outro uso.

Provado no nível do livro-razão; as etapas seguintes repetem o cenário pelos fluxos reais.
"""

from decimal import Decimal
from typing import Any

import pytest

from apps.financeiro.livro import EXTERIOR, MovimentoProibido, saldo
from apps.financeiro.models import ContaFinanceira, MovimentoFinanceiro, TipoDeMovimento
from tests.apoio.financeiro import (
    Mundo,
    custodia,
    despesas,
    frete_de,
    montar_mundo,
    mover,
    obrigacao_com,
    obrigacao_de,
    receita_de,
    reserva,
    semear,
)

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal
T = TipoDeMovimento


def _saldos() -> list[tuple[int, Decimal]]:
    return [(c.pk, saldo(c)) for c in ContaFinanceira.objects.order_by("pk") if saldo(c) != 0]


@pytest.fixture
def m() -> Mundo:
    return montar_mundo()


def test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso(m: Mundo) -> None:
    produtos = custodia(m.ra, m.ca, m.x)
    semear(m, produtos, "100.00")
    devida = obrigacao_de(m.fa, m.ra)
    semear(m, devida, "100.00")
    mover(T.TARIFA, despesas(), EXTERIOR, "1.00")
    antes = (_saldos(), MovimentoFinanceiro.objects.count())
    tentativas: list[tuple[str, Any, Any]] = [
        (T.COBERTURA_DE_DESPESA, produtos, despesas()),
        (T.FINANCIAMENTO_DE_OBRIGACAO, devida, obrigacao_com(m.rb, m.cb, m.x, numero=2)),
        (T.COBERTURA_DE_DESPESA, devida, frete_de(m.rb)),
        (T.APURACAO, devida, reserva()),
        (T.APURACAO, devida, receita_de(m.ra)),
        (T.REPASSE, devida, obrigacao_de(m.fb, m.rb)),
        (T.FINANCIAMENTO_DE_OBRIGACAO, produtos, obrigacao_com(m.ra, m.ca, m.y)),
    ]
    for tipo, de, para in tentativas:
        with pytest.raises(MovimentoProibido):
            mover(tipo, de, para, "1.00")
    assert (_saldos(), MovimentoFinanceiro.objects.count()) == antes


def test_a_devolucao_devida_antes_do_repasse_e_a_unica_ressalva(m: Mundo) -> None:
    devida = obrigacao_de(m.fa, m.ra)
    semear(m, devida, "100.00")
    obrigacao = obrigacao_com(m.ra, m.ca, m.x)
    mover(T.FINANCIAMENTO_DE_OBRIGACAO, devida, obrigacao, "25.00")
    assert (saldo(devida), saldo(obrigacao)) == (D("75.00"), D("25.00"))
