"""E04-01: marcações simultâneas da mesma notificação (acceptance A-13)."""

import time
from typing import Any

import pytest
from django.db import connection, transaction

from apps.notificacoes.models import Notificacao
from apps.notificacoes.servicos import marcar_como_lida
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ContaFactory, NotificacaoFactory

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]


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


def test_duas_marcacoes_gravam_uma_so_vez() -> None:  # A-13
    conta = ContaFactory.create()
    notificacao = NotificacaoFactory.create(conta=conta)

    def primeira(barreira: Any) -> bool | None:
        with transaction.atomic():
            gravou = marcar_como_lida(conta, notificacao.pk)
            barreira.wait(timeout=10)
            _esperar_outra_conexao_na_trava()
        return gravou

    def segunda(barreira: Any) -> bool | None:
        barreira.wait(timeout=10)
        return marcar_como_lida(conta, notificacao.pk)

    resultados = executar_em_paralelo(primeira, segunda)
    assert resultados[0].excecao is None, resultados[0].excecao
    assert resultados[1].excecao is None, resultados[1].excecao
    assert resultados[0].valor is True
    assert resultados[1].valor is False
    lida_em = Notificacao.objects.get(pk=notificacao.pk).lida_em
    assert lida_em is not None
