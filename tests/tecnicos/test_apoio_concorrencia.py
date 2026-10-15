"""E01-05: utilitário de testes de concorrência (acceptance A-1 a A-7)."""

import threading
import time
from collections.abc import Callable
from typing import Any

import pytest
from django.db import OperationalError, connection, connections, transaction
from django.db.backends.postgresql.base import DatabaseWrapper

from tests.apoio.concorrencia import Resultado, TempoEsgotado, executar_em_paralelo
from tests.apoio.models import ModeloContador

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
