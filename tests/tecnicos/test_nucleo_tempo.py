"""E01-03: relógio do servidor e fronteiras de prazo (acceptance A-1 a A-8)."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from apps.nucleo.tempo import (
    InstanteSemFuso,
    agora,
    ate_o_limite,
    no_fuso_da_operacao,
    prazo_encerrado,
    somar_horas,
)

T = datetime(2026, 10, 14, 15, 0, 0, 0, tzinfo=UTC)
MS = timedelta(milliseconds=1)
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def test_agora_devolve_utc_com_fuso() -> None:  # A-1
    instante = agora()
    assert instante.tzinfo is not None
    assert instante.utcoffset() == timedelta(0)
    assert instante.tzinfo is UTC


def test_agora_reflete_relogio_congelado(relogio: Any) -> None:  # A-2
    relogio.congelar(T)
    assert agora() == T
    assert agora() == T  # congelado: não avança sozinho


def test_agora_avanca_com_o_relogio_controlado(relogio: Any) -> None:  # A-3
    relogio.congelar(T)
    relogio.avancar(timedelta(hours=24))
    assert agora() == T + timedelta(hours=24)


def test_agora_congelar_aceita_so_instante_com_fuso(relogio: Any) -> None:
    with pytest.raises(InstanteSemFuso):
        relogio.congelar(datetime(2026, 10, 14, 15, 0))  # noqa: DTZ001


def test_fronteira_prazo_encerrado_exclusivo() -> None:  # A-4
    limite = T + timedelta(hours=24)
    assert prazo_encerrado(limite - MS, limite) is False
    assert prazo_encerrado(limite, limite) is True
    assert prazo_encerrado(limite + MS, limite) is True


def test_fronteira_ate_o_limite_inclusivo() -> None:  # A-5
    limite = T + timedelta(hours=48)
    assert ate_o_limite(limite - MS, limite) is True
    assert ate_o_limite(limite, limite) is True
    assert ate_o_limite(limite + MS, limite) is False


def test_fronteira_comparacoes_usam_microssegundos() -> None:
    limite = T + timedelta(hours=24)
    assert prazo_encerrado(limite - timedelta(microseconds=1), limite) is False
    assert ate_o_limite(limite + timedelta(microseconds=1), limite) is False


def test_fronteira_funciona_entre_fusos_diferentes() -> None:
    limite = T + timedelta(hours=24)
    mesmo_instante_em_sp = limite.astimezone(SAO_PAULO)
    assert prazo_encerrado(mesmo_instante_em_sp, limite) is True
    assert ate_o_limite(mesmo_instante_em_sp, limite) is True


def test_fuso_somar_24h_atravessa_meia_noite_em_sao_paulo() -> None:  # A-6
    inicio = datetime(2026, 10, 14, 23, 30, tzinfo=timezone(timedelta(hours=-3))).astimezone(UTC)
    fim = somar_horas(inicio, 24)
    assert fim - inicio == timedelta(hours=24)
    local = no_fuso_da_operacao(fim)
    assert local == datetime(2026, 10, 15, 23, 30, tzinfo=SAO_PAULO)
    assert (local.year, local.month, local.day, local.hour, local.minute) == (2026, 10, 15, 23, 30)


def test_fuso_somar_horas_e_duracao_absoluta_no_horario_de_verao() -> None:
    # Instante na véspera de uma mudança de offset em outro fuso civil: 24h continuam 24h.
    inicio = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)
    assert somar_horas(inicio, 24) == datetime(2026, 3, 8, 12, 0, tzinfo=UTC)


def test_fuso_exibicao_em_sao_paulo_preserva_o_instante() -> None:  # A-7
    local = no_fuso_da_operacao(T)
    assert local.tzinfo == SAO_PAULO
    assert local == T
    assert local.hour == 12  # 15:00 UTC = 12:00 -03:00


@pytest.mark.parametrize(
    "chamada",
    [
        lambda naive: somar_horas(naive, 1),
        lambda naive: prazo_encerrado(naive, T),
        lambda naive: prazo_encerrado(T, naive),
        lambda naive: ate_o_limite(naive, T),
        lambda naive: ate_o_limite(T, naive),
        lambda naive: no_fuso_da_operacao(naive),
    ],
)
def test_fuso_recusa_instante_sem_fuso(chamada: Any) -> None:  # A-8
    naive = datetime(2026, 10, 14, 15, 0)  # noqa: DTZ001
    with pytest.raises(InstanteSemFuso):
        chamada(naive)


def test_fronteira_instantes_civis_repetidos_comparam_em_utc() -> None:  # R03
    # Fim do horário de verão em São Paulo: 23:30 ocorre duas vezes (fold 0: -02, fold 1: -03).
    primeiro = datetime(2019, 2, 16, 23, 30, tzinfo=SAO_PAULO, fold=0)
    segundo = datetime(2019, 2, 16, 23, 30, tzinfo=SAO_PAULO, fold=1)
    assert segundo.astimezone(UTC) - primeiro.astimezone(UTC) == timedelta(hours=1)
    assert prazo_encerrado(primeiro, segundo) is False
    assert prazo_encerrado(segundo, primeiro) is True
    assert ate_o_limite(primeiro, segundo) is True
    assert ate_o_limite(segundo, primeiro) is False


def test_fuso_somar_horas_atravessa_transicao_civil_com_24h_exatas() -> None:  # R03
    inicio = datetime(2019, 2, 16, 22, 0, tzinfo=SAO_PAULO)  # -02, antes do fim do verão
    fim = somar_horas(inicio, 24)
    assert fim - inicio.astimezone(UTC) == timedelta(hours=24)
    assert no_fuso_da_operacao(fim) == datetime(2019, 2, 17, 21, 0, tzinfo=SAO_PAULO)
