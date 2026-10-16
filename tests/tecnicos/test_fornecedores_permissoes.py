"""E03-01: só o administrador acessa as rotas de fornecedores (acceptance A-12)."""

import pytest
from django.test import Client

from apps.fornecedores.models import Fornecedor
from tests.fabricas import ContaFactory, FornecedorFactory

pytestmark = pytest.mark.django_db


def _rotas(pk: int) -> list[str]:
    return [
        "/administracao/fornecedores/",
        "/administracao/fornecedores/novo/",
        f"/administracao/fornecedores/{pk}/",
        f"/administracao/fornecedores/{pk}/editar/",
    ]


@pytest.mark.parametrize("fornecedor", [False, True], ids=["comprador", "fornecedor"])
def test_autenticados_que_nao_sao_administrador_recebem_403(
    client: Client, fornecedor: bool
) -> None:
    alvo = FornecedorFactory.create(nome="Intacto")
    client.force_login(ContaFactory.create(fornecedor=fornecedor))
    antes = Fornecedor.objects.count()
    dados = {
        "nome": "Invasor",
        "email_pedido": "i@x.com",
        "minimo": "10",
        "prazo_entrega_dias": "3",
    }
    for rota in _rotas(alvo.pk):
        assert client.get(rota).status_code == 403, rota
        assert client.post(rota, dados).status_code == 403, rota
    assert Fornecedor.objects.count() == antes
    alvo.refresh_from_db()
    assert alvo.nome == "Intacto"


def test_visitante_anonimo_vai_para_o_login() -> None:
    alvo = FornecedorFactory.create(nome="Intacto")
    anonimo = Client()
    for rota in _rotas(alvo.pk):
        for resposta in (anonimo.get(rota), anonimo.post(rota, {"nome": "X"})):
            assert resposta.status_code == 302, rota
            assert resposta["Location"].startswith("/entrar/"), rota
    assert Fornecedor.objects.count() == 1
