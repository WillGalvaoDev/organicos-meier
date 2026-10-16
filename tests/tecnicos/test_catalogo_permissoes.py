"""E03-03: só o administrador acessa as rotas do catálogo (acceptance A-22)."""

from decimal import Decimal

import pytest
from django.test import Client

from apps.catalogo.models import Produto
from apps.nucleo.auditoria import EntradaAuditoria
from tests.fabricas import ContaFactory, ProdutoFactory

pytestmark = pytest.mark.django_db

DADOS = {
    "nome": "Invasor",
    "unidade": "kg",
    "incremento": "1",
    "preco": "1,00",
    "multiplo": "5",
    "descricao": "",
}


def _rotas(produto: Produto) -> list[str]:
    return [
        f"/administracao/fornecedores/{produto.fornecedor_id}/produtos/novo/",
        f"/administracao/produtos/{produto.pk}/",
        f"/administracao/produtos/{produto.pk}/multiplo/",
    ]


@pytest.mark.parametrize("fornecedor", [False, True], ids=["comprador", "fornecedor"])
def test_autenticados_que_nao_sao_administrador_recebem_403(
    client: Client, fornecedor: bool
) -> None:
    produto = ProdutoFactory.create(nome="Intacto", preco=Decimal("10.00"))
    client.force_login(ContaFactory.create(fornecedor=fornecedor))
    for rota in _rotas(produto):
        assert client.get(rota).status_code == 403, rota
        assert client.post(rota, DADOS).status_code == 403, rota
    produto.refresh_from_db()
    assert (produto.nome, produto.preco, produto.multiplo) == ("Intacto", Decimal("10.00"), None)
    assert Produto.objects.count() == 1
    assert EntradaAuditoria.objects.count() == 0


def test_visitante_anonimo_vai_para_o_login() -> None:
    produto = ProdutoFactory.create()
    anonimo = Client()
    for rota in _rotas(produto):
        for resposta in (anonimo.get(rota), anonimo.post(rota, DADOS)):
            assert resposta.status_code == 302, rota
            assert resposta["Location"].startswith("/entrar/"), rota
    assert Produto.objects.count() == 1
