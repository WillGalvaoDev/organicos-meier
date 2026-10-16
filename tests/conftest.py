from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest
import time_machine

from apps.nucleo.tempo import InstanteSemFuso
from tests.apoio.concorrencia import (
    LimpezaIncompleta,
    aguardar_limpezas_pendentes,
    limpezas_pendentes,
)


class RelogioControlado:
    """Controla `agora()` durante o teste: `congelar` fixa o instante, `avancar` o desloca."""

    def __init__(self) -> None:
        self._viagem: Any = None
        self._coordenadas: Any = None

    def congelar(self, instante: datetime) -> None:
        if instante.tzinfo is None or instante.utcoffset() is None:
            raise InstanteSemFuso("o relógio só pode ser congelado em instante com fuso")
        self.parar()
        self._viagem = time_machine.travel(instante, tick=False)
        self._coordenadas = self._viagem.start()

    def avancar(self, duracao: timedelta) -> None:
        if self._coordenadas is None:
            raise RuntimeError("congele o relógio antes de avançar")
        self._coordenadas.shift(duracao)

    def parar(self) -> None:
        if self._viagem is not None:
            self._viagem.stop()
            self._viagem = None
            self._coordenadas = None


@pytest.fixture
def relogio() -> Iterator[RelogioControlado]:
    controle = RelogioControlado()
    try:
        yield controle
    finally:
        controle.parar()


PRAZO_PADRAO_DA_GUARDA = 30.0


def guarda_entre_testes(prazo: float = PRAZO_PADRAO_DA_GUARDA) -> None:
    """Resolve limpezas de conexão pendentes de um teste anterior (E01-05, correção R05).

    Só age se `executar_em_paralelo` levantou `LimpezaIncompleta`. Se ainda restar sessão,
    falha o teste atual, citando a operação de origem, para que ninguém siga com conexão herdada.
    """
    if limpezas_pendentes() == 0:
        return
    try:
        aguardar_limpezas_pendentes(prazo)
    except LimpezaIncompleta as erro:
        pytest.fail(f"conexão herdada de um teste anterior: {erro}", pytrace=False)


@pytest.fixture(autouse=True)
def _guarda_de_conexoes(django_db_blocker: Any) -> None:
    if limpezas_pendentes():
        with django_db_blocker.unblock():
            guarda_entre_testes()


@pytest.fixture(autouse=True)
def _cache_limpo() -> None:
    """Os limites de requisição do allauth usam o cache: cada teste começa do zero."""
    from django.core.cache import cache

    cache.clear()
