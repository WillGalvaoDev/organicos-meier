"""E03-03: edições de preço em paralelo (acceptance A-21)."""

from decimal import Decimal
from typing import Any

import pytest

from apps.catalogo.models import Produto
from apps.catalogo.servicos import editar_produto
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ContaFactory, ProdutoFactory

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]


def test_duas_edicoes_de_preco_ficam_em_serie() -> None:  # A-21
    admin = ContaFactory.create(administrador=True)
    for _ in range(10):
        produto = ProdutoFactory.create(preco=Decimal("10.00"))

        def mudar(barreira: Any, preco: str, produto_id: int = produto.pk) -> None:
            barreira.wait(timeout=5)
            editar_produto(admin, Produto.objects.get(pk=produto_id), preco=preco)

        def para_11(barreira: Any, produto_id: int = produto.pk) -> None:
            mudar(barreira, "11,00", produto_id)

        def para_12(barreira: Any, produto_id: int = produto.pk) -> None:
            mudar(barreira, "12,00", produto_id)

        resultados = executar_em_paralelo(para_11, para_12)
        assert all(r.excecao is None for r in resultados), resultados
        entradas = list(
            EntradaAuditoria.objects.filter(
                acao="produto.alterar_preco", objeto_id=str(produto.pk)
            ).order_by("id")
        )
        assert len(entradas) == 2
        primeira, segunda = entradas
        assert primeira.alteracoes["anterior"] == "10.00"
        assert segunda.alteracoes["anterior"] == primeira.alteracoes["novo"]
        produto.refresh_from_db()
        assert str(produto.preco) == segunda.alteracoes["novo"]
