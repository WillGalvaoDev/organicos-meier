"""E09-01: concorrência do livro-razão (acceptance A-14 a A-16)."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from threading import Barrier, BrokenBarrierError, local
from typing import Any

import pytest
from django.db import transaction

from apps.financeiro import livro
from apps.financeiro.alertas import abrir_alerta
from apps.financeiro.apuracao import registrar_apuracao_no_livro
from apps.financeiro.conciliacao import ConciliacaoDiaria, conciliar_dia
from apps.financeiro.liquidez import LiquidezInsuficiente, registrar_saida
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
    TransferenciaFinanceira,
)
from apps.financeiro.obrigacoes import (
    LiquidacaoRecusada,
    liquidar_obrigacao,
    registrar_obrigacao_com_comprador,
)
from apps.financeiro.reserva import (
    AporteRepetido,
    ReservaInsuficiente,
    designar_reserva,
    registrar_aporte,
    situacao_da_reserva,
    utilizar_reserva,
)
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import SISTEMA
from apps.pedidos.tarefas import reconsultar_pagamentos_da_margem_agora
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.financeiro import (
    Mundo,
    custodia,
    despesa_de_tarifa,
    despesas,
    montar_ap,
    montar_l,
    montar_mundo,
    mover,
    obrigacao_de,
    obrigacao_de_teste,
    pagar_pedido,
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


# --- E09-05: reserva (A-12 a A-14) ------------------------------------------------------------


def _um_passa_e_o_outro_e_recusado(resultados: list[Any]) -> None:
    excecoes = [r.excecao for r in resultados]
    assert sum(e is None for e in excecoes) == 1, excecoes
    (recusa,) = [e for e in excecoes if e is not None]
    assert isinstance(recusa, ReservaInsuficiente), recusa


def test_duas_designacoes_que_juntas_passam_do_livre(m: Mundo) -> None:  # E09-05, A-12, T-10
    with transaction.atomic():
        semear(m, reserva(), "60.00")
        primeira, segunda = obrigacao_de_teste("50.00"), obrigacao_de_teste("50.00")

    def designar(obrigacao: Any) -> Callable[[], Any]:
        return lambda: designar_reserva(m.admin, obrigacao, Decimal("50.00"), "devolução")

    resultados = executar_em_paralelo(
        segurando(designar(primeira)), esperando(_atomica(designar(segunda)))
    )
    _um_passa_e_o_outro_e_recusado(resultados)
    assert situacao_da_reserva().comprometido == Decimal("50.00")


def test_designacao_e_utilizacao_ao_mesmo_tempo(m: Mundo) -> None:  # E09-05, A-13, T-10
    with transaction.atomic():
        semear(m, reserva(), "60.00")
        obrigacao = obrigacao_de_teste("50.00")
        tarifa = despesa_de_tarifa("40.00")

    def designar() -> Any:
        return designar_reserva(m.admin, obrigacao, Decimal("50.00"), "devolução")

    def utilizar() -> Any:
        return utilizar_reserva(m.admin, tarifa, Decimal("40.00"), "tarifa")

    resultados = executar_em_paralelo(segurando(designar), esperando(_atomica(utilizar)))
    _um_passa_e_o_outro_e_recusado(resultados)
    assert situacao_da_reserva().livre >= 0


def test_o_mesmo_deposito_registrado_duas_vezes(m: Mundo) -> None:  # E09-05, A-14
    reserva()  # a conta já existe: o que serializa as duas é a trava, e não a criação dela

    def aportar() -> Any:
        return registrar_aporte(m.admin, Decimal("100.00"), "sim-mov-1", "Aporte")

    resultados = executar_em_paralelo(segurando(aportar), esperando(_atomica(aportar)))
    excecoes = [r.excecao for r in resultados]
    assert sum(e is None for e in excecoes) == 1, excecoes
    (recusa,) = [e for e in excecoes if e is not None]
    assert isinstance(recusa, AporteRepetido), recusa
    assert MovimentoFinanceiro.objects.filter(tipo=T.APORTE).count() == 1
    assert saldo(reserva()) == Decimal("100.00")


# --- E09-06: apuração e obrigações com compradores (A-17 a A-19) ------------------------------


def _ap_com_x_pago(relogio: RelogioControlado, sim: Any) -> Any:
    sim.definir_tarifa("pix", percentual=Decimal("1.00"), fixa=Decimal("0.00"))
    ap = montar_ap()
    pagar_pedido(ap, ap.x, sim, relogio, timedelta(hours=1))
    return ap


def _financiar(ap: Any, origem: Any, produtos: str) -> Callable[[], Any]:
    def registrar() -> Any:
        return registrar_obrigacao_com_comprador(
            origem=origem,
            rodada=ap.rodada,
            ciclo=ap.ciclo,
            comprador=ap.b,
            pedido=ap.x,
            motivo="devolucao_de_teste",
            produtos=Decimal(produtos),
            servico=Decimal("0.00"),
            frete=Decimal("0.00"),
        )

    return registrar


def test_duas_obrigacoes_do_mesmo_comprador_disputam_a_mesma_custodia(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # E09-06, A-17
    ap = _ap_com_x_pago(relogio, simulador_pagamentos)
    resultados = executar_em_paralelo(
        segurando(_financiar(ap, ap.x, "60.00")),
        esperando(_atomica(_financiar(ap, ap.abertura, "60.00"))),
    )
    assert all(r.excecao is None for r in resultados), [repr(r.excecao) for r in resultados]
    assert sorted(r.valor.sem_cobertura for r in resultados) == [
        Decimal("0.00"),
        Decimal("20.00"),
    ]
    assert saldo(custodia(ap.rodada, ap.ciclo, ap.b, "produtos")) == Decimal("0.00")
    financiado = sum(
        t.valor
        for t in TransferenciaFinanceira.objects.filter(
            movimento__tipo=T.FINANCIAMENTO_DE_OBRIGACAO
        )
    )
    assert financiado == Decimal("100.00")


def test_duas_liquidacoes_da_mesma_obrigacao(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # E09-06, A-18
    ap = _ap_com_x_pago(relogio, simulador_pagamentos)
    with transaction.atomic():
        obrigacao = _financiar(ap, ap.x, "25.00")().obrigacao

    def liquidar(referencia: str) -> Callable[[], Any]:
        return lambda: liquidar_obrigacao(obrigacao, Decimal("25.00"), referencia=referencia)

    resultados = executar_em_paralelo(
        segurando(liquidar("dev-a")), esperando(_atomica(liquidar("dev-b")))
    )
    excecoes = [r.excecao for r in resultados]
    assert sum(e is None for e in excecoes) == 1, excecoes
    (recusa,) = [e for e in excecoes if e is not None]
    assert isinstance(recusa, LiquidacaoRecusada), recusa
    assert MovimentoFinanceiro.objects.filter(tipo=T.DEVOLUCAO).count() == 1


def test_apuracao_e_quitacao_ao_mesmo_tempo_nunca_movem_so_parte(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # E09-06, A-19
    simulador_pagamentos.definir_tarifa("pix", percentual=Decimal("1.00"), fixa=Decimal("0.00"))
    ap = montar_ap()
    relogio.congelar(T0 + timedelta(hours=1))
    id_externo = tentativa_criada(ap.x).id_externo
    assert id_externo is not None
    simulador_pagamentos.aprovar(id_externo)

    def quitar(barreira: Any) -> None:
        barreira.wait(timeout=10)
        sincronizar(id_externo)

    def apurar(barreira: Any) -> None:
        barreira.wait(timeout=10)
        with transaction.atomic():
            registrar_apuracao_no_livro(ap.ciclo, [ap.x], autor=SISTEMA)

    resultados = executar_em_paralelo(quitar, apurar)
    assert resultados[0].excecao is None, repr(resultados[0].excecao)
    custodias = [
        saldo(custodia(ap.rodada, ap.ciclo, ap.b, componente))
        for componente in ("produtos", "servico", "frete")
    ]
    if resultados[1].excecao is None:  # a apuração viu o destino e moveu os saldos completos
        assert custodias == [Decimal("0.00")] * 3
        assert saldo(obrigacao_de(ap.fornecedor, ap.rodada)) == Decimal("100.00")
    else:  # a apuração chegou antes de X quitar: recusada, sem tocar nada
        assert isinstance(resultados[1].excecao, ValueError), repr(resultados[1].excecao)
        assert custodias == [Decimal("100.00"), Decimal("5.00"), Decimal("20.00")]


# --- E09-07: liquidez e conciliação (A-19 e A-20) ---------------------------------------------


def test_dois_repasses_que_juntos_passam_do_liberado(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # E09-07, A-19, T-11
    a, _ = montar_l(simulador_pagamentos, relogio)
    relogio.congelar(T0 + timedelta(hours=25))
    conta_de_a = obrigacao_de(a.fornecedor, a.rodada)

    def repassar(identificacao: str) -> Callable[[], Any]:
        return lambda: registrar_saida(
            m_admin(),
            tipo="repasse",
            conta=conta_de_a,
            valor=Decimal("60.00"),
            identificacao=identificacao,
            justificativa="Repasse",
        )

    resultados = executar_em_paralelo(
        segurando(repassar("rep-a")), esperando(_atomica(repassar("rep-b")))
    )
    excecoes = [r.excecao for r in resultados]
    assert sum(e is None for e in excecoes) == 1, excecoes
    (recusa,) = [e for e in excecoes if e is not None]
    assert isinstance(recusa, LiquidezInsuficiente), recusa
    assert saldo(conta_de_a) == Decimal("40.00")


def m_admin() -> Any:
    from tests.apoio.pedidos import administrador

    return administrador()


def test_duas_conciliacoes_do_mesmo_dia(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # E09-07, A-20
    montar_l(simulador_pagamentos, relogio)
    relogio.congelar(T0 + timedelta(hours=3))
    simulador_pagamentos.depositar(Decimal("200.00"))  # depósito sem aporte: gera divergência
    relogio.congelar(datetime(2026, 11, 3, 12, 0, tzinfo=UTC))

    def conciliar(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        return conciliar_dia(date(2026, 11, 2))

    resultados = executar_em_paralelo(conciliar, conciliar)
    assert all(r.excecao is None for r in resultados), [repr(r.excecao) for r in resultados]
    assert resultados[0].valor.pk == resultados[1].valor.pk
    assert ConciliacaoDiaria.objects.count() == 1
    abertos = AlertaFinanceiro.objects.filter(tipo="divergencia_na_conciliacao", resolvido_em=None)
    assert abertos.count() == 1
