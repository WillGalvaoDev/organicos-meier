from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest
import time_machine

from apps.nucleo.tempo import InstanteSemFuso


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
