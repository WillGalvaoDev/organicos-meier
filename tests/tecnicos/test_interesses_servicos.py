"""E05-01: adição e redução de interesse com reserva de estoque (acceptance A-1 a A-12)."""

from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db.transaction import TransactionManagementError

from apps.catalogo.models import Unidade
from apps.catalogo.quantidades import QuantidadeInvalida, calcular_subtotal
from apps.contas.models import Conta
from apps.interesses.consultas import total_reservado
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.interesses.servicos import (
    EstoqueInsuficiente,
    ProdutoForaDaRodada,
    ReducaoAcimaDoReservado,
    ResumoDoInteresse,
    adicionar_interesse,
    definir_interesse,
    reduzir_interesse,
)
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.valores import MENSAGEM_CAPACIDADE_QUANTIDADE
from apps.rodadas.condicoes import (
    MENSAGEM_INTERESSES,
    InteressesBloqueados,
    travar_rodada_para_interesses,
)
from apps.rodadas.models import Etapa
from tests.apoio.interesses import auditorias, cenario, parcelas
from tests.fabricas import (
    ContaFactory,
    FornecedorFactory,
    ParcelaFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = pytest.mark.django_db

D = Decimal


def test_adicionar_cria_parcela_e_audita() -> None:  # A-1
    rodada, produto, _ = cenario("10")
    a = ContaFactory.create(nome="Ana Silva", email_normalizado="ana@exemplo.com")
    resumo = adicionar_interesse(a, produto, "4")
    assert resumo == ResumoDoInteresse(reservado=D("4.000"), pendente=D("0.000"))
    (parcela,) = parcelas(produto)
    assert parcela.comprador_id == a.pk
    assert (parcela.quantidade_original, parcela.quantidade_reservada) == (D("4"), D("4"))
    assert parcela.quantidade_pendente == 0
    assert parcela.situacao == SituacaoParcela.ATIVA
    (entrada,) = auditorias("interesse.adicionar")
    assert entrada.objeto_id == str(parcela.pk)
    assert entrada.autor_id == str(a.pk)
    assert entrada.alteracoes == {
        "parcela": parcela.pk,
        "produto": produto.pk,
        "rodada": rodada.pk,
        "quantidade": "4.000",
    }
    assert "Ana Silva" not in str(entrada.alteracoes)
    assert "ana@exemplo.com" not in str(entrada.alteracoes)


@pytest.mark.acceptance
def test_acrescimo_posterior_vai_para_o_fim_da_fila() -> None:  # A-2, cenário 8
    _, produto, _ = cenario(None)
    a, b = ContaFactory.create(), ContaFactory.create()
    adicionar_interesse(a, produto, "8")
    adicionar_interesse(b, produto, "10")
    adicionar_interesse(a, produto, "2")
    pa8, pb10, pa2 = parcelas(produto)
    assert pa8.sequencia < pb10.sequencia < pa2.sequencia
    assert (pa8.quantidade_original, pb10.quantidade_original, pa2.quantidade_original) == (
        D("8"),
        D("10"),
        D("2"),
    )
    resumo = reduzir_interesse(a, produto, "2")
    pa8.refresh_from_db()
    pa2.refresh_from_db()
    assert pa2.situacao == SituacaoParcela.REMOVIDA
    assert (pa2.quantidade_reservada, pa2.quantidade_pendente) == (0, 0)
    assert (pa8.situacao, pa8.quantidade_reservada) == (SituacaoParcela.ATIVA, D("8"))
    assert resumo.reservado == D("8")


def test_reducao_atravessa_parcelas_da_mais_recente_para_a_mais_antiga() -> None:  # A-3
    _, produto, _ = cenario(None)
    a = ContaFactory.create()
    criadas = [
        ParcelaFactory.create(
            comprador=a, produto=produto, quantidade_original=D(q), quantidade_reservada=D(q)
        )
        for q in (2, 3, 4)
    ]
    antes = [(p.quantidade_original, p.sequencia) for p in criadas]
    reduzir_interesse(a, produto, "5")
    for p in criadas:
        p.refresh_from_db()
    p2, p3, p4 = criadas
    assert p4.situacao == SituacaoParcela.REMOVIDA
    assert (p3.situacao, p3.quantidade_reservada) == (SituacaoParcela.ATIVA, D("2"))
    assert (p2.situacao, p2.quantidade_reservada) == (SituacaoParcela.ATIVA, D("2"))
    assert [(p.quantidade_original, p.sequencia) for p in criadas] == antes
    (entrada,) = auditorias("interesse.reduzir")
    assert entrada.objeto_id == str(produto.pk)
    assert entrada.alteracoes["parcelas"] == [p4.pk, p3.pk]
    assert entrada.alteracoes["quantidade"] == "5.000"


def test_excedente_e_recusado_por_inteiro() -> None:  # A-4
    _, produto, _ = cenario("10")
    a, b = ContaFactory.create(), ContaFactory.create()
    ParcelaFactory.create(
        comprador=b, produto=produto, quantidade_original=D(7), quantidade_reservada=D(7)
    )
    with pytest.raises(EstoqueInsuficiente) as erro:
        adicionar_interesse(a, produto, "4")
    assert erro.value.mensagem == "Há apenas 3 unidade disponível."
    assert erro.value.disponivel == D("3")
    assert len(parcelas(produto)) == 1
    assert auditorias("interesse.adicionar") == []


def test_estoque_zero_esta_esgotado() -> None:  # A-4
    _, produto, _ = cenario("0")
    with pytest.raises(EstoqueInsuficiente) as erro:
        adicionar_interesse(ContaFactory.create(), produto, "1")
    assert erro.value.mensagem == "Este produto está esgotado nesta rodada."
    assert parcelas(produto) == []
    assert auditorias("interesse.adicionar") == []


CASOS_DE_QUANTIDADE = [
    (Unidade.KG, "0.5", "1.5", True),
    (Unidade.KG, "0.5", "1.2", False),
    (Unidade.LITRO, "0.5", "1.5", True),
    (Unidade.LITRO, "0.5", "1.2", False),
    (Unidade.UNIDADE, "1", "2", True),
    (Unidade.UNIDADE, "1", "2.5", False),
    (Unidade.KG, "0.25", "0.75", True),
    (Unidade.UNIDADE, "1", "12", True),
    (Unidade.UNIDADE, "1", "12.5", False),
    (Unidade.UNIDADE, "2", "4", True),
    (Unidade.UNIDADE, "2", "3", False),
    (Unidade.KG, "0.25", "1.25", True),
    (Unidade.CAIXA, "1", "3", True),
    (Unidade.CAIXA, "1", "1.5", False),
]


@pytest.mark.acceptance
@pytest.mark.parametrize(("unidade", "incremento", "entrada", "aceita"), CASOS_DE_QUANTIDADE)
def test_quantidades_e_incrementos(
    unidade: str, incremento: str, entrada: str, aceita: bool
) -> None:  # A-5, cenários 63, 85, 109
    _, produto, _ = cenario(None, unidade=unidade, incremento=D(incremento), preco=D("12.00"))
    a = ContaFactory.create()
    if aceita:
        resumo = adicionar_interesse(a, produto, entrada)
        assert resumo.reservado == D(entrada)
        (parcela,) = parcelas(produto)
        assert parcela.quantidade_reservada == D(entrada)
        if entrada == "1.5":
            assert calcular_subtotal(produto.preco, parcela.quantidade_reservada) == D("18.00")
    else:
        with pytest.raises(QuantidadeInvalida):
            adicionar_interesse(a, produto, entrada)
        assert parcelas(produto) == []
        assert auditorias("interesse.adicionar") == []


@pytest.mark.parametrize("entrada", [1.5, "abc", "-1", "0", "1000000000.000"])
def test_entradas_invalidas_nao_gravam(entrada: Any) -> None:  # A-5
    _, produto, _ = cenario(None, incremento=D("0.5"), unidade=Unidade.KG)
    with pytest.raises(QuantidadeInvalida) as erro:
        adicionar_interesse(ContaFactory.create(), produto, entrada)
    if entrada == "1000000000.000":
        assert str(erro.value) == MENSAGEM_CAPACIDADE_QUANTIDADE
    assert parcelas(produto) == []


def test_reducao_acima_do_reservado_e_quantidade_invalida() -> None:  # A-6
    _, produto, _ = cenario(None)
    a = ContaFactory.create()
    adicionar_interesse(a, produto, "4")
    with pytest.raises(ReducaoAcimaDoReservado) as erro:
        reduzir_interesse(a, produto, "5")
    assert erro.value.mensagem == "A redução passa da quantidade reservada (4)."
    with pytest.raises(QuantidadeInvalida):
        reduzir_interesse(a, produto, "0.5")
    (parcela,) = parcelas(produto)
    assert parcela.quantidade_reservada == D("4")
    assert auditorias("interesse.reduzir") == []


def test_definir_interesse_e_idempotente() -> None:  # A-7
    _, produto, _ = cenario(None)
    a = ContaFactory.create()
    adicionar_interesse(a, produto, "4")
    resumo = definir_interesse(a, produto, "6")
    assert resumo.reservado == D("6")
    assert [p.quantidade_original for p in parcelas(produto)] == [D("4"), D("2")]
    antes = (len(auditorias("interesse.adicionar")), len(auditorias("interesse.reduzir")))
    assert definir_interesse(a, produto, "6").reservado == D("6")
    assert len(parcelas(produto)) == 2
    assert (len(auditorias("interesse.adicionar")), len(auditorias("interesse.reduzir"))) == antes
    assert definir_interesse(a, produto, "1").reservado == D("1")
    primeira, segunda = parcelas(produto)
    assert (primeira.quantidade_reservada, segunda.situacao) == (D("1"), SituacaoParcela.REMOVIDA)
    resumo = definir_interesse(a, produto, "0")
    assert resumo == ResumoDoInteresse(D("0"), D("0"))
    assert {p.situacao for p in parcelas(produto)} == {SituacaoParcela.REMOVIDA}


@pytest.mark.parametrize("quem", ["suspenso", "fornecedor", "administrador"])
@pytest.mark.parametrize("servico", [adicionar_interesse, reduzir_interesse, definir_interesse])
def test_so_comprador_ativo_mexe_em_interesse(quem: str, servico: Any) -> None:  # A-8
    _, produto, _ = cenario(None)
    conta = {
        "suspenso": lambda: ContaFactory.create(suspensa=True),
        "fornecedor": lambda: ContaFactory.create(fornecedor=True),
        "administrador": lambda: Conta.objects.get(papel="administrador"),
    }[quem]()
    with pytest.raises(PermissionDenied):
        servico(conta, produto, "1")
    assert parcelas(produto) == []
    assert EntradaAuditoria.objects.filter(acao__startswith="interesse.").count() == 0


@pytest.mark.parametrize(
    ("etapa", "codigo"),
    [
        (Etapa.INTERESSE, None),
        (Etapa.FECHAMENTO, None),
        (Etapa.FECHAMENTO_ENCERRADO, "etapa_bloqueada"),
        (Etapa.PAGAMENTO, "etapa_bloqueada"),
        (Etapa.AGUARDANDO_FORNECEDOR, "etapa_bloqueada"),
    ],
)
def test_etapas_que_aceitam_interesse(etapa: str, codigo: str | None) -> None:  # A-9
    _, produto, _ = cenario(None, etapa=etapa)
    a = ContaFactory.create()
    if codigo is None:
        assert adicionar_interesse(a, produto, "1").reservado == D("1")
        return
    with pytest.raises(InteressesBloqueados) as erro:
        adicionar_interesse(a, produto, "1")
    assert erro.value.codigo == codigo
    assert str(erro.value) == MENSAGEM_INTERESSES
    assert parcelas(produto) == []


def test_sem_rodada_ativa_e_bloqueado() -> None:  # A-9
    produto = ProdutoFactory.create(unidade=Unidade.UNIDADE)
    with pytest.raises(InteressesBloqueados) as erro:
        adicionar_interesse(ContaFactory.create(), produto, "1")
    assert erro.value.codigo == "sem_rodada_ativa"
    assert str(erro.value) == MENSAGEM_INTERESSES


def test_produto_fora_da_rodada() -> None:  # A-10
    rodada, _, _ = cenario("10")
    fora = ProdutoFactory.create(fornecedor=rodada.fornecedor, unidade=Unidade.UNIDADE)
    g = FornecedorFactory.create()
    RodadaFactory.create(fornecedor=g)
    outro = ProdutoFactory.create(fornecedor=g, unidade=Unidade.UNIDADE)
    a = ContaFactory.create()
    for produto in (fora, outro):
        with pytest.raises(ProdutoForaDaRodada) as erro:
            adicionar_interesse(a, produto, "1")
        assert erro.value.mensagem == "Este produto não está disponível para interesse agora."
    assert ParcelaDeInteresse.objects.count() == 0
    assert EntradaAuditoria.objects.filter(acao__startswith="interesse.").count() == 0


def test_produto_indisponivel_continua_aceitando() -> None:  # A-11
    _, produto, _ = cenario(None, disponivel=False)
    a = ContaFactory.create()
    assert adicionar_interesse(a, produto, "2").reservado == D("2")
    assert reduzir_interesse(a, produto, "1").reservado == D("1")


@pytest.mark.django_db(transaction=True)
def test_travar_rodada_exige_transacao() -> None:  # A-12
    rodada, _, _ = cenario(None)
    with pytest.raises(TransactionManagementError):
        travar_rodada_para_interesses(rodada.fornecedor)


def test_total_reservado_nunca_passa_do_limite() -> None:
    _, produto, _ = cenario("5")
    for _ in range(3):
        try:
            adicionar_interesse(ContaFactory.create(), produto, "2")
        except EstoqueInsuficiente:
            pass
    assert total_reservado(produto) == D("4")
