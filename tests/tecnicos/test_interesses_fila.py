"""E05-02: atendimento da fila de pendentes (acceptance A-1 a A-14)."""

from decimal import Decimal

import pytest
from django.db import transaction
from django.db.transaction import TransactionManagementError

from apps.catalogo.models import Unidade
from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.interesses.consultas import total_reservado
from apps.interesses.fila import alocar_pendentes
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.interesses.servicos import (
    EstoqueInsuficiente,
    adicionar_interesse,
    reduzir_interesse,
)
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.estoque import alterar_estoque, incluir_produto_na_rodada
from apps.rodadas.models import Etapa
from tests.apoio.interesses import auditorias, cenario, parcelas, pendente, reservada
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    ParcelaFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = pytest.mark.django_db

D = Decimal
ACAO = "interesse.alocar_pendentes"


def administrador() -> Conta:
    return Conta.objects.get(papel="administrador")


def alocar(fornecedor: Fornecedor) -> Decimal:
    with transaction.atomic():
        return alocar_pendentes(fornecedor)


def estado(parcela: ParcelaDeInteresse) -> tuple[str, Decimal, Decimal]:
    parcela.refresh_from_db()
    return (parcela.situacao, parcela.quantidade_reservada, parcela.quantidade_pendente)


@pytest.mark.acceptance
def test_pendentes_sao_atendidas_pela_ordem_original() -> None:  # A-1, cenário 75
    rodada, produto, _ = cenario("10")
    a, c = ContaFactory.create(), ContaFactory.create()
    pa = pendente(a, produto, 6)
    pc = pendente(c, produto, 8)
    sequencias = (pa.sequencia, pc.sequencia)
    assert alocar(rodada.fornecedor) == 10
    assert estado(pa) == (SituacaoParcela.ATIVA, D("6"), D("0"))
    assert estado(pc) == (SituacaoParcela.ATIVA, D("4"), D("4"))
    assert (pa.sequencia, pc.sequencia) == sequencias
    assert (pa.quantidade_original, pc.quantidade_original) == (D("6"), D("8"))
    assert len(parcelas(produto)) == 2
    (entrada,) = auditorias(ACAO)
    assert entrada.autor_tipo == EntradaAuditoria.AutorTipo.SISTEMA
    assert entrada.objeto_id == str(produto.pk)
    assert entrada.alteracoes["parcelas"] == [[pa.pk, "6.000"], [pc.pk, "4.000"]]
    assert entrada.alteracoes["produto"] == produto.pk
    assert entrada.alteracoes["rodada"] == rodada.pk


@pytest.mark.acceptance
def test_novo_comprador_so_recebe_o_que_sobra_da_fila() -> None:  # A-2, cenário 76
    rodada, produto, estoque = cenario("10")
    a, c, d = (ContaFactory.create() for _ in range(3))
    pa = pendente(a, produto, 6)
    pc = pendente(c, produto, 8)
    alocar(rodada.fornecedor)
    with pytest.raises(EstoqueInsuficiente) as erro:
        adicionar_interesse(d, produto, "3")
    assert erro.value.mensagem == "Este produto está esgotado nesta rodada."
    alterar_estoque(administrador(), estoque, "13")
    assert estado(pc) == (SituacaoParcela.ATIVA, D("7"), D("1"))
    assert estado(pa) == (SituacaoParcela.ATIVA, D("6"), D("0"))
    with pytest.raises(EstoqueInsuficiente):
        adicionar_interesse(d, produto, "1")
    assert total_reservado(produto) == D("13")


@pytest.mark.acceptance
def test_liberacao_vai_para_a_fila_na_mesma_transacao() -> None:  # A-3, cenário 101
    _, produto, _ = cenario("10")
    d, outro, c = (ContaFactory.create() for _ in range(3))
    reservada(d, produto, 3)
    reservada(outro, produto, 7)
    pc = pendente(c, produto, 4)
    resumo = reduzir_interesse(d, produto, "3")
    assert resumo.reservado == 0
    assert estado(pc) == (SituacaoParcela.ATIVA, D("3"), D("1"))
    assert {p.situacao for p in parcelas(produto, d)} == {SituacaoParcela.REMOVIDA}
    assert total_reservado(produto) == D("10")


def test_reserva_nova_nao_passa_na_frente_da_fila() -> None:  # A-4, R-5
    _, produto, _ = cenario("10")
    e, outro, c = (ContaFactory.create() for _ in range(3))
    reservada(outro, produto, 4)
    pc = pendente(c, produto, 4)
    with pytest.raises(EstoqueInsuficiente) as erro:
        adicionar_interesse(e, produto, "4")
    assert erro.value.mensagem == "Há apenas 2 unidade disponível."
    assert estado(pc) == (SituacaoParcela.PENDENTE, D("0"), D("4"))
    assert parcelas(produto, e) == []
    assert auditorias(ACAO) == []
    adicionar_interesse(e, produto, "2")
    assert estado(pc) == (SituacaoParcela.ATIVA, D("4"), D("0"))
    assert parcelas(produto, e)[0].quantidade_reservada == D("2")
    assert total_reservado(produto) == D("10")


