"""E03-03: cadastro e edição de produtos (acceptance A-1, A-10 a A-12, A-19, A-20 e A-23)."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import Client

from apps.catalogo.models import Produto
from apps.catalogo.servicos import editar_produto
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.models import Etapa, Rodada
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, FornecedorFactory, ProdutoFactory, RodadaFactory

pytestmark = pytest.mark.django_db

D = Decimal


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def test_cadastro_grava_valores_exatos_e_audita(admin_client: Client) -> None:  # A-1
    fornecedor = FornecedorFactory.create()
    resposta = admin_client.post(
        f"/administracao/fornecedores/{fornecedor.pk}/produtos/novo/",
        {
            "nome": " Banana ",
            "descricao": "Prata",
            "unidade": "kg",
            "incremento": "0,25",
            "preco": "7,99",
            "multiplo": "",
            "disponivel": "on",
        },
    )
    assert resposta.status_code == 302
    assert resposta["Location"] == f"/administracao/fornecedores/{fornecedor.pk}/"
    produto = Produto.objects.get()
    assert produto.fornecedor_id == fornecedor.pk
    assert produto.nome == "Banana"
    assert produto.descricao == "Prata"
    assert produto.unidade == "kg"
    assert produto.incremento == D("0.250")
    assert str(produto.incremento) == "0.250"
    assert produto.preco == D("7.99")
    assert produto.multiplo is None
    assert produto.disponivel is True
    entrada = EntradaAuditoria.objects.get(acao="produto.criar")
    assert entrada.alteracoes == {"produto": produto.pk, "fornecedor": fornecedor.pk}


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("nome", ""),
        ("nome", "x" * 151),
        ("unidade", "caixote"),
        ("unidade", ""),
        ("preco", "0"),
        ("preco", "0,001"),
        ("preco", "abc"),
        ("preco", ""),
        ("descricao", "x" * 2001),
    ],
)
def test_cadastro_recusa_campo_invalido(admin_client: Client, campo: str, valor: str) -> None:
    fornecedor = FornecedorFactory.create()
    dados = {
        "nome": "Banana",
        "unidade": "kg",
        "incremento": "1",
        "preco": "7,99",
        "multiplo": "",
        "descricao": "",
        **{campo: valor},
    }
    resposta = admin_client.post(
        f"/administracao/fornecedores/{fornecedor.pk}/produtos/novo/", dados
    )
    assert resposta.status_code == 200
    assert campo in resposta.context["form"].errors
    assert Produto.objects.count() == 0


def test_preco_de_um_centavo_e_aceito(admin_client: Client) -> None:
    fornecedor = FornecedorFactory.create()
    admin_client.post(
        f"/administracao/fornecedores/{fornecedor.pk}/produtos/novo/",
        {"nome": "X", "unidade": "pacote", "incremento": "1", "preco": "0,01"},
    )
    assert Produto.objects.get().preco == D("0.01")


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE catalogo_produto SET incremento = 0 WHERE id = %s",
        "UPDATE catalogo_produto SET preco = 0 WHERE id = %s",
        "UPDATE catalogo_produto SET multiplo = 1 WHERE id = %s",
    ],
)
def test_banco_recusa_valores_invalidos(sql: str) -> None:  # A-10
    produto = ProdutoFactory.create(incremento=D("0.300"))
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, [produto.pk])
    produto.refresh_from_db()
    assert produto.incremento == D("0.300")
    assert produto.preco == D("10.00")
    assert produto.multiplo is None


def test_banco_aceita_multiplo_divisivel() -> None:
    produto = ProdutoFactory.create(incremento=D("0.250"))
    with connection.cursor() as cursor:
        cursor.execute("UPDATE catalogo_produto SET multiplo = 1 WHERE id = %s", [produto.pk])
    produto.refresh_from_db()
    assert produto.multiplo == D("1.000")


def test_banco_recusa_troca_de_unidade_e_de_fornecedor_e_exclusao() -> None:  # A-11
    produto = ProdutoFactory.create()
    outro = FornecedorFactory.create()
    for sql, parametros in (
        ("UPDATE catalogo_produto SET unidade = 'unidade' WHERE id = %s", [produto.pk]),
        (
            "UPDATE catalogo_produto SET fornecedor_id = %s WHERE id = %s",
            [outro.pk, produto.pk],
        ),
        ("DELETE FROM catalogo_produto WHERE id = %s", [produto.pk]),
    ):
        with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql, parametros)
    produto.refresh_from_db()
    assert produto.unidade == "kg"
    assert produto.fornecedor_id != outro.pk


def test_update_comum_do_orm_passa_pelo_gatilho() -> None:
    produto = ProdutoFactory.create()
    produto.nome = "Outro nome"
    produto.save()  # reenvia unidade e fornecedor com o mesmo valor
    produto.refresh_from_db()
    assert produto.nome == "Outro nome"


def test_edicao_ignora_unidade_fornecedor_e_incremento(admin_client: Client) -> None:  # A-12
    produto = ProdutoFactory.create(nome="Antigo", incremento=D("0.500"))
    outro = FornecedorFactory.create()
    original = produto.fornecedor_id
    resposta = admin_client.post(
        f"/administracao/produtos/{produto.pk}/",
        {
            "nome": "Novo nome",
            "descricao": "",
            "preco": "10,00",
            "disponivel": "on",
            "unidade": "unidade",
            "fornecedor": str(outro.pk),
            "incremento": "1",
        },
    )
    assert resposta.status_code == 302
    produto.refresh_from_db()
    assert produto.nome == "Novo nome"
    assert produto.unidade == "kg"
    assert produto.fornecedor_id == original
    assert produto.incremento == D("0.500")
    entrada = EntradaAuditoria.objects.get(acao="produto.editar")
    assert entrada.alteracoes == {"produto": produto.pk, "campos": ["nome"]}


@pytest.mark.parametrize(("campo", "dados"), [("nome", {"nome": ""}), ("preco", {"preco": "0"})])
def test_edicao_invalida_nao_grava(admin_client: Client, campo: str, dados: dict[str, str]) -> None:
    produto = ProdutoFactory.create(nome="Intacto")
    corpo = {"nome": "Intacto", "preco": "10,00", "descricao": "", "disponivel": "on", **dados}
    resposta = admin_client.post(f"/administracao/produtos/{produto.pk}/", corpo)
    assert resposta.status_code == 200
    assert campo in resposta.context["form"].errors
    produto.refresh_from_db()
    assert produto.nome == "Intacto"
    assert produto.preco == D("10.00")
    assert EntradaAuditoria.objects.count() == 0


def test_produto_novo_com_rodada_em_fechamento_e_aceito(admin_client: Client) -> None:  # A-19
    rodada = RodadaFactory.create(etapa=Etapa.FECHAMENTO)
    resposta = admin_client.post(
        f"/administracao/fornecedores/{rodada.fornecedor_id}/produtos/novo/",
        {"nome": "Novo", "unidade": "kg", "incremento": "1", "preco": "5,00"},
    )
    assert resposta.status_code == 302
    assert Produto.objects.filter(fornecedor=rodada.fornecedor).count() == 1
    assert Rodada.objects.get().etapa == Etapa.FECHAMENTO


def test_marcar_indisponivel_so_grava_o_produto() -> None:  # A-20
    admin = ContaFactory.create(administrador=True)
    produto = ProdutoFactory.create()
    editar_produto(admin, produto, disponivel=False)
    produto.refresh_from_db()
    assert produto.disponivel is False
    entradas = EntradaAuditoria.objects.all()
    assert [e.acao for e in entradas] == ["produto.editar"]
    assert entradas[0].alteracoes["campos"] == ["disponivel"]


def test_detalhe_do_fornecedor_lista_produtos_com_quantidades_formatadas(
    admin_client: Client,
) -> None:  # A-23
    fornecedor = FornecedorFactory.create()
    ProdutoFactory.create(fornecedor=fornecedor, nome="Banana", incremento=D("0.250"))
    ProdutoFactory.create(fornecedor=fornecedor, nome="Ovos", incremento=D("1.000"))
    ProdutoFactory.create(
        fornecedor=fornecedor, nome="Queijo", incremento=D("1.500"), multiplo=D("3.000")
    )
    outro = ProdutoFactory.create(nome="De outro fornecedor")
    html = admin_client.get(f"/administracao/fornecedores/{fornecedor.pk}/").content.decode()
    for esperado in ("Banana", "Ovos", "Queijo", "0,25", "1,5", "kg"):
        assert esperado in html
    for proibido in ("0,250", "1,500", "1,000", "3,000", outro.nome):
        assert proibido not in html
    assert f"/administracao/produtos/{outro.pk}/" not in html
    assert f"/administracao/fornecedores/{fornecedor.pk}/produtos/novo/" in html


def test_edicao_mostra_quantidades_formatadas(admin_client: Client) -> None:  # A-23
    produto = ProdutoFactory.create(incremento=D("0.250"), multiplo=D("1.000"), preco=D("7.99"))
    html = admin_client.get(f"/administracao/produtos/{produto.pk}/").content.decode()
    assert "0,25" in html
    assert "7,99" in html
    assert "0,250" not in html
    assert "1,000" not in html


def test_ids_inexistentes_dao_404(admin_client: Client) -> None:
    for rota in (
        "/administracao/fornecedores/999999/produtos/novo/",
        "/administracao/produtos/999999/",
        "/administracao/produtos/999999/multiplo/",
    ):
        assert admin_client.get(rota).status_code == 404, rota
