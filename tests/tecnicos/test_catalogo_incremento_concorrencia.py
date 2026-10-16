"""E03-06: alteração do incremento sob concorrência (acceptance A-10 a A-12)."""

import time
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection, transaction

from apps.catalogo.models import Produto
from apps.catalogo.servicos import IncrementoIncompativel, alterar_incremento
from apps.interesses.consultas import quantidades_em_uso
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.condicoes import CondicoesCongeladas, travar_condicoes
from apps.rodadas.models import Etapa, Rodada
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ContaFactory, ParcelaFactory, ProdutoFactory, RodadaFactory

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


def test_alteracao_espera_a_mudanca_de_etapa() -> None:  # A-10
    admin = ContaFactory.create(administrador=True)
    produto = ProdutoFactory.create(incremento=D("0.500"))
    rodada = RodadaFactory.create(fornecedor=produto.fornecedor)

    def transicao(barreira: Any) -> None:
        with transaction.atomic():
            travada = travar_condicoes(Produto.objects.get(pk=produto.pk).fornecedor)
            travada.etapa = Etapa.FECHAMENTO
            travada.save(update_fields=["etapa"])
            barreira.wait(timeout=10)
            _esperar_outra_conexao_na_trava()

    def alteracao(barreira: Any) -> None:
        barreira.wait(timeout=10)
        alterar_incremento(admin, Produto.objects.get(pk=produto.pk), "0.25")

    resultados = executar_em_paralelo(transicao, alteracao)
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, CondicoesCongeladas)
    produto.refresh_from_db()
    assert produto.incremento == D("0.500")
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO


def test_parcela_criada_antes_da_trava_barra_a_alteracao() -> None:  # A-11
    admin = ContaFactory.create(administrador=True)
    produto = ProdutoFactory.create(incremento=D("0.500"))
    RodadaFactory.create(fornecedor=produto.fornecedor)
    comprador = ContaFactory.create()

    def adicao(barreira: Any) -> None:
        # a mesma ordem de travas que a adição de interesse da E05 usa
        with transaction.atomic():
            fornecedor = Produto.objects.get(pk=produto.pk).fornecedor
            travar_condicoes(fornecedor)
            alvo = Produto.objects.select_for_update().get(pk=produto.pk)
            quantidades_em_uso(alvo, travar=True)
            ParcelaFactory.create(
                comprador=comprador,
                produto=alvo,
                quantidade_original=D("1.5"),
                quantidade_reservada=D("1.5"),
            )
            barreira.wait(timeout=10)
            _esperar_outra_conexao_na_trava()

    def alteracao(barreira: Any) -> None:
        barreira.wait(timeout=10)
        alterar_incremento(admin, Produto.objects.get(pk=produto.pk), "1")

    resultados = executar_em_paralelo(adicao, alteracao)
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, IncrementoIncompativel)
    produto.refresh_from_db()
    assert produto.incremento == D("0.500")
    assert EntradaAuditoria.objects.filter(acao="produto.alterar_incremento").count() == 0


def test_duas_alteracoes_ficam_em_serie() -> None:  # A-12
    admin = ContaFactory.create(administrador=True)
    produto = ProdutoFactory.create(incremento=D("0.500"))
    RodadaFactory.create(fornecedor=produto.fornecedor)

    def para(valor: str) -> Any:
        def alteracao(barreira: Any) -> None:
            barreira.wait(timeout=5)
            alterar_incremento(admin, Produto.objects.get(pk=produto.pk), valor)

        return alteracao

    resultados = executar_em_paralelo(para("0.25"), para("0.125"))
    assert all(r.excecao is None for r in resultados), resultados
    entradas = list(
        EntradaAuditoria.objects.filter(acao="produto.alterar_incremento").order_by("id")
    )
    assert len(entradas) == 2
    primeira, segunda = entradas
    assert primeira.alteracoes["anterior"] == "0.500"
    assert segunda.alteracoes["anterior"] == primeira.alteracoes["novo"]
    produto.refresh_from_db()
    assert str(produto.incremento) == segunda.alteracoes["novo"]
