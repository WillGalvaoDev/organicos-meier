"""E03-04: sequência da parcela sob concorrência (acceptance A-9)."""

from typing import Any

import pytest

from apps.interesses.models import ParcelaDeInteresse
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ContaFactory, ParcelaFactory, ProdutoFactory

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]


def test_vinte_insercoes_em_paralelo_recebem_sequencias_distintas() -> None:  # A-9
    comprador = ContaFactory.create()
    produto = ProdutoFactory.create()

    def inserir(barreira: Any) -> int:
        barreira.wait(timeout=10)
        return ParcelaFactory.create(comprador=comprador, produto=produto).sequencia

    resultados = executar_em_paralelo(*[inserir] * 20)
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    sequencias = [r.valor for r in resultados]
    assert len(set(sequencias)) == 20
    gravadas = list(
        ParcelaDeInteresse.objects.order_by("sequencia").values_list("sequencia", flat=True)
    )
    assert sorted(sequencias) == gravadas
