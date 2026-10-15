"""Relógio do servidor e comparação de prazos (E01-03).

Instantes em UTC com fuso; exibição em America/Sao_Paulo. O código de negócio obtém o
instante atual somente por `agora()`. Nunca usa o `now()` do banco.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

FUSO_DA_OPERACAO = ZoneInfo("America/Sao_Paulo")


class InstanteSemFuso(Exception):
    """Recebido um `datetime` sem fuso. Instantes precisam ser inequívocos."""


def _com_fuso(instante: datetime) -> datetime:
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise InstanteSemFuso("datetime sem fuso não é aceito")
    return instante


def _em_utc(instante: datetime) -> datetime:
    """Instante absoluto em UTC. A comparação nunca depende do fuso nem da dobra (fold)."""
    return _com_fuso(instante).astimezone(UTC)


def agora() -> datetime:
    """Instante atual do servidor, em UTC e com fuso."""
    return datetime.now(UTC)


def somar_horas(instante: datetime, horas: int) -> datetime:
    """Soma uma duração absoluta em horas, em UTC. Não depende de horário de verão."""
    return _em_utc(instante) + timedelta(hours=horas)


def prazo_encerrado(instante: datetime, limite: datetime) -> bool:
    """Limite exclusivo: verdadeiro quando `instante >= limite` (janela [início, limite))."""
    return _em_utc(instante) >= _em_utc(limite)


def ate_o_limite(instante: datetime, limite: datetime) -> bool:
    """Limite inclusivo: verdadeiro quando `instante <= limite`."""
    return _em_utc(instante) <= _em_utc(limite)


def no_fuso_da_operacao(instante: datetime) -> datetime:
    """Converte para America/Sao_Paulo, sem alterar o instante."""
    return _com_fuso(instante).astimezone(FUSO_DA_OPERACAO)