def test_sem_limite_a_fila_e_atendida_antes() -> None:  # A-5
    _, produto, _ = cenario(None)
    a, e = ContaFactory.create(), ContaFactory.create()
    pa = pendente(a, produto, 5)
    adicionar_interesse(e, produto, "2")
    assert estado(pa) == (SituacaoParcela.ATIVA, D("5"), D("0"))
    assert parcelas(produto, e)[0].quantidade_reservada == D("2")


@pytest.mark.acceptance
def test_a_fila_de_um_fornecedor_so_vai_para_as_rodadas_dele() -> None:  # A-6, cenário 102
    rodada_x, _, _ = cenario("10")
    y = RodadaFactory.create()
    q = ProdutoFactory.create(fornecedor=y.fornecedor, unidade=Unidade.UNIDADE)
    EstoqueDaRodadaFactory.create(rodada=y, produto=q, limite=None)
    pq = pendente(ContaFactory.create(), q, 4)
    assert alocar(rodada_x.fornecedor) == 0
    novo = ProdutoFactory.create(fornecedor=rodada_x.fornecedor, unidade=Unidade.UNIDADE)
    incluir_produto_na_rodada(administrador(), rodada_x, novo, "5")
    assert estado(pq) == (SituacaoParcela.PENDENTE, D("0"), D("4"))
    assert total_reservado(novo) == 0
    assert auditorias(ACAO) == []


def test_incluir_o_produto_na_rodada_atende_a_fila() -> None:  # A-7
    rodada, _, _ = cenario("10")
    p = ProdutoFactory.create(fornecedor=rodada.fornecedor, unidade=Unidade.UNIDADE)
    pa = pendente(ContaFactory.create(), p, 4)
    assert alocar(rodada.fornecedor) == 0
    assert estado(pa) == (SituacaoParcela.PENDENTE, D("0"), D("4"))
    incluir_produto_na_rodada(administrador(), rodada, p, "3")
    assert estado(pa) == (SituacaoParcela.ATIVA, D("3"), D("1"))


@pytest.mark.parametrize("etapa", [Etapa.FECHAMENTO_ENCERRADO, Etapa.PAGAMENTO, Etapa.CANCELADA])
def test_fora_das_etapas_que_reservam_nada_acontece(etapa: str) -> None:  # A-8
    rodada, produto, _ = cenario("10", etapa=etapa)
    pa = pendente(ContaFactory.create(), produto, 4)
    assert alocar(rodada.fornecedor) == 0
    assert estado(pa) == (SituacaoParcela.PENDENTE, D("0"), D("4"))
    assert auditorias(ACAO) == []


def test_em_fechamento_a_fila_e_atendida() -> None:  # A-9
    rodada, produto, _ = cenario("10", etapa=Etapa.FECHAMENTO)
    pa = pendente(ContaFactory.create(), produto, 4)
    assert alocar(rodada.fornecedor) == 4
    assert estado(pa) == (SituacaoParcela.ATIVA, D("4"), D("0"))


def test_livre_nao_multiplo_do_incremento() -> None:  # A-10
    rodada, produto, _ = cenario("10", incremento=D("4"))
    pa = pendente(ContaFactory.create(), produto, 12)
    assert alocar(rodada.fornecedor) == 8
    assert estado(pa) == (SituacaoParcela.ATIVA, D("8"), D("4"))


def test_parcela_em_pedido_nao_e_atendida() -> None:  # A-11
    rodada, produto, _ = cenario("10")
    parcela = ParcelaFactory.create(
        comprador=ContaFactory.create(),
        produto=produto,
        quantidade_original=D("4"),
        quantidade_reservada=D("2"),
        quantidade_pendente=D("2"),
        situacao=SituacaoParcela.EM_PEDIDO,
    )
    assert alocar(rodada.fornecedor) == 0
    assert estado(parcela) == (SituacaoParcela.EM_PEDIDO, D("2"), D("2"))
    assert auditorias(ACAO) == []


@pytest.mark.acceptance
def test_execucao_repetida_nao_altera_nada() -> None:  # A-12, cenário 78
    rodada, produto, _ = cenario("10")
    pendente(ContaFactory.create(), produto, 6)
    pendente(ContaFactory.create(), produto, 8)
    alocar(rodada.fornecedor)
    antes = [(p.pk, p.quantidade_reservada, p.quantidade_pendente) for p in parcelas(produto)]
    assert alocar(rodada.fornecedor) == 0
    depois = [(p.pk, p.quantidade_reservada, p.quantidade_pendente) for p in parcelas(produto)]
    assert depois == antes
    assert len(auditorias(ACAO)) == 1


def test_reduzir_o_limite_nao_atende_a_fila() -> None:  # A-13
    _, produto, estoque = cenario("10")
    reservada(ContaFactory.create(), produto, 2)
    pa = pendente(ContaFactory.create(), produto, 4)
    alterar_estoque(administrador(), estoque, "8")
    assert estado(pa) == (SituacaoParcela.PENDENTE, D("0"), D("4"))
    assert total_reservado(produto) == D("2")


@pytest.mark.django_db(transaction=True)
def test_alocar_exige_transacao() -> None:  # A-14
    rodada, _, _ = cenario("10")
    with pytest.raises(TransactionManagementError):
        alocar_pendentes(rodada.fornecedor)
