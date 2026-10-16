"""E03-03: só o administrador acessa as rotas do catálogo (acceptance A-22)."""

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from apps.catalogo.models import Produto
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, ProdutoFactory, RodadaFactory

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
        f"/administracao/produtos/{produto.pk}/incremento/",
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
    assert produto.incremento == Decimal("1.000")
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


def _rotas_do_catalogo() -> list[str]:
    rodada = RodadaFactory.create()
    return ["/catalogo/", f"/catalogo/{rodada.fornecedor_id}/"]


def test_comprador_suspenso_consulta_o_catalogo(client: Client) -> None:  # A-7
    rotas = _rotas_do_catalogo()
    client.force_login(ContaFactory.create(suspensa=True))
    for rota in rotas:
        assert client.get(rota).status_code == 200, rota


def test_fornecedor_e_administrador_nao_consultam_o_catalogo(
    client: Client, webauthn: Any
) -> None:  # A-8
    outro = Client()
    administrador_logado(outro)
    rotas = _rotas_do_catalogo()
    client.force_login(ContaFactory.create(fornecedor=True))
    for rota in rotas:
        assert client.get(rota).status_code == 403, rota
    for rota in rotas:
        assert outro.get(rota).status_code == 403, rota


def test_visitante_anonimo_vai_para_o_login_no_catalogo() -> None:  # A-8
    rotas = _rotas_do_catalogo()
    anonimo = Client()
    for rota in rotas:
        resposta = anonimo.get(rota)
        assert resposta.status_code == 302, rota
        assert resposta["Location"].startswith("/entrar/"), rota
