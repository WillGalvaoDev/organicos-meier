"""E03-04: leituras das parcelas (acceptance A-6 a A-8 e A-11)."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from apps.catalogo.models import Produto
from apps.interesses.consultas import quantidades_em_uso, total_reservado
from apps.interesses.models import SituacaoParcela
from tests.fabricas import ParcelaFactory, ProdutoFactory

pytestmark = pytest.mark.django_db

D = Decimal
S = SituacaoParcela


def _cenario() -> tuple[Produto, Produto]:
    x, y = ProdutoFactory.create(), ProdutoFactory.create()
    ParcelaFactory.create(
        produto=x, quantidade_original=D("6"), quantidade_reservada=D("6"), situacao=S.ATIVA
    )
    ParcelaFactory.create(
        produto=x, quantidade_original=D("2"), quantidade_reservada=D("2"), situacao=S.EM_PEDIDO
    )
    ParcelaFactory.create(
        produto=x,
        quantidade_original=D("3"),
        quantidade_reservada=D("0"),
        quantidade_pendente=D("3"),
        situacao=S.PENDENTE,
    )
    ParcelaFactory.create(
        produto=x,
        quantidade_original=D("5"),
        quantidade_reservada=D("0"),
        quantidade_pendente=D("0"),
        situacao=S.REMOVIDA,
    )
    ParcelaFactory.create(
        produto=y, quantidade_original=D("5"), quantidade_reservada=D("5"), situacao=S.ATIVA
    )
    return x, y


def test_total_reservado_soma_ativas_e_em_pedido_do_produto() -> None:  # A-6
    x, _ = _cenario()
    total = total_reservado(x)
    assert total == D("8.000")
    assert str(total) == "8.000"


def test_total_reservado_sem_parcelas_e_zero() -> None:  # A-7
    total = total_reservado(ProdutoFactory.create())
    assert total == D("0.000")
    assert str(total) == "0.000"


def test_quantidades_em_uso_inclui_reservadas_e_pendentes() -> None:  # A-8
    x, _ = _cenario()
    ParcelaFactory.create(
        produto=x,
        quantidade_original=D("8"),
        quantidade_reservada=D("4"),
        quantidade_pendente=D("4"),
        situacao=S.ATIVA,
    )
    usadas = quantidades_em_uso(x)
    assert sorted(usadas) == [D(2), D(3), D(4), D(4), D(6)]
    assert all(isinstance(q, Decimal) for q in usadas)


def test_quantidades_em_uso_vazio_sem_parcelas() -> None:
    assert quantidades_em_uso(ProdutoFactory.create()) == []


def test_quantidades_em_uso_segue_a_ordem_da_fila() -> None:
    produto = ProdutoFactory.create()
    for q in ("3", "1", "2"):
        ParcelaFactory.create(produto=produto, quantidade_original=D(q), quantidade_reservada=D(q))
    assert quantidades_em_uso(produto) == [D(3), D(1), D(2)]


@pytest.mark.parametrize("leitura", [total_reservado, quantidades_em_uso])
def test_leitura_com_trava_usa_for_update_ordenado_pela_sequencia(
    leitura: Callable[..., Any],
) -> None:  # A-11
    x, _ = _cenario()
    with transaction.atomic(), CaptureQueriesContext(connection) as consultas:
        leitura(x, travar=True)
    sqls = [c["sql"] for c in consultas if "interesses_parcela" in c["sql"]]
    assert sqls, "a leitura precisa consultar as parcelas"
    for sql in sqls:
        assert "FOR UPDATE" in sql
        assert 'ORDER BY "interesses_parcela"."sequencia"' in sql


def test_leitura_com_trava_devolve_os_mesmos_valores() -> None:
    x, _ = _cenario()
    with transaction.atomic():
        assert total_reservado(x, travar=True) == D("8.000")
        assert sorted(quantidades_em_uso(x, travar=True)) == [D(2), D(3), D(6)]
