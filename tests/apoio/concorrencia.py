"""Execução paralela de operações, cada uma com sua conexão ao Postgres (E01-05).

Uso: o teste precisa de `django_db(transaction=True)` e do marcador `concorrencia`.
Cada operação recebe uma barreira interna (`threading.Barrier`) para forçar um ponto de
encontro definido pelo teste, por exemplo depois de ler e antes de gravar.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper

TEMPO_LIMITE_PADRAO = 30.0

Operacao = Callable[[threading.Barrier], Any]


class TempoEsgotado(Exception):
    """Alguma operação não terminou dentro do tempo limite."""


@dataclass
class Resultado:
    valor: Any = None
    excecao: BaseException | None = None


def _nome(operacao: Operacao, indice: int) -> str:
    return f"{indice}:{getattr(operacao, '__name__', repr(operacao))}"


def executar_em_paralelo(
    *operacoes: Operacao, tempo_limite: float = TEMPO_LIMITE_PADRAO
) -> list[Resultado]:
    """Executa as operações juntas, uma thread e uma conexão por operação.

    Devolve um `Resultado` por operação, na ordem recebida. Se alguma não terminar em
    `tempo_limite` segundos, fecha as conexões das pendentes e levanta `TempoEsgotado`.
    """
    total = len(operacoes)
    if total == 0:
        return []
    inicio = threading.Barrier(total)
    interna = threading.Barrier(total)
    resultados = [Resultado() for _ in operacoes]
    conexoes: list[BaseDatabaseWrapper | None] = [None] * total

    def executar(indice: int) -> None:
        try:
            conexao = connections["default"]
            conexao.ensure_connection()  # todas abertas antes do início: pids distintos
            conexoes[indice] = conexao
            inicio.wait(timeout=tempo_limite)
            resultados[indice].valor = operacoes[indice](interna)
        except BaseException as erro:
            resultados[indice].excecao = erro
        finally:
            try:
                connections.close_all()
            except Exception:  # noqa: S110
                pass

    threads = [
        threading.Thread(target=executar, args=(i,), name=f"concorrencia-{i}", daemon=True)
        for i in range(total)
    ]
    for thread in threads:
        thread.start()

    prazo = time.monotonic() + tempo_limite
    for thread in threads:
        thread.join(max(0.0, prazo - time.monotonic()))

    pendentes = [i for i, thread in enumerate(threads) if thread.is_alive()]
    if pendentes:
        inicio.abort()
        interna.abort()
        for i in pendentes:
            conexao = conexoes[i]
            if conexao is not None:
                conexao.inc_thread_sharing()
                try:
                    conexao.close()
                except Exception:  # noqa: S110
                    pass
        nomes = ", ".join(_nome(operacoes[i], i) for i in pendentes)
        raise TempoEsgotado(f"operações pendentes após {tempo_limite}s: {nomes}")
    return resultados
