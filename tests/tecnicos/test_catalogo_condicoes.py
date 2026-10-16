"""E03-03: preço em qualquer etapa e múltiplo só em interesse (acceptance A-13 a A-18)."""

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import Client

from apps.catalogo.models import Produto
from apps.catalogo.servicos import alterar_multiplo, editar_produto
from apps.catalogo.sinais import preco_alterado
from apps.contas.models import Conta, Papel
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.models import Etapa
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, FornecedorFactory, ProdutoFactory, RodadaFactory

pytestmark = pytest.mark.django_db

D = Decimal
MENSAGEM = "As condições da rodada só podem ser alteradas na fase de interesse."


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


@pytest.fixture
def receptor() -> Iterator[list[tuple[Any, Decimal, Decimal, bool]]]:
    chamadas: list[tuple[Any, Decimal, Decimal, bool]] = []

    def ouvir(sender: Any, produto: Produto, anterior: Decimal, novo: Decimal, **kw: Any) -> None:
        chamadas.append((produto, anterior, novo, connection.in_atomic_block))

    preco_alterado.connect(ouvir, weak=False)
    yield chamadas
    preco_alterado.disconnect(ouvir)


def _produto_com_rodada(etapa: Etapa | None, **campos: Any) -> Produto:
    produto = ProdutoFactory.create(**campos)
    if etapa is not None:
        RodadaFactory.create(fornecedor=produto.fornecedor, etapa=etapa)
    return produto


def _editar(cliente: Client, produto: Produto, **campos: Any) -> Any:
    dados = {
        "nome": produto.nome,
        "descricao": produto.descricao,
        "preco": str(produto.preco).replace(".", ","),
        "disponivel": "on",
        **campos,
    }
    return cliente.post(f"/administracao/produtos/{produto.pk}/", dados)


@pytest.mark.acceptance
@pytest.mark.parametrize("etapa", [Etapa.INTERESSE, Etapa.FECHAMENTO, Etapa.PAGAMENTO])
def test_preco_muda_em_qualquer_etapa(
    admin_client: Client, etapa: Etapa, receptor: list[Any]
) -> None:  # A-13, §5.1, cenário 72
    produto = _produto_com_rodada(etapa, preco=D("10.00"))
    resposta = _editar(admin_client, produto, preco="12,50")
    assert resposta.status_code == 302
    produto.refresh_from_db()
    assert produto.preco == D("12.50")
    entrada = EntradaAuditoria.objects.get(acao="produto.alterar_preco")
    assert entrada.alteracoes == {"produto": produto.pk, "anterior": "10.00", "novo": "12.50"}
    editou = EntradaAuditoria.objects.get(acao="produto.editar")
    assert editou.alteracoes == {"produto": produto.pk, "campos": ["preco"]}
    assert len(receptor) == 1
    chamado, anterior, novo, dentro = receptor[0]
    assert chamado.pk == produto.pk
    assert (anterior, novo, dentro) == (D("10.00"), D("12.50"), True)


def test_receptor_que_falha_desfaz_a_edicao_do_preco() -> None:  # A-14
    admin = ContaFactory.create(administrador=True)
    produto = ProdutoFactory.create(preco=D("10.00"))

    def falha(sender: Any, **kwargs: Any) -> None:
        raise RuntimeError("falha do receptor")

    preco_alterado.connect(falha, weak=False)
    try:
        with pytest.raises(RuntimeError):
            editar_produto(admin, produto, preco="12.50")
    finally:
        preco_alterado.disconnect(falha)
    produto.refresh_from_db()
    assert produto.preco == D("10.00")
    assert EntradaAuditoria.objects.count() == 0


def test_editar_so_a_descricao_nao_avisa_preco(receptor: list[Any]) -> None:  # A-15
    admin = ContaFactory.create(administrador=True)
    produto = ProdutoFactory.create()
    editar_produto(admin, produto, descricao="Nova descrição")
    assert receptor == []
    entrada = EntradaAuditoria.objects.get()
    assert entrada.acao == "produto.editar"
    assert entrada.alteracoes["campos"] == ["descricao"]


def test_preco_igual_nao_avisa_nem_audita(receptor: list[Any]) -> None:
    admin = ContaFactory.create(administrador=True)
    produto = ProdutoFactory.create(preco=D("10.00"))
    editar_produto(admin, produto, preco="10,00", nome=produto.nome)
    assert receptor == []
    assert EntradaAuditoria.objects.count() == 0


def test_servico_de_edicao_recusa_campo_nao_editavel_e_preco_float() -> None:
    admin = ContaFactory.create(administrador=True)
    produto = ProdutoFactory.create()
    with pytest.raises(ValidationError):
        editar_produto(admin, produto, unidade="unidade")
    with pytest.raises(ValidationError):
        editar_produto(admin, produto, incremento="1")
    with pytest.raises(ValidationError):
        editar_produto(admin, produto, preco=10.5)
    produto.refresh_from_db()
    assert produto.unidade == "kg"
    assert EntradaAuditoria.objects.count() == 0


