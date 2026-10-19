"""E06-01: início do fechamento sob concorrência (acceptance A-12 a A-14)."""

import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction

from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import alterar_minimo
from apps.interesses import servicos
from apps.interesses.servicos import adicionar_interesse, interesse_do_comprador, reduzir_interesse
from apps.notificacoes.models import Notificacao
from apps.rodadas import condicoes
from apps.rodadas.condicoes import CondicoesCongeladas, InteressesBloqueados
from apps.rodadas.fechamento import TransicaoRecusada, iniciar_fechamento, prazo_do_fechamento
from apps.rodadas.models import Ciclo, Etapa, PrazoDoFechamento, Rodada
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.interesses import cenario, reservada
from tests.apoio.trava import esperando, esperar_outra_conexao_na_trava, segurando
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]

D = Decimal


def admin() -> Conta:
    return Conta.objects.get(papel="administrador")


def etapa(rodada: Rodada) -> str:
    return str(Rodada.objects.get(pk=rodada.pk).etapa)


def test_reducao_que_confirma_antes_derruba_o_minimo() -> None:  # A-12 (a)
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    a = ContaFactory.create()
    reservada(a, produto, 10)
    resultados = executar_em_paralelo(
        segurando(lambda: reduzir_interesse(a, produto, "1")),
        esperando(lambda: iniciar_fechamento(admin(), rodada)),
    )
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, TransicaoRecusada), resultados[1].excecao
    assert resultados[1].excecao.codigo == "minimo_nao_atingido"
    assert etapa(rodada) == Etapa.INTERESSE
    assert Ciclo.objects.count() == 0


def test_inicio_que_confirma_antes_aceita_a_reducao_no_fechamento() -> None:  # A-12 (b)
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    a = ContaFactory.create()
    reservada(a, produto, 10)
    resultados = executar_em_paralelo(
        segurando(lambda: iniciar_fechamento(admin(), rodada)),
        esperando(lambda: reduzir_interesse(a, produto, "1")),
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert etapa(rodada) == Etapa.FECHAMENTO
    prazo = PrazoDoFechamento.objects.get()
    assert prazo_do_fechamento(rodada) == prazo.termina_em
    assert (prazo.termina_em - prazo.ciclo.iniciado_em).total_seconds() == 24 * 3600


def test_alteracao_de_minimo_depois_do_inicio_e_recusada() -> None:  # A-13
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    resultados = executar_em_paralelo(
        segurando(lambda: iniciar_fechamento(admin(), rodada)),
        esperando(lambda: alterar_minimo(admin(), rodada.fornecedor, "50,00")),
    )
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, CondicoesCongeladas), resultados[1].excecao
    (ciclo,) = Ciclo.objects.all()
    assert ciclo.minimo == D("100.00")


def test_dois_inicios_simultaneos_so_um_confirma() -> None:  # A-14
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)

    def iniciar(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        return iniciar_fechamento(admin(), rodada)

    resultados = executar_em_paralelo(iniciar, iniciar)
    excecoes = [r.excecao for r in resultados if r.excecao is not None]
    assert len(excecoes) == 1, [r.excecao for r in resultados]
    assert isinstance(excecoes[0], TransicaoRecusada)
    assert excecoes[0].codigo == "fora_de_interesse"
    assert Ciclo.objects.count() == 1
    assert PrazoDoFechamento.objects.filter(origem="inicio").count() == 1


def test_aviso_do_inicio_nao_trava_com_a_conta_do_comprador_segura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # E06-02 A-8
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    a = ContaFactory.create()
    reservada(a, produto, 10)

    def comprador(barreira: Any) -> Any:
        original = servicos._travar_conta

        def com_pausa(conta: Conta) -> Conta:
            travada = original(conta)
            barreira.wait(timeout=10)  # a conta já está travada pelo serviço do comprador
            return travada

        monkeypatch.setattr(servicos, "_travar_conta", com_pausa)
        return adicionar_interesse(a, produto, "1")

    def inicio(barreira: Any) -> Any:
        with transaction.atomic():
            Fornecedor.objects.select_for_update().get(pk=rodada.fornecedor_id)
            barreira.wait(timeout=10)
            return iniciar_fechamento(admin(), rodada)

    resultados = executar_em_paralelo(inicio, comprador)
    assert all(r.excecao is None for r in resultados), [str(r.excecao) for r in resultados]
    avisos = Notificacao.objects.filter(conta=a, evento="fechamento_iniciado")
    assert avisos.count() == 1
    assert etapa(rodada) == Etapa.FECHAMENTO
    assert interesse_do_comprador(a, produto).reservado == D("11")


def test_o_prazo_e_lido_depois_de_obter_as_travas(
    monkeypatch: pytest.MonkeyPatch, relogio: RelogioControlado
) -> None:  # E06-03 A-9
    # `time-machine` não atravessa threads de forma confiável: o relógio compartilhado é um
    # `monkeypatch` de `agora` em `apps.rodadas.condicoes`, que é onde o prazo é decidido.
    relogio.congelar(datetime(2026, 11, 2, 13, 30, tzinfo=UTC))
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    iniciar_fechamento(admin(), rodada)
    relogio.parar()
    prazo = prazo_do_fechamento(rodada)
    assert prazo is not None
    compartilhado = {"agora": prazo - timedelta(milliseconds=50)}
    monkeypatch.setattr(condicoes, "agora", lambda: compartilhado["agora"])
    original = servicos.travar_rodada_para_interesses  # type: ignore[attr-defined]
    contexto: dict[str, Any] = {}

    def travar_com_pausa(fornecedor: Fornecedor) -> Rodada:
        travada = original(fornecedor)  # lê `agora()` (antes do prazo) já com as travas
        if threading.current_thread().name.endswith("-0"):  # só a operação que segura
            contexto["barreira"].wait(timeout=10)
            esperar_outra_conexao_na_trava()
            compartilhado["agora"] = prazo + timedelta(seconds=1)  # o prazo passa antes de soltar
        return travada

    monkeypatch.setattr(servicos, "travar_rodada_para_interesses", travar_com_pausa)
    b, c = ContaFactory.create(), ContaFactory.create()

    def adicao_de_b(barreira: Any) -> Any:
        contexto["barreira"] = barreira
        return adicionar_interesse(b, produto, "1")

    def adicao_de_c(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        return adicionar_interesse(c, produto, "1")

    resultados = executar_em_paralelo(adicao_de_b, adicao_de_c)
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, InteressesBloqueados), resultados[1].excecao
    assert resultados[1].excecao.codigo == "prazo_encerrado"
    assert interesse_do_comprador(b, produto).reservado == D("1")
    assert interesse_do_comprador(c, produto).reservado == D("0")
