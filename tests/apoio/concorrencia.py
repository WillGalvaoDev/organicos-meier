"""Execução paralela de operações, cada uma com sua conexão ao Postgres (E01-05).

Uso: o teste precisa de `django_db(transaction=True)` e do marcador `concorrencia`.
Cada operação recebe uma barreira interna (`threading.Barrier`) para forçar um ponto de
encontro definido pelo teste, por exemplo depois de ler e antes de gravar.

Tempo esgotado (spec.md, "Correção R05"): cada operação pendente fica numa de três situações,
nunca abriu conexão e já não pode abrir, abriu e teve a sessão encerrada no Postgres, ou estava
abrindo, terminou dentro do prazo de limpeza e fechou a conexão sem executar a operação. Quando
isso não pode ser cumprido, levanta `LimpezaIncompleta` e a guarda entre testes
(`tests/conftest.py`) impede que a suíte siga com conexão herdada.
"""

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper

TEMPO_LIMITE_PADRAO = 30.0
TEMPO_LIMITE_LIMPEZA_PADRAO = 30.0
# Limite fixo do driver: garante que uma abertura real termine em tempo finito, para que a
# guarda resolva a pendência. Só garante término dentro do prazo de limpeza quando esse prazo
# é maior que este valor; com prazo menor ou igual, uma abertura lenta resulta em
# `LimpezaIncompleta` (A-15). A ausência de sessão residual não depende desta desigualdade.
CONNECT_TIMEOUT_DAS_THREADS = 10
_INTERVALO_DE_CONFIRMACAO = 0.02

Operacao = Callable[[threading.Barrier], Any]


class TempoEsgotado(Exception):
    """Alguma operação não terminou dentro do tempo limite (e a limpeza foi confirmada)."""


class LimpezaIncompleta(Exception):
    """O tempo esgotou e a ausência de conexões residuais não pôde ser garantida.

    Falha de teste, nunca resultado aceitável. Não é subclasse de `TempoEsgotado`, para que
    `pytest.raises(TempoEsgotado)` não esconda a falha de limpeza.
    """


@dataclass
class Resultado:
    valor: Any = None
    excecao: BaseException | None = None


class Fase(Enum):
    ANTES = "ANTES"
    ABRINDO = "ABRINDO"
    ABERTA = "ABERTA"
    SEM_CONEXAO = "SEM_CONEXAO"


@dataclass
class _Operacao:
    indice: int
    nome: str
    aplicacao: str
    fase: Fase = Fase.ANTES


@dataclass
class _Execucao:
    """Estado compartilhado de uma chamada. `fase` e `expirado` só mudam sob `condicao`."""

    operacoes: list[_Operacao]
    condicao: threading.Condition = field(default_factory=threading.Condition)
    expirado: bool = False
    pendentes: list[_Operacao] = field(default_factory=list)

    def abrindo(self, operacoes: list[_Operacao]) -> bool:
        return any(op.fase is Fase.ABRINDO for op in operacoes)

    def descrever(self, operacoes: list[_Operacao]) -> str:
        with self.condicao:
            return ", ".join(f"{op.indice}:{op.nome} ({op.fase.value})" for op in operacoes)


_PENDENCIAS: list[_Execucao] = []
_TRAVA_DAS_PENDENCIAS = threading.Lock()


def limpezas_pendentes() -> int:
    """Quantidade de execuções com limpeza incompleta ainda não resolvida."""
    with _TRAVA_DAS_PENDENCIAS:
        return len(_PENDENCIAS)


def _nome(operacao: Operacao) -> str:
    return str(getattr(operacao, "__name__", repr(operacao)))


def _encerrar_e_confirmar(nomes: list[str], limite: float) -> bool:
    """Encerra no servidor as sessões com esses `application_name` e confirma que sumiram.

    `pg_terminate_backend` e o fechamento pelo cliente são assíncronos no servidor, então a
    confirmação em `pg_stat_activity` repete até zero sessões ou até `limite` (monotonic).
    """
    if not nomes:
        return True
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
                if restantes == 0:
                    return True
                if time.monotonic() >= limite:
                    return False
                time.sleep(_INTERVALO_DE_CONFIRMACAO)
    except Exception:
        return False


def _limpar(execucao: _Execucao, limite: float) -> bool:
    """Espera as aberturas em andamento (com prazo) e confirma zero sessões no servidor."""
    pendentes = execucao.pendentes
    nomes = [op.aplicacao for op in pendentes]
    _encerrar_e_confirmar(nomes, limite)  # sessões já ABERTAS saem sem esperar a abertura
    with execucao.condicao:
        sem_abertura = execucao.condicao.wait_for(
            lambda: not execucao.abrindo(pendentes), timeout=max(0.0, limite - time.monotonic())
        )
    sem_sessao = _encerrar_e_confirmar(nomes, limite)
    return sem_abertura and sem_sessao


