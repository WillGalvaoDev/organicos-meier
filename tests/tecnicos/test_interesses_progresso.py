"""E05-04: progresso elegível e caixas (acceptance A-1 a A-11, A-13 a A-15)."""

import dataclasses
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalogo.models import Produto, Unidade
from apps.catalogo.servicos import editar_produto
from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.interesses.models import SituacaoParcela
from apps.interesses.progresso import (
    ParticipacaoDoComprador,
    ProgressoDaRodada,
    ProgressoDoProduto,
    progresso_da_rodada,
)
from apps.interesses.servicos import adicionar_interesse
from apps.rodadas.models import Etapa, Rodada
from tests.apoio.interesses import cenario, pendente, reservada
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    ParcelaFactory,
    ProdutoFactory,
)

pytestmark = pytest.mark.django_db

D = Decimal


def com_minimo(rodada: Rodada, minimo: str) -> Rodada:
    Fornecedor.objects.filter(pk=rodada.fornecedor_id).update(minimo=D(minimo))
    return Rodada.objects.select_related("fornecedor").get(pk=rodada.pk)


def so_produto(resultado: ProgressoDaRodada) -> ProgressoDoProduto:
    assert len(resultado.produtos) == 1
    return resultado.produtos[0]


@pytest.mark.acceptance
def test_dezoito_unidades_com_multiplo_doze() -> None:  # A-1, cenário 6
    rodada, produto, _ = cenario(None, preco=D("10.00"), multiplo=D("12"))
    reservada(ContaFactory.create(), produto, 18)
    item = so_produto(progresso_da_rodada(rodada))
    assert item.total_reservado == D("18")
    assert item.quantidade_elegivel == D("12")
    assert item.caixas_completas == 1
    assert item.faltam_para_proxima_caixa == D("6")
    assert item.excedente == D("6")
    assert item.valor_bruto == D("180.00")
    assert item.valor_elegivel == D("120.00")
    assert item.do_comprador is None


@pytest.fixture
def cenario_a_e_b() -> tuple[Rodada, Produto, Conta, Conta]:
    rodada, produto, _ = cenario(None, preco=D("10.00"), multiplo=D("12"))
    a = ContaFactory.create(nome="Ana Secreta", email_normalizado="ana@secreta.example")
    b = ContaFactory.create(nome="Beto Secreto", email_normalizado="beto@secreto.example")
    adicionar_interesse(a, produto, "8")
    adicionar_interesse(b, produto, "10")
    return rodada, produto, a, b


@pytest.mark.acceptance
def test_caixa_formada_pela_ordem_de_adicao(
    cenario_a_e_b: tuple[Rodada, Produto, Conta, Conta],
) -> None:  # A-2, cenário 7
    rodada, _, a, b = cenario_a_e_b
    para_a = so_produto(progresso_da_rodada(rodada, a))
    para_b = so_produto(progresso_da_rodada(rodada, b))
    assert (para_a.do_comprador.reservado, para_a.do_comprador.em_caixas) == (D("8"), D("8"))  # type: ignore[union-attr]
    assert para_a.do_comprador.excedente == 0  # type: ignore[union-attr]
    assert (para_b.do_comprador.reservado, para_b.do_comprador.em_caixas) == (D("10"), D("4"))  # type: ignore[union-attr]
    assert para_b.do_comprador.excedente == D("6")  # type: ignore[union-attr]
    for item in (para_a, para_b):
        assert (item.total_reservado, item.quantidade_elegivel) == (D("18"), D("12"))
        assert item.caixas_completas == 1
        assert item.valor_elegivel == D("120.00")


def test_acrescimo_posterior_fica_com_o_excedente(
    cenario_a_e_b: tuple[Rodada, Produto, Conta, Conta],
) -> None:  # A-3, cenário 8
    rodada, produto, a, b = cenario_a_e_b
    adicionar_interesse(a, produto, "2")
    para_a = so_produto(progresso_da_rodada(rodada, a))
    para_b = so_produto(progresso_da_rodada(rodada, b))
    assert (para_a.total_reservado, para_a.caixas_completas) == (D("20"), 1)
    assert (para_a.do_comprador.em_caixas, para_a.do_comprador.excedente) == (D("8"), D("2"))  # type: ignore[union-attr]
    assert (para_b.do_comprador.em_caixas, para_b.do_comprador.excedente) == (D("4"), D("6"))  # type: ignore[union-attr]


