"""E09-01: concorrência do livro-razão (acceptance A-14 a A-16)."""

from collections.abc import Callable
from datetime import timedelta
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
from apps.financeiro.models import (
    AlertaFinanceiro,
    ContaFinanceira,
    Despesa,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    TipoDeMovimento,
)
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import SISTEMA
from apps.pedidos.tarefas import reconsultar_pagamentos_da_margem_agora
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.financeiro import (
    Mundo,
    despesas,
    montar_mundo,
    mover,
    pedido_composto,
    receita_de,
    reserva,
    semear,
)
from tests.apoio.pedidos import T0, sincronizar, tentativa_criada
from tests.apoio.trava import esperando, segurando
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

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


# --- E09-04: entradas dos pagamentos (A-11 e A-12) --------------------------------------------


def _duas_cobrancas_aprovadas(relogio: RelogioControlado, sim: Any) -> tuple[Any, str, str]:
    """O pedido X de B com duas cobranças aprovadas, a primeira expirada e sincronizada antes."""
    sim.definir_tarifa("pix", percentual=Decimal("1.00"), fixa=Decimal("0.00"))
    relogio.congelar(T0 + timedelta(hours=1))
    comprador = ContaFactory.create()
    pedido = pedido_composto(comprador)
    primeira = tentativa_criada(pedido).id_externo
    assert primeira is not None
    sim.expirar(primeira)
    sincronizar(primeira)
    relogio.congelar(T0 + timedelta(hours=2))
    segunda = tentativa_criada(pedido).id_externo
    assert segunda is not None
    sim.aprovar(primeira, em=T0 + timedelta(minutes=110))
    sim.aprovar(segunda, em=T0 + timedelta(minutes=125))
    return pedido, primeira, segunda


def test_dois_pagamentos_do_mesmo_pedido_ao_mesmo_tempo(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # E09-04, A-11, cenário 39
    pedido, primeira, segunda = _duas_cobrancas_aprovadas(relogio, simulador_pagamentos)

    def sincronizar_em_paralelo(id_externo: str) -> Callable[[Any], None]:
        def executa(barreira: Any) -> None:
            barreira.wait(timeout=10)
            sincronizar(id_externo)

        return executa

    resultados = executar_em_paralelo(
        sincronizar_em_paralelo(primeira), sincronizar_em_paralelo(segunda)
    )
    assert all(r.excecao is None for r in resultados), [repr(r.excecao) for r in resultados]
    entradas = MovimentoFinanceiro.objects.filter(tipo=T.ENTRADA_DE_PAGAMENTO)
    assert entradas.count() == 1
    assert sum(t.valor for t in entradas.get().transferencias.all()) == Decimal("125.00")
    (obrigacao,) = ObrigacaoComComprador.objects.all()
    assert obrigacao.integral == Decimal("125.00")
    assert MovimentoFinanceiro.objects.filter(tipo=T.ENTRADA_PARA_DEVOLUCAO).count() == 1
    custodias = ContaFinanceira.objects.filter(destinacao="custodia", comprador=pedido.comprador)
    assert sum((saldo(c) for c in custodias), Decimal("0.00")) == pedido.total


def test_aviso_e_reconsulta_do_mesmo_pagamento_registram_uma_entrada(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # E09-04, A-12
    simulador_pagamentos.definir_tarifa("pix", percentual=Decimal("1.00"), fixa=Decimal("0.00"))
    relogio.congelar(T0 + timedelta(hours=1))
    pedido = pedido_composto(ContaFactory.create())
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    simulador_pagamentos.aprovar(id_externo)
    relogio.congelar(T0 + timedelta(hours=25))

    def aviso(barreira: Any) -> None:
        barreira.wait(timeout=10)
        sincronizar(id_externo, "aviso")

    def reconsulta(barreira: Any) -> None:
        barreira.wait(timeout=10)
        reconsultar_pagamentos_da_margem_agora()

    resultados = executar_em_paralelo(aviso, reconsulta)
    assert all(r.excecao is None for r in resultados), [repr(r.excecao) for r in resultados]
    assert MovimentoFinanceiro.objects.filter(tipo=T.ENTRADA_DE_PAGAMENTO).count() == 1
    assert MovimentoFinanceiro.objects.filter(tipo=T.TARIFA).count() == 1
    assert Despesa.objects.count() == 1
