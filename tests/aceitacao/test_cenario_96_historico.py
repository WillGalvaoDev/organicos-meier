"""Cenário 96 (§16): o carrinho e o histórico mostram reservado e pendente, com o estoque zerado.

E16-09 A-1: A com 6 reservados e 4 pendentes reais de `P` (apuração com caixa invalidada,
restauração e reabertura com o estoque livre zero); o histórico é a tela "Meus pedidos".
"""

import re
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from apps.financeiro.models import Reembolso
from apps.interesses.consultas import total_reservado
from tests.conftest import RelogioControlado
from tests.tecnicos.test_fila_ponta_a_ponta import _estado, abrir_r2, montar_fp

D = Decimal
pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def test_cenario_96_historico_mostra_reservado_e_pendente_com_estoque_zerado(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    # A: 10 em P; a caixa invalidada deixa os 10 pendentes; a rodada nova tem limite 6.
    fp = montar_fp(relogio, simulador_pagamentos, quantidades_de_p=(10, 4, 6))
    abrir_r2(fp, 6)
    _situacao, reservado, pendente = _estado(fp.a, fp.p)
    assert (reservado, pendente) == (D("6.000"), D("4.000"))
    assert Reembolso.objects.filter(motivo="caixa_invalidada", pedido__comprador=fp.a).exists()
    cliente = Client()
    cliente.force_login(fp.a)
    assert total_reservado(fp.p) == D("6.000")  # igual ao limite de P: livre zero
    resposta = cliente.get("/pedidos/")
    assert resposta.status_code == 200
    texto = _texto(resposta)
    assert "Interesses reservados e pendentes" in texto
    secao = texto.split("Interesses reservados e pendentes", 1)[1]
    assert "Reservado: 6" in secao
    assert "Pendente: 4" in secao
    assert secao.index("Reservado: 6") < secao.index("Pendente: 4")
