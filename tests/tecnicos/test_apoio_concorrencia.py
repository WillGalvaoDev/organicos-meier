"""E01-05: utilitário de testes de concorrência (acceptance A-1 a A-7)."""

import re
import threading
import time
from collections.abc import Callable
from typing import Any

import pytest
from django.db import OperationalError, connection, connections, transaction
from django.db.backends.postgresql.base import DatabaseWrapper

from tests.apoio.concorrencia import (
    CONNECT_TIMEOUT_DAS_THREADS,
    TEMPO_LIMITE_LIMPEZA_PADRAO,
    LimpezaIncompleta,
    Resultado,
    TempoEsgotado,
    aguardar_limpezas_pendentes,
    executar_em_paralelo,
    limpezas_pendentes,
)
from tests.apoio.models import ModeloContador
from tests.conftest import PRAZO_PADRAO_DA_GUARDA, guarda_entre_testes

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]


def _conexoes_do_usuario_no_banco() -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE usename = current_user AND datname = current_database() "
            "AND pid <> pg_backend_pid()"
        )
        (total,) = cursor.fetchone()
    return int(total)


def _esperar_conexoes(esperado: int, prazo: float = 3.0) -> int:
    limite = time.monotonic() + prazo
    total = _conexoes_do_usuario_no_banco()
    while total != esperado and time.monotonic() < limite:
        time.sleep(0.05)
        total = _conexoes_do_usuario_no_banco()
    return total


@pytest.fixture
def contador() -> ModeloContador:
    return ModeloContador.objects.create(valor=0)


def test_utilitario_devolve_resultados_na_ordem_das_operacoes() -> None:  # A-1
    resultados = executar_em_paralelo(lambda _b: "a", lambda _b: "b")
    assert [r.valor for r in resultados] == ["a", "b"]
    assert all(isinstance(r, Resultado) and r.excecao is None for r in resultados)


def test_utilitario_cada_operacao_tem_conexao_propria() -> None:  # A-2
    def pid_da_conexao(_barreira: threading.Barrier) -> int:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            (pid,) = cursor.fetchone()
        return int(pid)

    r1, r2 = executar_em_paralelo(pid_da_conexao, pid_da_conexao)
    assert r1.valor != r2.valor
    assert r1.valor != _backend_pid_do_chamador()


def _backend_pid_do_chamador() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        (pid,) = cursor.fetchone()
    return int(pid)


def test_demonstracao_corrida_sem_trava_perde_atualizacao(contador: ModeloContador) -> None:  # A-3
    def incrementar_sem_trava(barreira: threading.Barrier) -> None:
        lido = ModeloContador.objects.get(pk=contador.pk).valor
        barreira.wait(timeout=5)
        ModeloContador.objects.filter(pk=contador.pk).update(valor=lido + 1)

    resultados = executar_em_paralelo(incrementar_sem_trava, incrementar_sem_trava)
    assert [r.excecao for r in resultados] == [None, None]
    contador.refresh_from_db()
    assert contador.valor == 1


def test_demonstracao_select_for_update_nao_perde_atualizacao(
    contador: ModeloContador,
) -> None:  # A-4
    def incrementar_com_trava(_barreira: threading.Barrier) -> None:
        with transaction.atomic():
            linha = ModeloContador.objects.select_for_update().get(pk=contador.pk)
            linha.valor += 1
            linha.save()

    for _ in range(20):
        ModeloContador.objects.filter(pk=contador.pk).update(valor=0)
        resultados = executar_em_paralelo(incrementar_com_trava, incrementar_com_trava)
        assert [r.excecao for r in resultados] == [None, None]
        contador.refresh_from_db()
        assert contador.valor == 2


def test_utilitario_devolve_excecao_de_uma_operacao_e_valor_da_outra() -> None:  # A-5
    def falha(_barreira: threading.Barrier) -> None:
        raise ValueError("de propósito")

    r1, r2 = executar_em_paralelo(falha, lambda _b: "ok")
    assert isinstance(r1.excecao, ValueError)
    assert r1.valor is None
    assert r2.valor == "ok"
    assert r2.excecao is None