@pytest.mark.acceptance
def test_pendentes_nao_entram_no_minimo() -> None:  # A-4, cenário 104
    rodada, produto, _ = cenario(None, preco=D("10.00"))
    rodada = com_minimo(rodada, "100.00")
    a, c = ContaFactory.create(), ContaFactory.create()
    reservada(a, produto, 8)
    pendente(c, produto, 5)
    resultado = progresso_da_rodada(rodada, c)
    assert resultado.valor_elegivel == D("80.00")
    assert resultado.percentual == 80
    assert resultado.atingido is False
    assert resultado.falta == D("20.00")
    participacao = so_produto(resultado).do_comprador
    assert participacao is not None
    assert (participacao.reservado, participacao.pendente) == (D("0"), D("5"))


@pytest.mark.parametrize(
    ("preco", "percentual", "atingido"),
    [("99.99", 99, False), ("100.00", 100, True), ("250.00", 100, True)],
)
def test_percentual_nos_limites_do_minimo(
    preco: str, percentual: int, atingido: bool
) -> None:  # A-14
    rodada, produto, _ = cenario(None, preco=D(preco))
    rodada = com_minimo(rodada, "100.00")
    reservada(ContaFactory.create(), produto, 1)
    resultado = progresso_da_rodada(rodada)
    assert (resultado.percentual, resultado.atingido) == (percentual, atingido)


def test_minimo_zero_ja_esta_atingido() -> None:  # A-14
    rodada, _, _ = cenario(None)
    # o banco não aceita mínimo zero (`fornecedor_minimo_positivo`): o ramo é exercitado em memória
    rodada.fornecedor.minimo = D("0.00")
    resultado = progresso_da_rodada(rodada)
    assert (resultado.percentual, resultado.atingido, resultado.falta) == (100, True, D("0"))
    assert resultado.valor_elegivel == 0


def test_comprador_sem_parcela_tem_participacao_zerada() -> None:  # A-15
    rodada, produto, _ = cenario(None, multiplo=D("12"))
    reservada(ContaFactory.create(), produto, 5)
    b = ContaFactory.create()
    assert so_produto(progresso_da_rodada(rodada, b)).do_comprador == ParticipacaoDoComprador(
        reservado=D("0"), pendente=D("0"), em_caixas=D("0"), excedente=D("0"), subtotal=D("0.00")
    )


@pytest.mark.acceptance
def test_arredondamento_por_comprador() -> None:  # A-5, cenário 89
    rodada, produto, _ = cenario(None, unidade=Unidade.KG, preco=D("2.50"), incremento=D("0.25"))
    for _ in range(2):
        reservada(ContaFactory.create(), produto, "0.25")
    item = so_produto(progresso_da_rodada(rodada))
    assert item.valor_elegivel == D("1.26")
    assert item.valor_bruto == D("1.25")


def test_multiplo_fracionario_e_total_zero() -> None:  # A-6
    rodada, kg, _ = cenario(None, unidade=Unidade.KG, incremento=D("0.25"), multiplo=D("1"))
    segundo = ProdutoFactory.create(
        fornecedor=rodada.fornecedor, unidade=Unidade.UNIDADE, multiplo=D("12"), nome="Zzz"
    )
    EstoqueDaRodadaFactory.create(rodada=rodada, produto=segundo, limite=None)
    reservada(ContaFactory.create(), kg, "2.75")
    por_produto = {item.produto.pk: item for item in progresso_da_rodada(rodada).produtos}
    assert {kg.pk, segundo.pk} <= set(por_produto)
    primeiro, vazio = por_produto[kg.pk], por_produto[segundo.pk]
    assert (primeiro.caixas_completas, primeiro.quantidade_elegivel) == (2, D("2"))
    assert (primeiro.excedente, primeiro.faltam_para_proxima_caixa) == (D("0.75"), D("0.25"))
    assert (vazio.caixas_completas, vazio.faltam_para_proxima_caixa) == (0, D("12"))
    assert vazio.excedente == 0


def test_produtos_nao_se_misturam_para_completar_caixa() -> None:  # A-7
    rodada, um, _ = cenario(None, multiplo=D("12"))
    dois = ProdutoFactory.create(
        fornecedor=rodada.fornecedor, unidade=Unidade.UNIDADE, multiplo=D("12")
    )
    EstoqueDaRodadaFactory.create(rodada=rodada, produto=dois, limite=None)
    for produto in (um, dois):
        reservada(ContaFactory.create(), produto, 7)
    resultado = progresso_da_rodada(rodada)
    assert [item.caixas_completas for item in resultado.produtos] == [0, 0]
    assert resultado.valor_elegivel == 0


