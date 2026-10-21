"""E08-02 correção R04: a menor quantidade de um produto custa ao menos R$ 0,01 depois do
arredondamento (acceptance A-22 a A-25 e A-27)."""

from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import Client

from apps.catalogo.models import Produto
from apps.catalogo.servicos import (
    IncrementoIncompativel,
    alterar_incremento,
    criar_produto,
    editar_produto,
)
from apps.catalogo.sinais import preco_alterado
from apps.contas.models import Conta, Papel
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.models import Etapa
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import (
    ContaFactory,
    FornecedorFactory,
    ParcelaFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = pytest.mark.django_db

D = Decimal
MENSAGEM_PRECO = (
    "Com este preço e este incremento, a menor quantidade custaria menos de R$ 0,01. "
    "Aumente o preço ou o incremento."
)
MENSAGEM_INCREMENTO = (
    "Com este incremento, a menor quantidade custaria menos de R$ 0,01 ao preço atual."
)
RESTRICAO = "produto_menor_quantidade_custa_um_centavo"


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def _admin() -> Conta:
    return Conta.objects.filter(papel=Papel.ADMINISTRADOR).first() or ContaFactory.create(
        administrador=True
    )


def _criar(fornecedor: Any, incremento: str, preco: str) -> Produto:
    return criar_produto(
        _admin(),
        fornecedor,
        nome="Produto",
        unidade="kg",
        incremento=incremento,
        preco=preco,
    )


def test_criar_recusa_a_menor_quantidade_abaixo_de_um_centavo(webauthn: Any) -> None:  # A-22
    fornecedor = FornecedorFactory.create()
    with pytest.raises(ValidationError) as erro:
        _criar(fornecedor, "0.001", "4.99")
    assert erro.value.message_dict == {"preco": [MENSAGEM_PRECO]}
    assert not Produto.objects.exists()
    assert not EntradaAuditoria.objects.filter(acao="produto.criar").exists()
    limite = _criar(fornecedor, "0.001", "5.00")  # 0,005 exato: fronteira inclusiva
    pequeno = _criar(fornecedor, "1", "0.01")
    assert (limite.preco, pequeno.incremento) == (D("5.00"), D("1.000"))
    assert Produto.objects.count() == 2


def test_editar_preco_recusa_e_nada_e_gravado(webauthn: Any) -> None:  # A-23
    produto = ProdutoFactory.create(incremento=D("0.001"), preco=D("5.00"))
    ParcelaFactory.create(produto=produto)
    avisos: list[Any] = []

    def receptor(sender: Any, **kwargs: Any) -> None:
        avisos.append(kwargs)

    preco_alterado.connect(receptor, weak=False, dispatch_uid="teste.valor_minimo")
    try:
        with pytest.raises(ValidationError) as erro:
            editar_produto(_admin(), produto, preco="4.99")
        assert erro.value.message_dict == {"preco": [MENSAGEM_PRECO]}
        produto.refresh_from_db()
        assert produto.preco == D("5.00")
        assert not EntradaAuditoria.objects.filter(
            acao__in=("produto.editar", "produto.alterar_preco")
        ).exists()
        assert avisos == []
        editar_produto(_admin(), produto, nome="Outro")
    finally:
        preco_alterado.disconnect(dispatch_uid="teste.valor_minimo")
    produto.refresh_from_db()
    assert (produto.nome, produto.preco) == ("Outro", D("5.00"))
    (editou,) = EntradaAuditoria.objects.filter(acao="produto.editar")
    assert editou.alteracoes["campos"] == ["nome"]


def test_alterar_incremento_recusa_o_que_ficaria_abaixo_de_um_centavo(webauthn: Any) -> None:
    # A-24
    produto = ProdutoFactory.create(incremento=D("1.000"), preco=D("0.01"))
    RodadaFactory.create(fornecedor=produto.fornecedor, etapa=Etapa.INTERESSE)
    with pytest.raises(IncrementoIncompativel) as erro:
        alterar_incremento(_admin(), produto, "0.25")
    assert erro.value.codigo == "centavo"
    assert str(erro.value) == MENSAGEM_INCREMENTO
    produto.refresh_from_db()
    assert produto.incremento == D("1.000")
    assert not EntradaAuditoria.objects.filter(acao="produto.alterar_incremento").exists()
    alterar_incremento(_admin(), produto, "0.5")  # 0,01 vezes 0,5 = 0,005
    produto.refresh_from_db()
    assert produto.incremento == D("0.500")
    assert EntradaAuditoria.objects.filter(acao="produto.alterar_incremento").count() == 1


def test_o_banco_recusa_a_combinacao_na_criacao_e_no_update() -> None:  # A-25
    fornecedor = FornecedorFactory.create()
    with pytest.raises(IntegrityError, match=RESTRICAO):
        with transaction.atomic():
            Produto.objects.create(
                fornecedor=fornecedor,
                nome="Direto",
                unidade="kg",
                incremento=D("0.001"),
                preco=D("0.01"),
            )
    assert not Produto.objects.exists()
    valido = ProdutoFactory.create(incremento=D("0.001"), preco=D("10.00"))
    with pytest.raises(IntegrityError, match=RESTRICAO):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE catalogo_produto SET preco = 0.01 WHERE id = %s", [valido.pk])
    valido.refresh_from_db()
    assert valido.preco == D("10.00")


def test_as_telas_mostram_a_mensagem_no_campo_e_nada_e_gravado(admin_client: Client) -> None:
    # A-27
    fornecedor = FornecedorFactory.create()
    resposta = admin_client.post(
        f"/administracao/fornecedores/{fornecedor.pk}/produtos/novo/",
        {
            "nome": "Banana",
            "descricao": "",
            "unidade": "kg",
            "incremento": "0,001",
            "preco": "0,01",
            "multiplo": "",
            "disponivel": "on",
        },
    )
    assert resposta.status_code == 200
    assert MENSAGEM_PRECO in resposta.content.decode()
    assert not Produto.objects.exists()

    produto = ProdutoFactory.create(incremento=D("1.000"), preco=D("0.01"))
    RodadaFactory.create(fornecedor=produto.fornecedor, etapa=Etapa.INTERESSE)
    resposta = admin_client.post(
        f"/administracao/produtos/{produto.pk}/incremento/", {"incremento": "0,25"}
    )
    assert resposta.status_code == 200
    assert MENSAGEM_INCREMENTO in resposta.content.decode()
    produto.refresh_from_db()
    assert produto.incremento == D("1.000")