def test_utilitario_tempo_esgotado_identifica_operacao_pendente() -> None:  # A-6
    nunca_completa = threading.Barrier(2)

    def presa(_barreira: threading.Barrier) -> None:
        nunca_completa.wait()

    inicio = time.monotonic()
    with pytest.raises(TempoEsgotado, match="presa"):
        executar_em_paralelo(presa, tempo_limite=2)
    assert time.monotonic() - inicio < 4
    nunca_completa.abort()  # libera a thread abandonada


@pytest.mark.parametrize("cenario", ["sucesso", "erro", "tempo_esgotado"])
def test_utilitario_nao_deixa_conexoes_abertas(cenario: str) -> None:  # A-7
    antes = _conexoes_do_usuario_no_banco()
    barreira_externa = threading.Barrier(2)

    def usa_banco(_barreira: threading.Barrier) -> int:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return 1

    def erra(_barreira: threading.Barrier) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        raise RuntimeError("falha")

    def presa(_barreira: threading.Barrier) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        barreira_externa.wait()

    operacoes: dict[str, tuple[Callable[[threading.Barrier], Any], ...]] = {
        "sucesso": (usa_banco, usa_banco),
        "erro": (usa_banco, erra),
        "tempo_esgotado": (usa_banco, presa),
    }
    if cenario == "tempo_esgotado":
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(*operacoes[cenario], tempo_limite=1)
        barreira_externa.abort()
    else:
        executar_em_paralelo(*operacoes[cenario])
    assert _esperar_conexoes(antes) == antes
    assert connections["default"].is_usable()


def test_utilitario_operacao_expirada_nao_reabre_conexao(contador: ModeloContador) -> None:  # R05
    liberar = threading.Event()
    terminou = threading.Event()
    registro: dict[str, Any] = {}

    def atrasada(_barreira: threading.Barrier) -> None:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                (registro["pid"],) = cursor.fetchone()
            liberar.wait(5)
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 42")
                    registro["resultado"] = cursor.fetchone()
            except BaseException as erro:
                registro["erro"] = erro
        finally:
            terminou.set()

    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(atrasada, tempo_limite=0.3)
        liberar.set()
        assert terminou.wait(5)
        assert "resultado" not in registro
        assert "erro" in registro
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE pid = %s", [registro["pid"]]
            )
            (total,) = cursor.fetchone()
        assert total == 0
    finally:
        liberar.set()


def test_utilitario_timeout_libera_trava_de_linha(contador: ModeloContador) -> None:  # R05
    segurando = threading.Event()
    liberar = threading.Event()

    def trava_e_espera(_barreira: threading.Barrier) -> None:
        with transaction.atomic():
            ModeloContador.objects.select_for_update().get(pk=contador.pk)
            segurando.set()
            liberar.wait(5)

    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(trava_e_espera, tempo_limite=0.5)
        assert segurando.is_set()
        with transaction.atomic():  # nowait: falha se a trava continuasse presa
            ModeloContador.objects.select_for_update(nowait=True).get(pk=contador.pk)
    finally:
        liberar.set()


def test_utilitario_timeout_durante_a_abertura_nao_deixa_conexao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # R05 (revalidação)
    liberar = threading.Event()
    entrou = threading.Event()
    registro: dict[str, Any] = {}
    original = DatabaseWrapper.ensure_connection

    def abertura_lenta(self: Any) -> None:
        original(self)
        if threading.current_thread().name.startswith("concorrencia-") and not entrou.is_set():
            registro["thread"] = threading.current_thread()
            registro["pid"] = self.connection.info.backend_pid
            entrou.set()
            liberar.wait(5)

    with connection.cursor() as cursor:  # conexão do chamador aberta antes do patch
        cursor.execute("SELECT 1")
    monkeypatch.setattr(DatabaseWrapper, "ensure_connection", abertura_lenta)
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(lambda _b: None, tempo_limite=0.3)
        assert entrou.is_set()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE pid = %s", [registro["pid"]]
            )
            (total,) = cursor.fetchone()
        assert total == 0
    finally:
        liberar.set()
        if "thread" in registro:
            registro["thread"].join(3)


