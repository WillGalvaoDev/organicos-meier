"""E03-04: sequência da parcela sob concorrência (acceptance A-9)."""

import time
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction

from apps.catalogo.models import Produto, Unidade
from apps.catalogo.quantidades import QuantidadeInvalida
from apps.catalogo.servicos import IncrementoIncompativel, alterar_incremento
from apps.contas.models import Conta
from apps.contas.moderacao import suspender
from apps.interesses.consultas import total_reservado
from apps.interesses.fila import alocar_pendentes
from apps.interesses.models import ParcelaDeInteresse
from apps.interesses.servicos import EstoqueInsuficiente, adicionar_interesse, reduzir_interesse
from apps.rodadas.condicoes import travar_rodada_para_interesses
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.interesses import cenario, pendente, reservada
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    ParcelaFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]


def test_vinte_insercoes_em_paralelo_recebem_sequencias_distintas() -> None:  # A-9
    comprador = ContaFactory.create()
    produto = ProdutoFactory.create()

    def inserir(barreira: Any) -> int:
        barreira.wait(timeout=10)
        return ParcelaFactory.create(comprador=comprador, produto=produto).sequencia

    resultados = executar_em_paralelo(*[inserir] * 20)
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    sequencias = [r.valor for r in resultados]
    assert len(set(sequencias)) == 20
    gravadas = list(
        ParcelaDeInteresse.objects.order_by("sequencia").values_list("sequencia", flat=True)
    )
    assert sorted(sequencias) == gravadas


D = Decimal


def _esperar_outra_conexao_na_trava(segundos: float = 15) -> None:
    with connection.cursor() as cursor:
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE wait_event_type = 'Lock' AND datname = current_database()"
            )
            (esperando,) = cursor.fetchone()
            if esperando:
                return
            time.sleep(0.05)
    raise AssertionError("a outra conexão não ficou esperando pela trava")


def _produto_na_rodada(limite: str | None) -> Produto:
    rodada = RodadaFactory.create()
    produto = ProdutoFactory.create(fornecedor=rodada.fornecedor, unidade=Unidade.UNIDADE)
    EstoqueDaRodadaFactory.create(
        rodada=rodada, produto=produto, limite=None if limite is None else D(limite)
    )
    return produto


def _segurando(operacao: Any) -> Any:
    """Roda a operação numa transação externa e segura as travas até a outra esperar."""

    def segura(barreira: Any) -> None:
        with transaction.atomic():
            operacao()
            barreira.wait(timeout=10)
            _esperar_outra_conexao_na_trava()

    return segura


def _esperando(operacao: Any) -> Any:
    def espera(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        return operacao()

    return espera


def test_ultima_unidade_disputada_so_uma_vence() -> None:  # A-13, cenário 3
    produto = _produto_na_rodada("1")
    a, b = ContaFactory.create(), ContaFactory.create()
    resultados = executar_em_paralelo(
        _segurando(lambda: adicionar_interesse(a, produto, "1")),
        _esperando(lambda: adicionar_interesse(b, produto, "1")),
    )
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, EstoqueInsuficiente)
    assert resultados[1].excecao.mensagem == "Este produto está esgotado nesta rodada."
    assert total_reservado(produto) == D("1")
    assert ParcelaDeInteresse.objects.filter(produto=produto).count() == 1


@pytest.mark.parametrize("adicao_primeiro", [True, False])
def test_adicao_e_alteracao_de_incremento_se_serializam(adicao_primeiro: bool) -> None:  # A-14
    # cenário 108
    produto = _produto_na_rodada(None)
    admin = Conta.objects.get(papel="administrador")
    a = ContaFactory.create()
    adicionar = lambda: adicionar_interesse(a, produto, "3")  # noqa: E731
    alterar = lambda: alterar_incremento(admin, Produto.objects.get(pk=produto.pk), "2")  # noqa: E731
    if adicao_primeiro:
        resultados = executar_em_paralelo(_segurando(adicionar), _esperando(alterar))
        assert resultados[0].excecao is None, resultados[0].excecao
        assert isinstance(resultados[1].excecao, IncrementoIncompativel)
        assert resultados[1].excecao.codigo == "quantidade"
        assert Produto.objects.get(pk=produto.pk).incremento == D("1")
    else:
        resultados = executar_em_paralelo(_segurando(alterar), _esperando(adicionar))
        assert resultados[0].excecao is None, resultados[0].excecao
        assert isinstance(resultados[1].excecao, QuantidadeInvalida)
        assert Produto.objects.get(pk=produto.pk).incremento == D("2")
        assert ParcelaDeInteresse.objects.count() == 0
    incremento = Produto.objects.get(pk=produto.pk).incremento
    for parcela in ParcelaDeInteresse.objects.all():
        assert parcela.quantidade_reservada % incremento == 0


