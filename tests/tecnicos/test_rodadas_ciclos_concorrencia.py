"""E03-07: início do fechamento sob concorrência (acceptance A-11)."""

import time
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection, transaction

from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import alterar_minimo
from apps.rodadas.ciclos import registrar_condicoes_do_ciclo
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.models import Ciclo, Etapa, Rodada
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ContaFactory, FornecedorFactory, ProdutoFactory, RodadaFactory

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


def test_fechamento_iniciado_primeiro_registra_o_minimo_anterior() -> None:  # A-11
    admin = ContaFactory.create(administrador=True)
    fornecedor = FornecedorFactory.create(minimo=D("150.00"))
    rodada = RodadaFactory.create(fornecedor=fornecedor)

    def inicio(barreira: Any) -> int:
        with transaction.atomic():
            ciclo = registrar_condicoes_do_ciclo(Rodada.objects.get(pk=rodada.pk))
            Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.FECHAMENTO)
            barreira.wait(timeout=10)
            _esperar_outra_conexao_na_trava()
        return ciclo.pk

    def alteracao(barreira: Any) -> None:
        barreira.wait(timeout=10)
        alterar_minimo(admin, Fornecedor.objects.get(pk=fornecedor.pk), "200,00")

    resultados = executar_em_paralelo(inicio, alteracao)
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, CondicoesCongeladas)
    ciclo = Ciclo.objects.get(pk=resultados[0].valor)
    assert ciclo.minimo == D("150.00")
    fornecedor.refresh_from_db()
    assert fornecedor.minimo == D("150.00")


def test_dois_inicios_simultaneos_geram_um_ciclo() -> None:
    rodada = RodadaFactory.create()
    ProdutoFactory.create(fornecedor=rodada.fornecedor)

    def inicio(barreira: Any) -> None:
        barreira.wait(timeout=5)
        with transaction.atomic():
            registrar_condicoes_do_ciclo(Rodada.objects.get(pk=rodada.pk))
            Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.FECHAMENTO)

    resultados = executar_em_paralelo(inicio, inicio)
    sucessos = [r for r in resultados if r.excecao is None]
    recusas = [r.excecao for r in resultados if r.excecao is not None]
    assert len(sucessos) == 1, resultados
    assert len(recusas) == 1
    assert isinstance(recusas[0], CondicoesCongeladas)
    assert Ciclo.objects.filter(rodada=rodada).count() == 1