def test_utilitario_abertura_tardia_nao_executa_a_operacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # R05 (revalidação)
    antes = _conexoes_do_usuario_no_banco()
    liberar = threading.Event()
    executou = threading.Event()
    registro: dict[str, Any] = {}
    original = DatabaseWrapper.ensure_connection

    def abertura_lenta(self: Any) -> None:
        if threading.current_thread().name.startswith("concorrencia-"):
            registro["thread"] = threading.current_thread()
            liberar.wait(5)  # abertura que só começa a concluir depois do tempo limite
        original(self)

    def operacao(_barreira: threading.Barrier) -> None:
        executou.set()

    monkeypatch.setattr(DatabaseWrapper, "ensure_connection", abertura_lenta)
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(operacao, tempo_limite=0.3)
        liberar.set()
        registro["thread"].join(3)
        assert not registro["thread"].is_alive()
        assert not executou.is_set()
        monkeypatch.undo()
        assert _esperar_conexoes(antes) == antes
    finally:
        liberar.set()


def test_utilitario_falha_na_abertura_vira_resultado_sem_vazar_conexao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # R05 (revalidação)
    antes = _conexoes_do_usuario_no_banco()

    def abertura_com_falha(self: Any) -> None:
        raise OperationalError("falha simulada na abertura")

    monkeypatch.setattr(DatabaseWrapper, "ensure_connection", abertura_com_falha)
    (resultado,) = executar_em_paralelo(lambda _b: "nunca")
    assert isinstance(resultado.excecao, OperationalError)
    assert resultado.valor is None
    monkeypatch.undo()
    assert _esperar_conexoes(antes) == antes


def test_utilitario_timeout_com_connect_ja_em_execucao_nao_deixa_conexao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # R05 (revalidação e7eec3c)
    liberar = threading.Event()
    abriu = threading.Event()
    executou = threading.Event()
    registro: dict[str, Any] = {}
    original = DatabaseWrapper.get_new_connection

    def abrir_com_retorno_lento(self: Any, params: Any) -> Any:
        bruta = original(self, params)
        if threading.current_thread().name.startswith("concorrencia-"):
            registro["thread"] = threading.current_thread()
            registro["pid"] = bruta.info.backend_pid
            registro["wrapper_sem_conexao"] = self.connection is None
            abriu.set()
            liberar.wait(5)
        return bruta

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    monkeypatch.setattr(DatabaseWrapper, "get_new_connection", abrir_com_retorno_lento)
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(lambda _b: executou.set(), tempo_limite=0.3)
        assert abriu.is_set()
        assert registro["wrapper_sem_conexao"]
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE pid = %s", [registro["pid"]]
            )
            (quantidade,) = cursor.fetchone()
        assert quantidade == 0
    finally:
        liberar.set()
        if "thread" in registro:
            registro["thread"].join(3)
            assert not registro["thread"].is_alive()
        assert not executou.is_set()


# Probe do revisor, copiado sem alteração de revalidação 6b7b9ab (A-12).
# Nome original: test_r05_timeout_durante_abertura
@pytest.mark.django_db(transaction=True)
def test_r05_revisor_timeout_durante_abertura(monkeypatch):  # type: ignore[no-untyped-def]
    liberar = threading.Event()
    entrou = threading.Event()
    registro = {}
    original = DatabaseWrapper.ensure_connection

    def abertura_lenta(self):  # type: ignore[no-untyped-def]
        original(self)
        if threading.current_thread().name.startswith("concorrencia-") and not entrou.is_set():
            registro["thread"] = threading.current_thread()
            registro["pid"] = self.connection.info.backend_pid
            entrou.set()
            liberar.wait(5)

    with connection.cursor() as c:
        c.execute("SELECT 1")
    monkeypatch.setattr(DatabaseWrapper, "ensure_connection", abertura_lenta)
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(lambda _b: None, tempo_limite=0.3)
        assert entrou.is_set()
        with connection.cursor() as c:
            c.execute("SELECT count(*) FROM pg_stat_activity WHERE pid=%s", [registro["pid"]])  # type: ignore[list-item]
            total = c.fetchone()[0]
        assert total == 0
    finally:
        liberar.set()
        if "thread" in registro:
            registro["thread"].join(3)


