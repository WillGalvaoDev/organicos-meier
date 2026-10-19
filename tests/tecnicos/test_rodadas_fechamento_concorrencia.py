"""E06-01: início do fechamento sob concorrência (acceptance A-12 a A-14)."""

from decimal import Decimal
from typing import Any

import pytest

from apps.contas.models import Conta
from apps.fornecedores.servicos import alterar_minimo
from apps.interesses.servicos import reduzir_interesse
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.fechamento import TransicaoRecusada, iniciar_fechamento, prazo_do_fechamento
from apps.rodadas.models import Ciclo, Etapa, PrazoDoFechamento, Rodada
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.interesses import cenario, reservada
from tests.apoio.trava import esperando, segurando
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
