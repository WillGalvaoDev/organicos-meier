"""E03-02: concorrência em rodadas (acceptance A-5, A-14 e A-15)."""

import time
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection, transaction

from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import alterar_minimo
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.condicoes import CondicoesCongeladas, travar_condicoes
from apps.rodadas.models import ETAPAS_ATIVAS, Etapa, Rodada
from apps.rodadas.servicos import RodadaAtivaExistente, abrir_rodada
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ContaFactory, FornecedorFactory, RodadaFactory

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]


def test_duas_aberturas_simultaneas_geram_uma_rodada() -> None:  # A-5
    admin = ContaFactory.create(administrador=True)
    for _ in range(10):
        fornecedor = FornecedorFactory.create()

        def abertura(barreira: Any, fornecedor_id: int = fornecedor.pk) -> None:
            barreira.wait(timeout=5)
            abrir_rodada(admin, Fornecedor.objects.get(pk=fornecedor_id))

        resultados = executar_em_paralelo(abertura, abertura)
        sucessos = [r for r in resultados if r.excecao is None]
        recusas = [r.excecao for r in resultados if r.excecao is not None]
        assert len(sucessos) == 1, resultados
        assert len(recusas) == 1
        assert isinstance(recusas[0], RodadaAtivaExistente)
        ativas = Rodada.objects.filter(fornecedor=fornecedor, etapa__in=ETAPAS_ATIVAS)
        assert ativas.count() == 1


def test_alteracao_do_minimo_espera_a_mudanca_de_etapa() -> None:  # A-14
    admin = ContaFactory.create(administrador=True)
    fornecedor = FornecedorFactory.create(minimo=Decimal("150.00"))
    rodada = RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.INTERESSE)

    def transicao(barreira: Any) -> None:
        with transaction.atomic():
            travada = travar_condicoes(Fornecedor.objects.get(pk=fornecedor.pk))
            travada.etapa = Etapa.FECHAMENTO
            travada.save(update_fields=["etapa"])
            barreira.wait(timeout=10)  # a outra operação já foi lançada
            with connection.cursor() as cursor:
                limite = time.monotonic() + 15
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

    def alteracao(barreira: Any) -> None:
        barreira.wait(timeout=10)
        alterar_minimo(admin, Fornecedor.objects.get(pk=fornecedor.pk), "200,00")

    resultados = executar_em_paralelo(transicao, alteracao)
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, CondicoesCongeladas)
    fornecedor.refresh_from_db()
    rodada.refresh_from_db()
    assert fornecedor.minimo == Decimal("150.00")
    assert rodada.etapa == Etapa.FECHAMENTO
    assert EntradaAuditoria.objects.filter(acao="fornecedor.alterar_minimo").count() == 0


def test_duas_alteracoes_simultaneas_ficam_em_serie() -> None:  # A-15
    admin = ContaFactory.create(administrador=True)
    fornecedor = FornecedorFactory.create(minimo=Decimal("150.00"))
    RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.INTERESSE)

    def alteracao(barreira: Any, valor: str) -> None:
        barreira.wait(timeout=5)
        alterar_minimo(admin, Fornecedor.objects.get(pk=fornecedor.pk), valor)

    def para_200(barreira: Any) -> None:
        alteracao(barreira, "200,00")

    def para_300(barreira: Any) -> None:
        alteracao(barreira, "300,00")

    resultados = executar_em_paralelo(para_200, para_300)
    assert all(r.excecao is None for r in resultados), resultados
    entradas = list(
        EntradaAuditoria.objects.filter(acao="fornecedor.alterar_minimo").order_by("id")
    )
    assert len(entradas) == 2
    primeira, segunda = entradas
    assert primeira.alteracoes["anterior"] == "150.00"
    assert segunda.alteracoes["anterior"] == primeira.alteracoes["novo"]
    fornecedor.refresh_from_db()
    assert str(fornecedor.minimo) == segunda.alteracoes["novo"]
    assert {primeira.alteracoes["novo"], segunda.alteracoes["novo"]} == {"200.00", "300.00"}