# Probe do revisor, copiado sem alteração de revalidação e7eec3c (A-11).
# Nome original: test_timeout_com_connect_ja_em_execucao
@pytest.mark.django_db(transaction=True)
@pytest.mark.concorrencia
def test_r05_revisor_connect_ja_em_execucao(monkeypatch):  # type: ignore[no-untyped-def]
    liberar = threading.Event()
    abriu = threading.Event()
    executou = threading.Event()
    registro = {}
    original = DatabaseWrapper.get_new_connection

    def abrir_com_retorno_lento(self, params):  # type: ignore[no-untyped-def]
        raw = original(self, params)
        if threading.current_thread().name.startswith("concorrencia-"):
            registro["thread"] = threading.current_thread()
            registro["pid"] = raw.info.backend_pid
            registro["wrapper_sem_conexao"] = self.connection is None  # type: ignore[assignment]
            abriu.set()
            liberar.wait(5)
        return raw

    with connection.cursor() as c:
        c.execute("SELECT 1")
    monkeypatch.setattr(DatabaseWrapper, "get_new_connection", abrir_com_retorno_lento)
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(lambda _b: executou.set(), tempo_limite=0.3)
        assert abriu.is_set()
        assert registro["wrapper_sem_conexao"]
        with connection.cursor() as c:
            c.execute("SELECT count(*) FROM pg_stat_activity WHERE pid=%s", [registro["pid"]])  # type: ignore[list-item]
            quantidade = c.fetchone()[0]
        assert quantidade == 0
    finally:
        liberar.set()
        if "thread" in registro:
            registro["thread"].join(3)
            assert not registro["thread"].is_alive()
        assert not executou.is_set()


# Probe do revisor, copiado sem alteração de revalidação 523cd9c (A-9).
# Nome original: test_abertura_em_andamento_conclui_apos_varredura
@pytest.mark.django_db(transaction=True)
@pytest.mark.concorrencia
def test_r05_revisor_abertura_em_andamento_conclui_apos_varredura(monkeypatch):  # type: ignore[no-untyped-def]
    permitir_abertura = threading.Event()
    permitir_retorno = threading.Event()
    entrou = threading.Event()
    abriu = threading.Event()
    executou = threading.Event()
    registro = {}
    original = DatabaseWrapper.get_new_connection

    def abertura_atrasada(self, params):  # type: ignore[no-untyped-def]
        if not threading.current_thread().name.startswith("concorrencia-"):
            return original(self, params)
        registro["thread"] = threading.current_thread()
        entrou.set()
        permitir_abertura.wait(5)
        raw = original(self, params)
        registro["pid"] = raw.info.backend_pid
        registro["nome"] = params["application_name"]
        abriu.set()
        permitir_retorno.wait(5)
        return raw

    with connection.cursor() as c:
        c.execute("SELECT 1")
    monkeypatch.setattr(DatabaseWrapper, "get_new_connection", abertura_atrasada)
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(lambda _b: executou.set(), tempo_limite=0.3)
        assert entrou.is_set()
        # O cleanup no servidor ja terminou; a chamada connect original ainda esta em curso.
        permitir_abertura.set()
        assert abriu.wait(3)
        with connection.cursor() as c:
            c.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE pid=%s AND application_name=%s",
                [registro["pid"], registro["nome"]],  # type: ignore[list-item]
            )
            restantes = c.fetchone()[0]
        assert restantes == 0
    finally:
        permitir_abertura.set()
        permitir_retorno.set()
        if "thread" in registro:
            registro["thread"].join(3)
            assert not registro["thread"].is_alive()
        assert not executou.is_set()


# --- Correção R05: critérios A-8 a A-17 (spec.md, "Correção R05") ---------------------------


