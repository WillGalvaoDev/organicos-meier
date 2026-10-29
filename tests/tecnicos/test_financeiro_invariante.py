"""E09-07: o invariante do saldo do provedor (acceptance A-7 a A-10 e A-22)."""

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction

from apps.financeiro.alertas import abrir_alerta
from apps.financeiro.invariante import ResultadoDoInvariante, verificar_invariante_agora
from apps.financeiro.liquidez import registrar_saida
from apps.financeiro.models import AlertaFinanceiro
from apps.financeiro.reserva import InvarianteViolado, registrar_aporte
from apps.nucleo.tempo import agora
from apps.pagamentos.provedor import ProvedorIndisponivel, SaldoNoProvedor
from tests.apoio.financeiro import montar_l, obrigacao_de, pedido_composto, receita_de
from tests.apoio.pedidos import T0, administrador, sincronizar, tentativa_criada
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)
LOG = "apps.financeiro.invariante"


def _alertas_abertos() -> list[AlertaFinanceiro]:
    return list(AlertaFinanceiro.objects.filter(tipo="invariante_violado", resolvido_em=None))


@pytest.fixture
def com_aporte(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    """O arranjo L, o depósito de 1000,00 no simulador e o aporte registrado (E09-05)."""
    a, b = montar_l(simulador_pagamentos, relogio)
    simulador_pagamentos.depositar(D("1000.00"))
    with transaction.atomic():
        registrar_aporte(administrador(), D("1000.00"), "sim-mov-1", "Aporte inicial")
    return a, b, simulador_pagamentos


def test_com_o_saldo_cobrindo_as_obrigacoes_nao_ha_alerta(com_aporte: Any) -> None:  # A-7
    resultado = verificar_invariante_agora()
    assert resultado == ResultadoDoInvariante(
        saldo_do_provedor=D("1189.00"),
        obrigacoes_de_terceiros=D("180.00"),
        diferenca=D("1009.00"),
    )
    assert _alertas_abertos() == []


def test_saldo_abaixo_das_obrigacoes_abre_o_alerta_e_o_restabelecimento_o_resolve(
    com_aporte: Any,
) -> None:  # A-8
    simulador = com_aporte[2]
    simulador.ajustar_saldo(D("-1100.00"))
    resultado = verificar_invariante_agora()
    assert resultado is not None
    assert resultado.diferenca == D("-91.00")
    (alerta,) = _alertas_abertos()
    assert alerta.chave == "geral"
    assert alerta.gravidade == "critico"
    assert D(str(alerta.dados["diferenca"])) == D("-91.00")
    simulador.ajustar_saldo(D("1100.00"))
    verificar_invariante_agora()
    assert _alertas_abertos() == []
    resolvido = AlertaFinanceiro.objects.get(tipo="invariante_violado")
    assert resolvido.resolvido_em is not None


def test_com_o_alerta_aberto_a_retirada_e_bloqueada_e_o_repasse_nao(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-9
    a, _ = montar_l(simulador_pagamentos, relogio)
    relogio.congelar(T0 + 25 * H)
    with transaction.atomic():
        abrir_alerta("invariante_violado", "geral", {"diferenca": "-91.00"})
    with pytest.raises(InvarianteViolado):
        registrar_saida(
            administrador(),
            tipo="retirada_de_receita",
            conta=receita_de(a.rodada),
            valor=D("1.00"),
            identificacao="ret-1",
            justificativa="Retirada",
        )
    repasse = registrar_saida(
        administrador(),
        tipo="repasse",
        conta=obrigacao_de(a.fornecedor, a.rodada),
        valor=D("10.00"),
        identificacao="rep-1",
        justificativa="Repasse",
    )
    assert repasse.chave == "saida:rep-1"


def test_provedor_indisponivel_deixa_os_alertas_como_estavam(
    com_aporte: Any, caplog: pytest.LogCaptureFixture
) -> None:  # A-10
    simulador = com_aporte[2]
    with transaction.atomic():
        abrir_alerta("invariante_violado", "geral", {"diferenca": "-1.00"})
    antes = list(AlertaFinanceiro.objects.order_by("pk").values())
    simulador.indisponivel()
    caplog.set_level(logging.INFO, logger=LOG)
    assert verificar_invariante_agora() is None
    assert [r for r in caplog.records if r.name == LOG and r.levelno == logging.WARNING]
    assert list(AlertaFinanceiro.objects.order_by("pk").values()) == antes


class _ProvedorDeTeste:
    """Um dublê que só responde o saldo: o do relatório do provedor, com o seu instante."""

    def __init__(self, liberado: str, referente_a: Any) -> None:
        self.liberado = D(liberado)
        self.referente_a = referente_a

    def consultar_saldo(self) -> SaldoNoProvedor:
        return SaldoNoProvedor(self.liberado, D("0.00"), self.referente_a, self.referente_a)


def test_o_saldo_de_relatorio_e_comparado_com_o_livro_no_mesmo_instante(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-22
    montar_l(simulador_pagamentos, relogio)  # o relógio fica em T0 + 2h
    relogio.congelar(T0 + 3 * H)
    xc = pedido_composto(ContaFactory.create(), "100.00", "5.00", "20.00")
    id_externo = tentativa_criada(xc).id_externo
    assert id_externo is not None
    simulador_pagamentos.aprovar(id_externo)
    sincronizar(id_externo)  # XC entra na custódia depois de `referente_a`
    referente_a = T0 + 2 * H
    monkeypatch.setattr(
        "apps.financeiro.invariante.obter_provedor", lambda: _ProvedorDeTeste("189.00", referente_a)
    )
    resultado = verificar_invariante_agora()
    assert resultado is not None
    assert resultado.obrigacoes_de_terceiros == D("180.00")  # sem o recorte seriam 305,00
    assert _alertas_abertos() == []
    monkeypatch.setattr(
        "apps.financeiro.invariante.obter_provedor", lambda: _ProvedorDeTeste("89.00", referente_a)
    )
    verificar_invariante_agora()
    (alerta,) = _alertas_abertos()
    assert D(str(alerta.dados["diferenca"])) == D("-91.00")


class _ProvedorQueResponde:
    """Um dublê que responde só o saldo, com folga para o invariante."""

    def consultar_saldo(self) -> SaldoNoProvedor:
        agora_ = agora()
        return SaldoNoProvedor(D("1000.00"), D("0.00"), agora_, agora_)


class _ProvedorFora:
    def consultar_saldo(self) -> SaldoNoProvedor:
        raise ProvedorIndisponivel("fora do ar")


def _alertas_da_reserva() -> list[AlertaFinanceiro]:
    return list(AlertaFinanceiro.objects.filter(tipo="reserva_insuficiente", resolvido_em=None))


def test_a_tarefa_do_invariante_avalia_a_reserva(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:  # A-24, E09-R05
    from apps.financeiro.apuracao import cobrir_tarifas_pendentes_da_rodada
    from tests.apoio.financeiro import despesa_de_tarifa, montar_mundo, semear

    relogio.congelar(T0)
    mundo = montar_mundo()
    despesa_de_tarifa("10.00", mundo.ra)
    monkeypatch.setattr("apps.financeiro.invariante.obter_provedor", lambda: _ProvedorQueResponde())
    # (i) sem violação do invariante, mas com 10,00 de tarifa pendente e a reserva em 0,00
    resultado = verificar_invariante_agora()
    assert resultado is not None
    assert _alertas_abertos() == []
    (alerta,) = _alertas_da_reserva()
    assert (D(str(alerta.dados["sem_cobertura"])), D(str(alerta.dados["livre"]))) == (
        D("10.00"),
        D("0.00"),
    )
    # (iii) o provedor fora do ar: devolve None, avisa, e a reserva continua avaliada
    monkeypatch.setattr("apps.financeiro.invariante.obter_provedor", lambda: _ProvedorFora())
    caplog.set_level(logging.INFO, logger=LOG)
    assert verificar_invariante_agora() is None
    assert [r for r in caplog.records if r.name == LOG and r.levelno == logging.WARNING]
    assert len(_alertas_da_reserva()) == 1
    assert _alertas_abertos() == []
    # (ii) a tarifa é coberta fora das operações da reserva: a tarefa resolve o alerta
    with transaction.atomic():
        semear(mundo, receita_de(mundo.ra), "10.00")
        assert cobrir_tarifas_pendentes_da_rodada(mundo.ra) == 1
    monkeypatch.setattr("apps.financeiro.invariante.obter_provedor", lambda: _ProvedorQueResponde())
    verificar_invariante_agora()
    assert _alertas_da_reserva() == []
