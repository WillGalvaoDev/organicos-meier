"""Apoio das corridas da correção da E09 (E09-01, "Padrão das corridas desta correção").

A operação A pausa num ponto; a operação B começa; um controlador libera A quando acontece a
primeira destas três coisas: B terminou, B está esperando uma trava ou passou o tempo limite de
15 s. O teste nunca espera só pelo fim de B, porque, depois da correção, B espera a trava de A.
O monkeypatch só pausa: não retira trava, validação nem efeito.
"""

import threading
import time
from collections.abc import Callable
from typing import Any

import pytest
from django.db import transaction

from apps.financeiro import livro
from tests.apoio.concorrencia import Resultado, executar_em_paralelo
from tests.apoio.trava import outra_conexao_esperando

TEMPO_LIMITE = 15.0


class Corrida:
    def __init__(self) -> None:
        self.a_pausou = threading.Event()
        self.liberar = threading.Event()
        self.b_terminou = threading.Event()
        self._local = threading.local()

    # --- os pontos de pausa -------------------------------------------------------------------

    def pausar_a(self) -> None:
        """Chamada no ponto de pausa: só a thread de A pausa, e só da primeira vez."""
        if getattr(self._local, "e_a", False) and not self.a_pausou.is_set():
            self.a_pausou.set()
            assert self.liberar.wait(TEMPO_LIMITE + 10), "ninguém liberou a operação A"

    def depois_de(self, monkeypatch: pytest.MonkeyPatch, alvo: Any, nome: str) -> None:
        """Faz `alvo.nome(...)` pausar A logo depois de devolver."""
        original = getattr(alvo, nome)

        def com_pausa(*args: Any, **kwargs: Any) -> Any:
            resultado = original(*args, **kwargs)
            self.pausar_a()
            return resultado

        monkeypatch.setattr(alvo, nome, com_pausa)

    def antes_de(self, monkeypatch: pytest.MonkeyPatch, alvo: Any, nome: str) -> None:
        """Faz `alvo.nome(...)` pausar A logo antes de executar."""
        original = getattr(alvo, nome)

        def com_pausa(*args: Any, **kwargs: Any) -> Any:
            self.pausar_a()
            return original(*args, **kwargs)

        monkeypatch.setattr(alvo, nome, com_pausa)

    # --- as operações ---------------------------------------------------------------------------

    def operacao_a(self, trabalho: Callable[[], Any]) -> Callable[[Any], Any]:
        def executa(barreira: Any) -> Any:
            barreira.wait(timeout=10)
            self._local.e_a = True
            try:
                with transaction.atomic():
                    return trabalho()
            finally:
                self.a_pausou.set()  # se A terminou sem pausar, ninguém fica esperando

        return executa

    def operacao_b(
        self, trabalho: Callable[[], Any], *, atomica: bool = True
    ) -> Callable[[Any], Any]:
        """`atomica=False` roda B sem a transação externa, como uma rota (`ATOMIC_REQUESTS` é
        falso): a operação abre as suas, e a consulta ao provedor não segura trava até o fim."""

        def executa(barreira: Any) -> Any:
            barreira.wait(timeout=10)
            assert self.a_pausou.wait(TEMPO_LIMITE), "A não chegou ao ponto de pausa"
            try:
                if not atomica:
                    return trabalho()
                with transaction.atomic():
                    return trabalho()
            finally:
                self.b_terminou.set()

        return executa

    def controlador(self) -> Callable[[Any], None]:
        def executa(barreira: Any) -> None:
            barreira.wait(timeout=10)
            try:
                assert self.a_pausou.wait(TEMPO_LIMITE), "A não chegou ao ponto de pausa"
                limite = time.monotonic() + TEMPO_LIMITE
                while time.monotonic() < limite:
                    if self.b_terminou.is_set() or outra_conexao_esperando():
                        break
                    time.sleep(0.05)
            finally:
                self.liberar.set()

        return executa

    def rodar(
        self, a: Callable[[], Any], b: Callable[[], Any], *, b_atomica: bool = True
    ) -> tuple[Resultado, Resultado]:
        """Roda A (que pausa) e B juntas; devolve os resultados de A e de B."""
        resultados = executar_em_paralelo(
            self.operacao_a(a),
            self.operacao_b(b, atomica=b_atomica),
            self.controlador(),
            tempo_limite=60,
        )
        assert resultados[2].excecao is None, repr(resultados[2].excecao)
        return resultados[0], resultados[1]


def pausar_depois_da_primeira_trava(monkeypatch: pytest.MonkeyPatch, esperar: float = 3.0) -> None:
    """Cada thread pausa logo depois da sua primeira trava de conta, até a outra também ter a
    sua (ou até `esperar` s: a que espera a trava da outra nunca chega à pausa). Troca a função de
    trava do livro e a de cada módulo do financeiro que a tenha importado."""
    import importlib
    import pkgutil

    import apps.financeiro as pacote

    barreira = threading.Barrier(2)
    local = threading.local()
    original = livro._travar_conta

    def travar_e_pausar(pk: int) -> Any:
        resultado = original(pk)
        if not getattr(local, "pausou", False):
            local.pausou = True
            try:
                barreira.wait(timeout=esperar)
            except threading.BrokenBarrierError:
                pass
        return resultado

    for info in pkgutil.iter_modules(pacote.__path__):
        modulo = importlib.import_module(f"apps.financeiro.{info.name}")
        if getattr(modulo, "_travar_conta", None) is original:
            monkeypatch.setattr(modulo, "_travar_conta", travar_e_pausar)
