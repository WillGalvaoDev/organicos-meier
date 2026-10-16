"""E03-05: estoque sob concorrência (acceptance A-15 a A-17)."""

import time
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from apps.catalogo.models import Produto
from apps.interesses.consultas import total_reservado
from apps.interesses.models import ParcelaDeInteresse
from apps.rodadas.condicoes import CondicoesCongeladas, travar_condicoes
from apps.rodadas.estoque import (
    EstoqueAbaixoDoReservado,
    alterar_estoque,
    incluir_produto_na_rodada,
    travar_estoque,
)
from apps.rodadas.models import EstoqueDaRodada, Etapa, Rodada
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    ParcelaFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]

D = Decimal


def _esperar_outra_conexao_na_trava(segundos: float = 15) -> None:
    with connection.cursor() as cursor:
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE wait_event_type = 'Lock' AND datname = current_database()"
            )
            (esperando,) = cursor.fetchone()
            if esperando:
                return
            time.sleep(0.05)
    raise AssertionError("a outra conexão não ficou esperando pela trava")


def test_alteracao_do_estoque_espera_a_mudanca_de_etapa() -> None:  # A-15
    admin = ContaFactory.create(administrador=True)
    estoque = EstoqueDaRodadaFactory.create(limite=D("10"))
    fornecedor_id = estoque.rodada.fornecedor_id

    def transicao(barreira: Any) -> None:
        with transaction.atomic():
            rodada = travar_condicoes(estoque.rodada.fornecedor)
            rodada.etapa = Etapa.FECHAMENTO
            rodada.save(update_fields=["etapa"])
            barreira.wait(timeout=10)
            _esperar_outra_conexao_na_trava()

    def alteracao(barreira: Any) -> None:
        barreira.wait(timeout=10)
        alterar_estoque(admin, EstoqueDaRodada.objects.get(pk=estoque.pk), "8")

    resultados = executar_em_paralelo(transicao, alteracao)
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, CondicoesCongeladas)
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")
    assert Rodada.objects.get(fornecedor_id=fornecedor_id).etapa == Etapa.FECHAMENTO


def test_reserva_concluida_antes_barra_a_reducao() -> None:  # A-16
    admin = ContaFactory.create(administrador=True)
    estoque = EstoqueDaRodadaFactory.create(limite=D("10"))
    produto = estoque.produto
    parcela = ParcelaFactory.create(
        produto=produto, quantidade_original=D("8"), quantidade_reservada=D("6")
    )

    def reserva(barreira: Any) -> None:
        # a mesma ordem de travas que a E05 usa: fornecedor, rodada, produto e estoque
        with transaction.atomic():
            rodada = travar_condicoes(Produto.objects.get(pk=produto.pk).fornecedor)
            travar_estoque(rodada, Produto.objects.get(pk=produto.pk))
            ParcelaDeInteresse.objects.filter(pk=parcela.pk).update(quantidade_reservada=D("8"))
            barreira.wait(timeout=10)
            _esperar_outra_conexao_na_trava()

    def reducao(barreira: Any) -> None:
        barreira.wait(timeout=10)
        alterar_estoque(admin, EstoqueDaRodada.objects.get(pk=estoque.pk), "7")

    resultados = executar_em_paralelo(reserva, reducao)
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, EstoqueAbaixoDoReservado)
    estoque.refresh_from_db()
    assert estoque.limite == D("10.000")
    assert total_reservado(produto) == D("8.000")


def test_duas_inclusoes_do_mesmo_produto() -> None:  # A-17
    admin = ContaFactory.create(administrador=True)
    for _ in range(10):
        rodada = RodadaFactory.create()
        produto = ProdutoFactory.create(fornecedor=rodada.fornecedor)

        def inclusao(
            barreira: Any, rodada_id: int = rodada.pk, produto_id: int = produto.pk
        ) -> None:
            barreira.wait(timeout=5)
            incluir_produto_na_rodada(
                admin, Rodada.objects.get(pk=rodada_id), Produto.objects.get(pk=produto_id), "5"
            )

        resultados = executar_em_paralelo(inclusao, inclusao)
        sucessos = [r for r in resultados if r.excecao is None]
        recusas = [r.excecao for r in resultados if r.excecao is not None]
        assert len(sucessos) == 1, resultados
        assert len(recusas) == 1
        assert isinstance(recusas[0], ValidationError)
        assert EstoqueDaRodada.objects.filter(rodada=rodada, produto=produto).count() == 1
