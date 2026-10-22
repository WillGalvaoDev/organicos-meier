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


@pytest.fixture
def webauthn(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Dublê determinístico da cerimônia WebAuthn (E02-03)."""
    from tests.apoio.webauthn_falso import instalar

    return instalar(monkeypatch)


@pytest.fixture
def simulador_whatsapp() -> Iterator[Any]:
    """O simulador de WhatsApp (E04-04), reiniciado antes e depois de cada teste."""
    from apps.notificacoes.whatsapp import SIMULADOR

    SIMULADOR.reiniciar()
    yield SIMULADOR
    SIMULADOR.reiniciar()


@pytest.fixture
def simulador_pagamentos() -> Iterator[Any]:
    """O controle do simulador de pagamentos (E07-01); o plano de falhas é reiniciado antes e
    depois de cada teste."""
    from apps.simulador_pagamentos import controle

    controle.reiniciar()
    yield controle
    controle.reiniciar()


BANCOS_DO_SIMULADOR = ["default", "simulador_pagamentos"]
PREFIXOS_COM_SIMULADOR = (
    "test_pagamentos_",
    "test_pedidos_",
    "test_simulador_pagamentos_",
    "test_financeiro_",
    "test_cenario_30_",
    "test_cenario_31_",
    "test_cenario_32_",
    "test_cenario_33_",
    "test_cenario_40_",
    "test_cenario_39_",
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Os testes de pagamentos usam o simulador, que tem conexão própria (E07-R03): declaram
    os dois bancos sem mudar o resto do marcador `django_db` de cada teste."""
    for item in items:
        if not item.path.name.startswith(PREFIXOS_COM_SIMULADOR):
            continue
        marcador = item.get_closest_marker("django_db")
        if marcador is None or marcador.kwargs.get("databases") is not None:
            continue
        argumentos = dict(marcador.kwargs)
        if marcador.args:
            argumentos.setdefault("transaction", marcador.args[0])
        item.add_marker(pytest.mark.django_db(databases=BANCOS_DO_SIMULADOR, **argumentos), False)