def test_so_o_administrador_edita_pelo_servico() -> None:
    comprador = ContaFactory.create()
    produto = ProdutoFactory.create()
    with pytest.raises(PermissionDenied):
        editar_produto(comprador, produto, nome="Invadido")
    with pytest.raises(PermissionDenied):
        alterar_multiplo(comprador, produto, "2")
    produto.refresh_from_db()
    assert EntradaAuditoria.objects.count() == 0


@pytest.mark.acceptance
def test_alterar_e_remover_o_multiplo_em_interesse(
    admin_client: Client,
) -> None:  # A-16, cenário 87
    produto = _produto_com_rodada(Etapa.INTERESSE, incremento=D("0.250"), multiplo=D("1.000"))
    url = f"/administracao/produtos/{produto.pk}/multiplo/"
    assert admin_client.post(url, {"multiplo": "2"}).status_code == 302
    produto.refresh_from_db()
    assert produto.multiplo == D("2.000")
    assert admin_client.post(url, {"multiplo": ""}).status_code == 302
    produto.refresh_from_db()
    assert produto.multiplo is None
    entradas = list(EntradaAuditoria.objects.filter(acao="produto.alterar_multiplo").order_by("id"))
    assert [e.alteracoes for e in entradas] == [
        {"produto": produto.pk, "anterior": "1.000", "novo": "2.000"},
        {"produto": produto.pk, "anterior": "2.000", "novo": None},
    ]


@pytest.mark.acceptance
def test_multiplo_invalido_em_interesse(admin_client: Client) -> None:  # A-17, cenário 87, R-2
    produto = _produto_com_rodada(Etapa.INTERESSE, incremento=D("0.250"), multiplo=D("1.000"))
    resposta = admin_client.post(
        f"/administracao/produtos/{produto.pk}/multiplo/", {"multiplo": "0,9"}
    )
    assert resposta.status_code == 200
    assert "multiplo" in resposta.context["form"].errors
    produto.refresh_from_db()
    assert produto.multiplo == D("1.000")
    assert EntradaAuditoria.objects.count() == 0


def test_mesmo_multiplo_nao_grava_nem_audita(admin_client: Client) -> None:
    produto = _produto_com_rodada(Etapa.INTERESSE, incremento=D("0.250"), multiplo=D("1.000"))
    resposta = admin_client.post(
        f"/administracao/produtos/{produto.pk}/multiplo/", {"multiplo": "1"}
    )
    assert resposta.status_code == 302
    assert EntradaAuditoria.objects.count() == 0


ETAPAS_CONGELADAS = [
    Etapa.FECHAMENTO,
    Etapa.FECHAMENTO_ENCERRADO,
    Etapa.PAGAMENTO,
    Etapa.AGUARDANDO_FORNECEDOR,
]


@pytest.mark.acceptance
@pytest.mark.parametrize("etapa", [*ETAPAS_CONGELADAS, None, Etapa.DISPONIVEL_PARA_RETIRADA])
def test_multiplo_congelado_pela_rota_e_pelo_servico(
    admin_client: Client, etapa: Etapa | None
) -> None:  # A-18, cenários 72 e 87, T-23
    produto = _produto_com_rodada(etapa, incremento=D("0.250"), multiplo=D("1.000"))
    resposta = admin_client.post(
        f"/administracao/produtos/{produto.pk}/multiplo/", {"multiplo": "2"}
    )
    assert resposta.status_code == 409
    assert MENSAGEM in resposta.content.decode()
    with pytest.raises(CondicoesCongeladas):
        alterar_multiplo(Conta.objects.get(papel=Papel.ADMINISTRADOR), produto, "2")
    produto.refresh_from_db()
    assert produto.multiplo == D("1.000")
    assert EntradaAuditoria.objects.count() == 0


def test_get_do_multiplo_fora_de_interesse_nao_mostra_formulario(admin_client: Client) -> None:
    produto = _produto_com_rodada(Etapa.PAGAMENTO, multiplo=None)
    resposta = admin_client.get(f"/administracao/produtos/{produto.pk}/multiplo/")
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert MENSAGEM in html
    assert 'name="multiplo"' not in html


def test_rodada_de_outro_fornecedor_nao_congela_o_multiplo(admin_client: Client) -> None:
    produto = _produto_com_rodada(Etapa.INTERESSE, incremento=D("0.250"))
    RodadaFactory.create(fornecedor=FornecedorFactory.create(), etapa=Etapa.PAGAMENTO)
    resposta = admin_client.post(
        f"/administracao/produtos/{produto.pk}/multiplo/", {"multiplo": "1"}
    )
    assert resposta.status_code == 302
    produto.refresh_from_db()
    assert produto.multiplo == D("1.000")
