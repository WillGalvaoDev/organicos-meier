"""Cenário 23 da especificação funcional: o descarte é manual e só depois de sete dias
(E14-05)."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from tests.apoio.apuracao import H
from tests.apoio.entrega import ae_liberada, descartar, item_de, retirar
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
L = T0 + 72 * H
PRAZO_FINAL = L + timedelta(days=7)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def test_nenhum_descarte_antes_dos_sete_dias(relogio: RelogioControlado, sim: Any) -> None:
    from apps.pedidos.retirada import RetiradaRecusada

    a, x, _y, _pf = ae_liberada(relogio, sim)
    relogio.congelar(PRAZO_FINAL - timedelta(milliseconds=1))
    with pytest.raises(RetiradaRecusada) as erro:
        descartar(a.admin, item_de(x, a.p1), D("6"))
    assert erro.value.codigo == "antes_do_prazo"


def test_o_descarte_exatamente_no_prazo_final(relogio: RelogioControlado, sim: Any) -> None:
    a, x, _y, _pf = ae_liberada(relogio, sim)
    relogio.congelar(PRAZO_FINAL)
    assert descartar(a.admin, item_de(x, a.p1), D("6")).novo is True


def test_a_passagem_do_tempo_nunca_descarta(relogio: RelogioControlado, sim: Any) -> None:
    from apps.pedidos.retirada import situacao_da_retirada

    from apps.pedidos.models import DescarteDeItem

    a, x, _y, _pf = ae_liberada(relogio, sim)
    retirar(a.admin, item_de(x, a.p1), D("4"))
    relogio.congelar(L + timedelta(days=8))
    situacao = situacao_da_retirada(a.rodada)
    assert situacao.prazo_encerrado is True
    assert len(situacao.vencidos) == 4
    assert not DescarteDeItem.objects.exists()
