"""E09-01: concorrência do livro-razão (acceptance A-14 a A-16)."""

from collections.abc import Callable
from decimal import Decimal
from threading import Barrier, BrokenBarrierError, local
from typing import Any

import pytest
from django.db import transaction

from apps.financeiro import livro
from apps.financeiro.alertas import abrir_alerta
from apps.financeiro.livro import (
    EXTERIOR,
    SaldoInsuficiente,
    Transferencia,
    lancar,
    saldo,
)
from apps.financeiro.models import AlertaFinanceiro, MovimentoFinanceiro, TipoDeMovimento
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import SISTEMA
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.financeiro import Mundo, despesas, montar_mundo, mover, receita_de, reserva, semear
from tests.apoio.trava import esperando, segurando

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]

D = Decimal
T = TipoDeMovimento


@pytest.fixture
def m() -> Mundo:
    return montar_mundo()


def _atomica(operacao: Callable[[], Any]) -> Callable[[], Any]:
    def executa() -> Any:
        with transaction.atomic():
            return operacao()

    return executa


def test_duas_retiradas_que_juntas_passam_do_saldo(m: Mundo) -> None:  # A-14
    receita = receita_de(m.ra)
    with transaction.atomic():
        semear(m, receita, "10.00")

    def retirar(chave: str) -> Callable[[], Any]:
        return lambda: mover(T.RETIRADA_DE_RECEITA, receita, EXTERIOR, "6.00", chave=chave)

    resultados = executar_em_paralelo(
        segurando(retirar("retirada:1")), esperando(_atomica(retirar("retirada:2")))
    )
    excecoes = [r.excecao for r in resultados]
    assert sum(e is None for e in excecoes) == 1, excecoes
    (recusa,) = [e for e in excecoes if e is not None]
    assert isinstance(recusa, SaldoInsuficiente), recusa
    assert saldo(receita) == D("4.00")
    assert MovimentoFinanceiro.objects.filter(tipo=T.RETIRADA_DE_RECEITA).count() == 1


def test_o_mesmo_movimento_por_duas_transacoes_grava_uma_vez(m: Mundo) -> None:  # A-15
    reservada = reserva()

    def aportar() -> Any:
        return mover(T.APORTE, EXTERIOR, reservada, "50.00", chave="aporte:1")

    resultados = executar_em_paralelo(segurando(aportar), esperando(_atomica(aportar)))
    assert all(r.excecao is None for r in resultados), [repr(r.excecao) for r in resultados]
    assert resultados[0].valor.pk == resultados[1].valor.pk
    assert MovimentoFinanceiro.objects.filter(chave="aporte:1").count() == 1
    assert saldo(reservada) == D("50.00")


def test_ordem_de_chamada_diferente_nao_causa_impasse(
    m: Mundo, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-16
    receita, reservada, a_cobrir = receita_de(m.ra), reserva(), despesas()
    with transaction.atomic():
        semear(m, receita, "10.00")
        semear(m, reservada, "10.00")
        mover(T.TARIFA, a_cobrir, EXTERIOR, "3.00")
    pausa = Barrier(2)
    estado = local()
    original = livro._travar_conta

    def travar_e_pausar(pk: int) -> Any:
        resultado = original(pk)
        if not getattr(estado, "pausou", False):
            estado.pausou = True
            try:
                pausa.wait(timeout=2)
            except BrokenBarrierError:
                pass  # a outra transação espera a primeira trava: a ordem global já a segura
        return resultado

    monkeypatch.setattr(livro, "_travar_conta", travar_e_pausar)

    def cobrir(primeira: Any, segunda: Any, chave: str) -> Callable[[Any], Any]:
        def executa(barreira: Any) -> Any:
            barreira.wait(timeout=10)
            with transaction.atomic():
                return lancar(
                    tipo=T.COBERTURA_DE_DESPESA,
                    transferencias=[
                        Transferencia(primeira, a_cobrir, D("1.00")),
                        Transferencia(segunda, a_cobrir, D("1.00")),
                    ],
                    autor=SISTEMA,
                    justificativa="teste",
                    origem=m.ra,
                    chave=chave,
                )

        return executa

    resultados = executar_em_paralelo(
        cobrir(receita, reservada, "cobertura:1"), cobrir(reservada, receita, "cobertura:2")
    )
    assert all(r.excecao is None for r in resultados), [repr(r.excecao) for r in resultados]
    assert (saldo(receita), saldo(reservada), saldo(a_cobrir)) == (
        D("8.00"),
        D("8.00"),
        D("1.00"),
    )


def test_duas_aberturas_do_mesmo_alerta_gravam_um_so(m: Mundo) -> None:  # E09-03, A-10
    admin = m.admin

    def abrir() -> Any:
        return abrir_alerta(
            "reserva_insuficiente", "geral", {"sem_cobertura": "5.00", "livre": "1.00"}
        )

    resultados = executar_em_paralelo(segurando(abrir), esperando(_atomica(abrir)))
    assert all(r.excecao is None for r in resultados), [repr(r.excecao) for r in resultados]
    assert resultados[0].valor.pk == resultados[1].valor.pk
    assert AlertaFinanceiro.objects.count() == 1
    assert Notificacao.objects.filter(conta=admin, evento="alerta_financeiro").count() == 1