def aguardar_limpezas_pendentes(prazo: float) -> None:
    """Resolve as limpezas pendentes (guarda); levanta `LimpezaIncompleta` se restar."""
    limite = time.monotonic() + prazo
    with _TRAVA_DAS_PENDENCIAS:
        execucoes = list(_PENDENCIAS)
    restantes: list[_Execucao] = []
    for execucao in execucoes:
        if _limpar(execucao, limite):
            with _TRAVA_DAS_PENDENCIAS:
                if execucao in _PENDENCIAS:
                    _PENDENCIAS.remove(execucao)
        else:
            restantes.append(execucao)
    if restantes:
        detalhes = "; ".join(e.descrever(e.pendentes) for e in restantes)
        raise LimpezaIncompleta(f"limpeza pendente de execução anterior: {detalhes}")


def executar_em_paralelo(
    *operacoes: Operacao,
    tempo_limite: float = TEMPO_LIMITE_PADRAO,
    tempo_limite_limpeza: float = TEMPO_LIMITE_LIMPEZA_PADRAO,
) -> list[Resultado]:
    """Executa as operações juntas, uma thread e uma conexão por operação.

    Devolve um `Resultado` por operação, na ordem recebida. Se alguma não terminar em
    `tempo_limite` segundos, faz a limpeza (até `tempo_limite_limpeza` segundos) e levanta
    `TempoEsgotado`; se a limpeza não puder ser garantida, levanta `LimpezaIncompleta`.
    Duração máxima: `tempo_limite + tempo_limite_limpeza`.
    """
    total = len(operacoes)
    if total == 0:
        return []
    prefixo = f"concorrencia-{uuid.uuid4().hex[:12]}"
    execucao = _Execucao(
        operacoes=[
            _Operacao(i, _nome(operacao), f"{prefixo}-{i}") for i, operacao in enumerate(operacoes)
        ]
    )
    condicao = execucao.condicao
    inicio = threading.Barrier(total)
    interna = threading.Barrier(total)
    resultados = [Resultado() for _ in operacoes]

    def mudar_fase(op: _Operacao, fase: Fase) -> None:
        with condicao:
            op.fase = fase
            condicao.notify_all()

    def instalar_connect_controlado(op: _Operacao, conexao: BaseDatabaseWrapper) -> None:
        original = conexao.connect

        def connect_controlado() -> None:
            with condicao:
                if execucao.expirado:
                    raise TempoEsgotado("operação expirada: não pode abrir conexão")
                op.fase = Fase.ABRINDO
            try:
                original()
            except BaseException:
                mudar_fase(op, Fase.SEM_CONEXAO)
                raise
            with condicao:
                if not execucao.expirado:
                    op.fase = Fase.ABERTA
                    condicao.notify_all()
                    return
            try:  # expirou durante a abertura: a própria thread fecha, sem executar a operação
                conexao.close()
            finally:
                mudar_fase(op, Fase.SEM_CONEXAO)
            raise TempoEsgotado("operação expirada durante a abertura da conexão")

        conexao.connect = connect_controlado  # type: ignore[method-assign]

    def executar(op: _Operacao) -> None:
        try:
            conexao = connections["default"]
            opcoes = {
                **conexao.settings_dict.get("OPTIONS", {}),
                "application_name": op.aplicacao,
                "connect_timeout": CONNECT_TIMEOUT_DAS_THREADS,
            }
            conexao.settings_dict = {**conexao.settings_dict, "OPTIONS": opcoes}
            instalar_connect_controlado(op, conexao)
            conexao.ensure_connection()  # todas abertas antes do início: pids distintos
            inicio.wait(timeout=tempo_limite)
            resultados[op.indice].valor = operacoes[op.indice](interna)
        except BaseException as erro:
            resultados[op.indice].excecao = erro
        finally:
            try:
                connections.close_all()
            except Exception:  # noqa: S110
                pass
            mudar_fase(op, Fase.SEM_CONEXAO)

    threads = [
        threading.Thread(target=executar, args=(op,), name=f"concorrencia-{op.indice}", daemon=True)
        for op in execucao.operacoes
    ]
    for thread in threads:
        thread.start()

    prazo = time.monotonic() + tempo_limite
    for thread in threads:
        thread.join(max(0.0, prazo - time.monotonic()))

    pendentes = [
        op for op, thread in zip(execucao.operacoes, threads, strict=True) if thread.is_alive()
    ]
    if not pendentes:
        return resultados

    limite_de_limpeza = time.monotonic() + tempo_limite_limpeza
    with condicao:
        execucao.expirado = True  # daqui em diante nenhuma operação em ANTES consegue abrir
        execucao.pendentes = pendentes
    inicio.abort()
    interna.abort()
    if _limpar(execucao, limite_de_limpeza):
        nomes = ", ".join(f"{op.indice}:{op.nome}" for op in pendentes)
        raise TempoEsgotado(f"operações pendentes após {tempo_limite}s: {nomes}")
    with _TRAVA_DAS_PENDENCIAS:
        _PENDENCIAS.append(execucao)
    raise LimpezaIncompleta(
        f"limpeza não garantida em {tempo_limite_limpeza}s: {execucao.descrever(pendentes)}"
    )