@pytest.mark.acceptance
def test_atingir_o_minimo_nao_muda_a_etapa_nem_grava() -> None:  # A-8, cenário 4
    rodada, produto, _ = cenario(None, preco=D("10.00"))
    rodada = com_minimo(rodada, "50.00")
    adicionar_interesse(ContaFactory.create(), produto, "6")
    with CaptureQueriesContext(connection) as consultas:
        resultado = progresso_da_rodada(rodada)
    assert resultado.atingido is True
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.INTERESSE
    escritas = [
        c["sql"] for c in consultas if c["sql"].lstrip().upper().startswith(("INSERT", "UPDATE"))
    ]
    assert escritas == []


def test_so_parcela_ativa_conta() -> None:  # A-9
    rodada, produto, _ = cenario(None)
    comprador = ContaFactory.create()
    reservada(comprador, produto, 4)
    ParcelaFactory.create(
        comprador=comprador,
        produto=produto,
        quantidade_original=D("3"),
        quantidade_reservada=D("3"),
        situacao=SituacaoParcela.EM_PEDIDO,
    )
    ParcelaFactory.create(
        comprador=comprador,
        produto=produto,
        quantidade_original=D("2"),
        quantidade_reservada=D("0"),
        quantidade_pendente=D("0"),
        situacao=SituacaoParcela.REMOVIDA,
    )
    assert so_produto(progresso_da_rodada(rodada)).total_reservado == D("4")


def _contar(rodada: Rodada, comprador: Conta | None = None) -> int:
    with CaptureQueriesContext(connection) as consultas:
        progresso_da_rodada(rodada, comprador)
    return len(consultas)


def test_numero_de_consultas_nao_cresce() -> None:  # A-10
    pequena, produto, _ = cenario(None)
    a, b = ContaFactory.create(), ContaFactory.create()
    reservada(a, produto, 2)
    reservada(b, produto, 3)
    pequena = Rodada.objects.select_related("fornecedor").get(pk=pequena.pk)
    poucas = _contar(pequena, a)
    grande, primeiro, _ = cenario(None)
    produtos = [primeiro] + [
        ProdutoFactory.create(fornecedor=grande.fornecedor, unidade=Unidade.UNIDADE)
        for _ in range(7)
    ]
    for item in produtos[1:]:
        EstoqueDaRodadaFactory.create(rodada=grande, produto=item, limite=None)
    compradores = [ContaFactory.create() for _ in range(30)]
    for indice, comprador in enumerate(compradores):
        reservada(comprador, produtos[indice % 8], 1 + indice % 3)
    grande = Rodada.objects.select_related("fornecedor").get(pk=grande.pk)
    muitas = _contar(grande, compradores[0])
    assert poucas == muitas
    assert poucas <= 4


def test_resultado_nao_expoe_outros_compradores(
    cenario_a_e_b: tuple[Rodada, Produto, Conta, Conta],
) -> None:  # A-11
    rodada, _, a, b = cenario_a_e_b
    resultado = progresso_da_rodada(rodada, a)
    texto = repr(resultado)
    for segredo in ("Beto", "beto@", "Ana Secreta", "ana@", str(b.email_normalizado)):
        assert segredo not in texto
    nomes = {f.name for f in dataclasses.fields(ProgressoDoProduto)}
    assert not nomes & {"conta", "comprador", "compradores", "parcelas", "parcela"}
    nomes_participacao = {f.name for f in dataclasses.fields(ParticipacaoDoComprador)}
    assert nomes_participacao == {"reservado", "pendente", "em_caixas", "excedente", "subtotal"}
    assert so_produto(progresso_da_rodada(rodada)).do_comprador is None


def test_alteracao_de_preco_muda_o_progresso_na_proxima_leitura() -> None:  # A-13
    rodada, produto, _ = cenario(None, preco=D("10.00"))
    rodada = com_minimo(rodada, "100.00")
    reservada(ContaFactory.create(), produto, 12)
    assert progresso_da_rodada(rodada).valor_elegivel == D("120.00")
    editar_produto(Conta.objects.get(papel="administrador"), produto, preco="5.00")
    resultado = progresso_da_rodada(rodada)
    assert resultado.valor_elegivel == D("60.00")
    assert resultado.atingido is False
