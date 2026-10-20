"""Apoio dos testes de concorrência por trava (E05, E06): reter a trava e esperar a outra operação.

`segurando` roda a operação numa transação externa e só a solta depois de ver a outra conexão
esperando por trava em `pg_stat_activity`; se ela não aparece no prazo, a falha é uma asserção com
mensagem (nunca um travamento do teste).
"""

import time
from collections.abc import Callable
from typing import Any

from django.db import connection, transaction


def outra_conexao_esperando() -> bool:
    """Alguma outra conexão do banco de testes está esperando por trava neste instante?"""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE wait_event_type = 'Lock' AND datname = current_database()"
        )
        (esperando,) = cursor.fetchone()
    return bool(esperando)


def esperar_outra_conexao_na_trava(segundos: float = 15) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if outra_conexao_esperando():
            return
        time.sleep(0.05)
    raise AssertionError("a outra conexão não ficou esperando pela trava")


def segurando(operacao: Callable[[], Any]) -> Callable[[Any], Any]:
    """Executa a operação e mantém as travas dela até a outra conexão esperar."""

    def segura(barreira: Any) -> Any:
        with transaction.atomic():
            resultado = operacao()
            barreira.wait(timeout=10)
            esperar_outra_conexao_na_trava()
        return resultado

    return segura


def esperando(operacao: Callable[[], Any]) -> Callable[[Any], Any]:
    """Começa junto com a que segura; a barreira garante que a outra já travou."""

    def espera(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        return operacao()

    return espera
