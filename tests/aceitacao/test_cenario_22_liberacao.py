"""Cenário 22 da especificação funcional: a liberação, a nova rodada e a rodada liberada que não
cancela (E14-04)."""

from decimal import Decimal
from typing import Any

import pytest

from tests.apoio.entrega import ae_recebido, liberar
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def test_a_liberacao_encerra_a_rodada_e_libera_o_fornecedor(
    relogio: RelogioControlado, sim: Any
) -> None:
    from apps.interesses.servicos import definir_interesse
    from apps.rodadas.estoque import incluir_produto_na_rodada
    from apps.rodadas.models import Rodada
    from apps.rodadas.servicos import abrir_rodada

    a, _x, _y, _pf = ae_recebido(relogio, sim)
    liberacao = liberar(relogio, a)
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "disponivel_para_retirada"
    assert (liberacao.prazo_final - liberacao.liberada_em).days == 7
    nova = abrir_rodada(a.admin, a.fornecedor)
    incluir_produto_na_rodada(a.admin, nova, a.p1, "11")
    c = ContaFactory.create(nome="Comprador C")
    assert definir_interesse(c, a.p1, "11").reservado == D("11")


def test_a_rodada_liberada_nao_e_cancelada(relogio: RelogioControlado, sim: Any) -> None:
    from apps.pedidos.cancelamento_da_rodada import CancelamentoRecusado, cancelar_rodada

    a, _x, _y, _pf = ae_recebido(relogio, sim)
    liberar(relogio, a)
    for com_reembolso in (True, False):
        with pytest.raises(CancelamentoRecusado) as erro:
            cancelar_rodada(a.admin, a.rodada, com_reembolso=com_reembolso)
        assert erro.value.codigo == "rodada_encerrada"