def _sessoes_por_nome(nome: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE application_name = %s", [nome])
        (total,) = cursor.fetchone()
    return int(total)


def test_r05_antes_da_abertura_a_operacao_nao_abre_conexao_nem_executa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-8
    liberar = threading.Event()
    executou = threading.Event()
    registro: dict[str, Any] = {}
    original = DatabaseWrapper.ensure_connection

    def pausa_antes_de_abrir(self: Any) -> None:
        if threading.current_thread().name.startswith("concorrencia-"):
            registro["thread"] = threading.current_thread()
            registro["nome"] = self.settings_dict["OPTIONS"]["application_name"]
            liberar.wait(5)
        original(self)

    monkeypatch.setattr(DatabaseWrapper, "ensure_connection", pausa_antes_de_abrir)
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(lambda _b: executou.set(), tempo_limite=0.3)
        assert _sessoes_por_nome(registro["nome"]) == 0
        liberar.set()
        registro["thread"].join(3)
        assert not registro["thread"].is_alive()
        assert _sessoes_por_nome(registro["nome"]) == 0  # a abertura foi recusada
        assert not executou.is_set()
    finally:
        liberar.set()


def test_r05_abertura_lenta_liberada_por_timer_termina_sem_sessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-10 (versão rápida do A-9)
    liberar = threading.Event()
    executou = threading.Event()
    registro: dict[str, Any] = {}
    original = DatabaseWrapper.get_new_connection

    def abertura_atrasada(self: Any, params: Any) -> Any:
        if not threading.current_thread().name.startswith("concorrencia-"):
            return original(self, params)
        registro["thread"] = threading.current_thread()
        registro["nome"] = params["application_name"]
        liberar.wait(5)
        return original(self, params)

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    monkeypatch.setattr(DatabaseWrapper, "get_new_connection", abertura_atrasada)
    temporizador = threading.Timer(0.5, liberar.set)
    temporizador.start()
    inicio = time.monotonic()
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(
                lambda _b: executou.set(), tempo_limite=0.2, tempo_limite_limpeza=10
            )
        decorrido = time.monotonic() - inicio
        assert 0.5 <= decorrido < 10.2
        assert _sessoes_por_nome(registro["nome"]) == 0
    finally:
        temporizador.cancel()
        liberar.set()
        if "thread" in registro:
            registro["thread"].join(3)
            assert not registro["thread"].is_alive()
        assert not executou.is_set()


def test_r05_erro_na_abertura_com_tempo_esgotado_e_sem_sessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-14 (com tempo esgotado; sem tempo esgotado já coberto)
    liberar = threading.Event()
    registro: dict[str, Any] = {}

    original = DatabaseWrapper.get_new_connection

    def abertura_que_falha(self: Any, params: Any) -> Any:
        if not threading.current_thread().name.startswith("concorrencia-"):
            return original(self, params)
        registro["nome"] = params["application_name"]
        liberar.wait(5)
        raise OperationalError("falha simulada na abertura")

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    monkeypatch.setattr(DatabaseWrapper, "get_new_connection", abertura_que_falha)
    temporizador = threading.Timer(0.5, liberar.set)
    temporizador.start()
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(lambda _b: "nunca", tempo_limite=0.2, tempo_limite_limpeza=10)
        assert _sessoes_por_nome(registro["nome"]) == 0
    finally:
        temporizador.cancel()
        liberar.set()


def test_r05_limpeza_incompleta_quando_a_abertura_passa_do_prazo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-15 e A-16
    liberar = threading.Event()
    executou = threading.Event()
    registro: dict[str, Any] = {}
    original = DatabaseWrapper.get_new_connection

    def abertura_pausada(self: Any, params: Any) -> Any:
        if not threading.current_thread().name.startswith("concorrencia-"):
            return original(self, params)
        registro["thread"] = threading.current_thread()
        registro["nome"] = params["application_name"]
        liberar.wait(10)
        return original(self, params)

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    monkeypatch.setattr(DatabaseWrapper, "get_new_connection", abertura_pausada)
    try:
        inicio = time.monotonic()
        with pytest.raises(LimpezaIncompleta) as erro:  # não é TempoEsgotado
            executar_em_paralelo(
                lambda _b: executou.set(), tempo_limite=0.2, tempo_limite_limpeza=0.5
            )
        decorrido = time.monotonic() - inicio
        assert 0.6 <= decorrido < 2.0
        assert "ABRINDO" in str(erro.value)
        assert "<lambda>" in str(erro.value)
        assert not isinstance(erro.value, TempoEsgotado)

        # A-16: a pendência está registrada; com a abertura ainda pausada a guarda acusa.
        with pytest.raises(LimpezaIncompleta, match="ABRINDO"):
            aguardar_limpezas_pendentes(0.2)
        with pytest.raises(pytest.fail.Exception, match="<lambda>"):
            guarda_entre_testes(prazo=0.2)

        # Liberada a abertura, a guarda termina com 0 sessões e esvazia o registro.
        liberar.set()
        aguardar_limpezas_pendentes(10)
        assert _sessoes_por_nome(registro["nome"]) == 0
        assert limpezas_pendentes() == 0
        guarda_entre_testes()  # sem pendência: não faz nada
        registro["thread"].join(3)
        assert not registro["thread"].is_alive()
        assert not executou.is_set()
    finally:
        liberar.set()
        monkeypatch.undo()
        aguardar_limpezas_pendentes(10)


@pytest.mark.parametrize("limpeza", [0.5, 1, 10.5, None])
def test_r05_conexao_do_utilitario_tem_nome_exclusivo_e_connect_timeout_fixo(
    limpeza: float | None,
) -> None:  # A-17 (revisto em 2026-10-16, R06)
    def descrever(_barreira: threading.Barrier) -> tuple[str, Any]:
        with connection.cursor() as cursor:
            cursor.execute("SHOW application_name")
            (nome,) = cursor.fetchone()
        return nome, connection.get_connection_params()["connect_timeout"]

    argumentos = {} if limpeza is None else {"tempo_limite_limpeza": limpeza}
    r1, r2 = executar_em_paralelo(descrever, descrever, **argumentos)
    assert r1.excecao is None
    assert r2.excecao is None
    nome1, timeout1 = r1.valor
    nome2, timeout2 = r2.valor
    assert nome1.startswith("concorrencia-")
    assert nome1 != nome2
    assert timeout1 == CONNECT_TIMEOUT_DAS_THREADS
    assert timeout2 == CONNECT_TIMEOUT_DAS_THREADS


def test_r05_connect_timeout_das_threads_e_uma_constante_fixa_coerente() -> None:  # A-17
    assert isinstance(CONNECT_TIMEOUT_DAS_THREADS, int)
    assert not isinstance(CONNECT_TIMEOUT_DAS_THREADS, bool)
    assert CONNECT_TIMEOUT_DAS_THREADS > 0
    assert CONNECT_TIMEOUT_DAS_THREADS < TEMPO_LIMITE_LIMPEZA_PADRAO
    assert CONNECT_TIMEOUT_DAS_THREADS < PRAZO_PADRAO_DA_GUARDA


# --- Correção E07-R06: critérios A-19 a A-23 (spec.md, "Correção E07-R06") -------------------

BANCOS = ["default", "simulador_pagamentos"]
ALIAS_DO_SIMULADOR = "simulador_pagamentos"


def _criar_cobranca_pendente() -> Any:
    from datetime import timedelta
    from decimal import Decimal

    from apps.nucleo.tempo import agora
    from apps.pagamentos.provedor import NovaCobranca, obter_provedor

    return (
        obter_provedor()
        .criar_cobranca(
            NovaCobranca(
                "probe", "ref-probe", Decimal("45.90"), "Teste", agora() + timedelta(days=1)
            )
        )
        .pagamento
    )


def _situacao_no_provedor(id_externo: str) -> Any:
    from apps.pagamentos.provedor import obter_provedor

    return obter_provedor().consultar_pagamento(id_externo).situacao


def _aprovar_pelo_simulador(id_externo: str) -> None:
    from apps.simulador_pagamentos import controle

    controle.aprovar(id_externo)


def _sessoes_com_nome_parecido(padrao: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE application_name LIKE %s", [padrao]
        )
        (total,) = cursor.fetchone()
    return int(total)


def _e_do_utilitario() -> bool:
    return threading.current_thread().name.startswith("concorrencia-")


@pytest.mark.usefixtures("simulador_pagamentos")
@pytest.mark.django_db(transaction=True, databases=BANCOS)
def test_e07_r06_timeout_limpa_tambem_a_conexao_do_simulador():  # type: ignore[no-untyped-def]  # A-19
    # Prova do revisor, copiada sem alteração (revalidação 636a94c da E07).
    # Nome original: test_timeout_limpa_tambem_a_conexao_do_simulador
    from apps.pagamentos.provedor import obter_provedor
    from apps.simulador_pagamentos import controle as sim
    from apps.simulador_pagamentos.models import CobrancaSimulada

    p = _criar_cobranca_pendente()
    terminou = threading.Event()
    ids = {}

    def bloqueada(barreira):  # type: ignore[no-untyped-def]
        try:
            with connections["simulador_pagamentos"].cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                ids["simulador"] = cursor.fetchone()[0]
            sim.aprovar(p.id_externo)
        finally:
            connections.close_all()
            terminou.set()

    with transaction.atomic(using="simulador_pagamentos"):
        CobrancaSimulada.objects.select_for_update().get(chave_idempotencia="probe")
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(bloqueada, tempo_limite=1, tempo_limite_limpeza=2)
        assert "simulador" in ids
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE pid=%s", [ids["simulador"]])
            restantes = cursor.fetchone()[0]
        pendencias = limpezas_pendentes()
    # Liberar a trava e esperar o encerramento garante limpeza da própria prova.
    assert terminou.wait(5), "thread da prova nao terminou apos liberar a trava"
    situacao = obter_provedor().consultar_pagamento(p.id_externo).situacao
    assert restantes == 0 and situacao == "pendente", {  # noqa: PT018 (prova do revisor, literal)
        "sessoes_apos_timeout": restantes,
        "guarda": pendencias,
        "situacao_depois": str(situacao),
    }


def _pausar_abertura_do_simulador(
    monkeypatch: pytest.MonkeyPatch, liberar: threading.Event, registro: dict[str, Any]
) -> None:
    """Pausa só a abertura do wrapper do simulador, nas threads do utilitário, e registra os
    nomes de todas as aberturas dessas threads."""
    original = DatabaseWrapper.get_new_connection
    registro["nomes"] = []
    registro["aberturas_do_simulador"] = 0
    registro["entrou"] = threading.Event()

    def abertura(self: Any, params: Any) -> Any:
        if not _e_do_utilitario():
            return original(self, params)
        registro["nomes"].append(params.get("application_name"))
        if self.alias != ALIAS_DO_SIMULADOR:
            return original(self, params)
        registro["aberturas_do_simulador"] += 1
        registro["thread"] = threading.current_thread()
        registro["entrou"].set()
        liberar.wait(10)
        return original(self, params)

    monkeypatch.setattr(DatabaseWrapper, "get_new_connection", abertura)


@pytest.mark.usefixtures("simulador_pagamentos")
@pytest.mark.django_db(transaction=True, databases=BANCOS)
def test_e07_r06_abertura_do_simulador_terminando_no_prazo_nao_executa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-20
    p = _criar_cobranca_pendente()
    liberar = threading.Event()
    registro: dict[str, Any] = {}
    _pausar_abertura_do_simulador(monkeypatch, liberar, registro)
    temporizador = threading.Timer(0.5, liberar.set)
    temporizador.start()
    inicio = time.monotonic()
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(
                lambda _b: _aprovar_pelo_simulador(p.id_externo),
                tempo_limite=0.2,
                tempo_limite_limpeza=10,
            )
        decorrido = time.monotonic() - inicio
        assert registro["entrou"].is_set()
        assert decorrido >= 0.5
        assert _sessoes_com_nome_parecido("concorrencia-%") == 0
        assert _situacao_no_provedor(p.id_externo) == "pendente"
    finally:
        temporizador.cancel()
        liberar.set()
        if "thread" in registro:
            registro["thread"].join(5)
            assert not registro["thread"].is_alive()
    assert _situacao_no_provedor(p.id_externo) == "pendente"


@pytest.mark.usefixtures("simulador_pagamentos")
@pytest.mark.django_db(transaction=True, databases=BANCOS)
def test_e07_r06_abertura_do_simulador_alem_do_prazo_vira_limpeza_incompleta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-21
    p = _criar_cobranca_pendente()
    liberar = threading.Event()
    registro: dict[str, Any] = {}
    _pausar_abertura_do_simulador(monkeypatch, liberar, registro)

    def aprovar_pelo_simulador(_barreira: threading.Barrier) -> None:
        _aprovar_pelo_simulador(p.id_externo)

    try:
        with pytest.raises(LimpezaIncompleta) as erro:  # e não TempoEsgotado
            executar_em_paralelo(aprovar_pelo_simulador, tempo_limite=0.2, tempo_limite_limpeza=0.5)
        mensagem = str(erro.value)
        assert not isinstance(erro.value, TempoEsgotado)
        assert "aprovar_pelo_simulador" in mensagem
        assert ALIAS_DO_SIMULADOR in mensagem
        assert "ABRINDO" in mensagem
        assert limpezas_pendentes() == 1

        liberar.set()
        aguardar_limpezas_pendentes(30)
        registro["thread"].join(5)
        assert not registro["thread"].is_alive()
        nomes = [nome for nome in registro["nomes"] if nome]
        assert len(nomes) == 2  # default e simulador
        for nome in nomes:
            assert _sessoes_por_nome(nome) == 0
        assert limpezas_pendentes() == 0
        assert _situacao_no_provedor(p.id_externo) == "pendente"
    finally:
        liberar.set()
        monkeypatch.undo()
        aguardar_limpezas_pendentes(10)


@pytest.mark.usefixtures("simulador_pagamentos")
@pytest.mark.django_db(transaction=True, databases=BANCOS)
def test_e07_r06_abertura_do_simulador_depois_do_tempo_esgotado_e_recusada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-22
    p = _criar_cobranca_pendente()
    liberar = threading.Event()
    registro: dict[str, Any] = {}
    _pausar_abertura_do_simulador(monkeypatch, liberar, registro)
    espera = threading.Event()
    terminou = threading.Event()
    erros: list[BaseException] = []

    def abre_depois(_barreira: threading.Barrier) -> None:
        try:
            espera.wait(10)
            try:
                _aprovar_pelo_simulador(p.id_externo)
            except BaseException as erro:
                erros.append(erro)
        finally:
            terminou.set()

    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(abre_depois, tempo_limite=0.2, tempo_limite_limpeza=5)
        espera.set()
        liberar.set()  # no código antigo a abertura pausada seguiria; aqui ela não pode ocorrer
        assert terminou.wait(5)
        assert len(erros) == 1
        assert isinstance(erros[0], TempoEsgotado)
        assert registro["aberturas_do_simulador"] == 0
        assert _sessoes_com_nome_parecido("concorrencia-%-simulador_pagamentos") == 0
        assert _situacao_no_provedor(p.id_externo) == "pendente"
    finally:
        espera.set()
        liberar.set()


def _descrever_os_dois_aliases(_barreira: threading.Barrier) -> dict[str, tuple[str, Any]]:
    descricao = {}
    for alias in BANCOS:
        with connections[alias].cursor() as cursor:
            cursor.execute("SHOW application_name")
            (nome,) = cursor.fetchone()
        descricao[alias] = (nome, connections[alias].get_connection_params()["connect_timeout"])
    return descricao


@pytest.mark.django_db(transaction=True, databases=BANCOS)
def test_e07_r06_cada_alias_tem_nome_exclusivo_e_connect_timeout_fixo() -> None:  # A-23 (i)
    r1, r2 = executar_em_paralelo(_descrever_os_dois_aliases, _descrever_os_dois_aliases)
    assert r1.excecao is None
    assert r2.excecao is None
    nomes = []
    for indice, resultado in enumerate((r1, r2)):
        for alias in BANCOS:
            nome, tempo = resultado.valor[alias]
            assert re.fullmatch(rf"concorrencia-[0-9a-f]{{12}}-{indice}-{alias}", nome), nome
            assert tempo == CONNECT_TIMEOUT_DAS_THREADS
            nomes.append(nome)
    assert len(set(nomes)) == 4
    assert len({nome.rsplit("-", 2)[0] for nome in nomes}) == 1  # mesmo prefixo da chamada


@pytest.mark.django_db(transaction=True, databases=BANCOS)
@pytest.mark.parametrize("campo", ["HOST", "PORT", "USER"])
def test_e07_r06_alias_em_outro_servidor_e_recusado_antes_de_iniciar(
    monkeypatch: pytest.MonkeyPatch, campo: str
) -> None:  # A-23 (ii)
    executou = threading.Event()
    monkeypatch.setitem(connections.settings[ALIAS_DO_SIMULADOR], campo, "outro")
    with pytest.raises(ValueError, match=ALIAS_DO_SIMULADOR):
        executar_em_paralelo(lambda _b: executou.set(), lambda _b: executou.set())
    assert not executou.is_set()
    assert not [t for t in threading.enumerate() if t.name.startswith("concorrencia-")]
