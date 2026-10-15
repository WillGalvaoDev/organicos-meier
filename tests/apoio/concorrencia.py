"""Execução paralela de operações, cada uma com sua conexão ao Postgres (E01-05).

Uso: o teste precisa de `django_db(transaction=True)` e do marcador `concorrencia`.
Cada operação recebe uma barreira interna (`threading.Barrier`) para forçar um ponto de
encontro definido pelo teste, por exemplo depois de ler e antes de gravar.
"""

import threading
import time
import uuid
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


def _inutilizar(conexao: BaseDatabaseWrapper) -> None:
    """Fecha a conexão de uma operação expirada e impede que ela abra outra.

    A thread continua viva e pode retomar depois do tempo limite. Sem isto, o próximo
    `cursor()` reabriria a conexão (e executaria SQL durante outro teste). Cada thread tem
    seu próprio wrapper, então trocar `connect` afeta só a operação expirada.
    """

    def _recusar() -> None:
        raise TempoEsgotado("operação expirada: acesso ao banco não é mais permitido")

    conexao.connect = _recusar  # type: ignore[method-assign]
    conexao.inc_thread_sharing()
    try:
        conexao.close()
    except Exception:  # noqa: S110
        pass


def _encerrar_no_servidor(nomes: list[str], prazo: float = 2.0) -> None:
    """Encerra no Postgres os backends das operações expiradas, pelo `application_name`.

    Alcança também a conexão que o driver já estabeleceu mas que ainda não foi entregue
    ao wrapper do Django (nesse intervalo `close()` do wrapper não tem o que fechar).
    Espera, de forma limitada, o desaparecimento deles.
    """
    if not nomes:
        return
    limite = time.monotonic() + prazo
    try:
        with connections["default"].cursor() as cursor:
            while True:
                cursor.execute(
                    "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity "
                    "WHERE application_name = ANY(%s) AND pid <> pg_backend_pid()",
                    [nomes],
                )
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE application_name = ANY(%s)",
                    [nomes],
                )
                (restantes,) = cursor.fetchone()
                if restantes == 0 or time.monotonic() >= limite:
                    return
                time.sleep(0.02)
    except Exception:  # noqa: S110 — o chamador ainda recebe TempoEsgotado
        pass


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
    expirado = threading.Event()
    prefixo = f"concorrencia-{uuid.uuid4().hex[:12]}"
    nomes_de_aplicacao = [f"{prefixo}-{i}" for i in range(total)]

    def executar(indice: int) -> None:
        try:
            conexao = connections["default"]
            # Nome único por operação: permite encerrar a conexão no servidor mesmo antes
            # de o driver entregá-la ao wrapper (ver `_encerrar_no_servidor`).
            opcoes = {**conexao.settings_dict.get("OPTIONS", {})}
            opcoes["application_name"] = nomes_de_aplicacao[indice]
            conexao.settings_dict = {**conexao.settings_dict, "OPTIONS": opcoes}
            conexoes[indice] = conexao  # registrada antes de abrir: o timeout sempre a alcança
            conexao.ensure_connection()  # todas abertas antes do início: pids distintos
            if expirado.is_set():  # a abertura retornou depois do tempo limite
                raise TempoEsgotado("operação expirada durante a abertura da conexão")
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
        expirado.set()
        inicio.abort()
        interna.abort()
        for i in pendentes:
            conexao = conexoes[i]
            if conexao is not None:
                _inutilizar(conexao)
        _encerrar_no_servidor([nomes_de_aplicacao[i] for i in pendentes])
        nomes = ", ".join(_nome(operacoes[i], i) for i in pendentes)
        raise TempoEsgotado(f"operações pendentes após {tempo_limite}s: {nomes}")
    return resultados
