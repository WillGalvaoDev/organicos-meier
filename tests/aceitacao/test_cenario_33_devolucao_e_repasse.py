"""Cenário 33 (E09-06, A-6 a A-9): a devolução devida sai dos recursos da própria rodada antes do
repasse; depois do repasse, o que falta fica sem cobertura até o administrador escolher a fonte."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from apps.financeiro.apuracao import registrar_apuracao_no_livro
from apps.financeiro.obrigacoes import (
    cobrir_obrigacao_com_receita,
    registrar_obrigacao_com_comprador,
)

from apps.financeiro.livro import EXTERIOR, saldo
from apps.financeiro.models import TipoDeMovimento
from apps.financeiro.reserva import designar_reserva, itens_sem_cobertura
from apps.nucleo.auditoria import SISTEMA
from tests.apoio.financeiro import (
    custodia,
    montar_ap,
    montar_mundo,
    mover,
    obrigacao_de,
    pagar_pedido,
    receita_de,
    reserva,
    semear,
)
from tests.conftest import RelogioControlado

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal


def _pedir(ap: Any) -> Any:
    return registrar_obrigacao_com_comprador(
        origem=ap.x,
        rodada=ap.rodada,
        ciclo=ap.ciclo,
        comprador=ap.b,
        pedido=ap.x,
        motivo="devolucao_de_teste",
        produtos=D("25.00"),
        servico=D("1.25"),
        frete=D("5.00"),
    )


def test_antes_do_repasse_a_devolucao_sai_dos_recursos_da_propria_rodada(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    simulador_pagamentos.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    ap = montar_ap()
    pagar_pedido(ap, ap.x, simulador_pagamentos, relogio, timedelta(hours=1))
    resultado = _pedir(ap)
    assert resultado.sem_cobertura == D("0.00")
    assert [
        saldo(custodia(ap.rodada, ap.ciclo, ap.b, componente))
        for componente in ("produtos", "servico", "frete")
    ] == [D("75.00"), D("3.75"), D("15.00")]


def test_depois_do_repasse_o_que_falta_fica_sem_cobertura_ate_o_administrador_escolher(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    simulador_pagamentos.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    ap = montar_ap()
    pagar_pedido(ap, ap.x, simulador_pagamentos, relogio, timedelta(hours=1))
    mover(TipoDeMovimento.APORTE, EXTERIOR, reserva(), "1000.00", autor=ap.admin, justificativa="A")
    registrar_apuracao_no_livro(ap.ciclo, [ap.x], autor=SISTEMA)
    mover(TipoDeMovimento.REPASSE, obrigacao_de(ap.fornecedor, ap.rodada), EXTERIOR, "100.00")
    resultado = registrar_obrigacao_com_comprador(
        origem=ap.x,
        rodada=ap.rodada,
        ciclo=ap.ciclo,
        comprador=ap.b,
        pedido=ap.x,
        motivo="devolucao_de_teste",
        produtos=D("25.00"),
        servico=D("0.00"),
        frete=D("0.00"),
    )
    assert resultado.obrigacao.devido == D("25.00")
    assert resultado.sem_cobertura == D("25.00")
    outra = montar_mundo()
    semear(outra, receita_de(outra.rb), "10.00")
    cobrir_obrigacao_com_receita(ap.admin, resultado.obrigacao, outra.rb, D("10.00"), "receita")
    designar_reserva(ap.admin, resultado.obrigacao, D("15.00"), "reserva")
    assert [i for i in itens_sem_cobertura() if i.tipo == "obrigacao"] == []