def test_suspensao_confirmada_antes_barra_a_adicao() -> None:  # A-15
    produto = _produto_na_rodada(None)
    admin = Conta.objects.get(papel="administrador")
    a = ContaFactory.create()
    resultados = executar_em_paralelo(
        _segurando(lambda: suspender(admin, a)),
        _esperando(lambda: adicionar_interesse(a, produto, "1")),
    )
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, PermissionDenied)
    assert ParcelaDeInteresse.objects.count() == 0


def test_dez_adicoes_de_dois_com_limite_dez() -> None:  # A-16
    produto = _produto_na_rodada("10")
    compradores = [ContaFactory.create() for _ in range(10)]

    def adicionar(comprador: Conta) -> Any:
        def operacao(barreira: Any) -> None:
            barreira.wait(timeout=10)
            adicionar_interesse(comprador, produto, "2")

        return operacao

    resultados = executar_em_paralelo(*[adicionar(c) for c in compradores])
    aceitas = [r for r in resultados if r.excecao is None]
    recusadas = [r for r in resultados if r.excecao is not None]
    assert len(aceitas) == 5, [r.excecao for r in recusadas]
    assert all(isinstance(r.excecao, EstoqueInsuficiente) for r in recusadas)
    assert total_reservado(produto) == D("10")
    sequencias = list(
        ParcelaDeInteresse.objects.filter(produto=produto).values_list("sequencia", flat=True)
    )
    assert len(sequencias) == len(set(sequencias)) == 5


def test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem() -> None:  # A-15
    # T-31, cenário 78
    rodada, produto, _ = cenario("6")
    a, e = ContaFactory.create(), ContaFactory.create()
    pa = pendente(a, produto, 4)

    def alocar() -> Any:
        with transaction.atomic():
            return alocar_pendentes(rodada.fornecedor)

    def adicionar() -> Any:
        try:
            adicionar_interesse(e, produto, "4")
        except EstoqueInsuficiente as erro:
            return erro
        return None

    def segurando_a_trava_e_adicionando(barreira: Any) -> Any:
        with transaction.atomic():
            travar_rodada_para_interesses(rodada.fornecedor)  # a trava fica até o fim do bloco
            recusa = adicionar()
            barreira.wait(timeout=10)
            _esperar_outra_conexao_na_trava()
        return recusa

    for primeiro, segundo in (
        (_segurando(alocar), _esperando(adicionar)),
        (segurando_a_trava_e_adicionando, _esperando(alocar)),
    ):
        ParcelaDeInteresse.objects.filter(produto=produto).exclude(pk=pa.pk).delete()
        ParcelaDeInteresse.objects.filter(pk=pa.pk).update(
            quantidade_reservada=D(0), quantidade_pendente=D(4), situacao="pendente"
        )
        resultados = executar_em_paralelo(primeiro, segundo)
        assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
        recusas = [r.valor for r in resultados if isinstance(r.valor, EstoqueInsuficiente)]
        assert [r.mensagem for r in recusas] == ["Há apenas 2 unidade disponível."]
        pa.refresh_from_db()
        assert (pa.quantidade_reservada, pa.quantidade_pendente) == (D("4"), D("0"))
        assert total_reservado(produto) == D("4")
        assert ParcelaDeInteresse.objects.filter(produto=produto).count() == 1


def test_reducao_e_adicao_concorrentes_dao_a_fila_o_que_foi_liberado() -> None:  # A-16
    # cenário 101, T-46
    _, produto, _ = cenario("10")
    d, outro, c, e = (ContaFactory.create() for _ in range(4))
    reservada(d, produto, 3)
    reservada(outro, produto, 7)
    pc = pendente(c, produto, 4)

    def reduzir(barreira: Any) -> None:
        barreira.wait(timeout=10)
        reduzir_interesse(d, produto, "3")

    def adicionar(barreira: Any) -> None:
        barreira.wait(timeout=10)
        adicionar_interesse(e, produto, "3")

    resultados = executar_em_paralelo(reduzir, adicionar)
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, EstoqueInsuficiente)
    pc.refresh_from_db()
    assert (pc.situacao, pc.quantidade_reservada, pc.quantidade_pendente) == (
        "ativa",
        D("3"),
        D("1"),
    )
    assert total_reservado(produto) == D("10")
    assert ParcelaDeInteresse.objects.filter(comprador=e).count() == 0
