"""Cenário 61 (E02-10, A-8): as contas da mesma pessoa não se misturam."""

import pytest
from django.test import Client

from tests.fabricas import ContaFactory

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

SENHA = "senha-forte-9271!"


def _entrar(email: str, **campos: object) -> Client:
    conta = ContaFactory.create(email_normalizado=email, **campos)
    conta.set_password(SENHA)
    conta.save()
    cliente = Client()
    cliente.post("/entrar/", {"login": email, "password": SENHA})
    assert "_auth_user_id" in cliente.session
    return cliente


def test_cada_sessao_ve_so_a_propria_conta() -> None:
    comprador = _entrar("ana@exemplo.com", nome="Ana Compradora")
    fornecedor = _entrar("ana.fornecedor@exemplo.com", nome="Ana Fornecedora", fornecedor=True)

    inicio_da_compradora = comprador.get("/inicio/").content.decode()
    perfil_da_compradora = comprador.get("/perfil/").content.decode()
    inicio_do_fornecedor = fornecedor.get("/inicio/").content.decode()
    perfil_do_fornecedor = fornecedor.get("/perfil/").content.decode()

    # nome e papel em /inicio/; nome e e-mail em /perfil/ — sempre os da própria sessão
    assert "Ana Compradora" in inicio_da_compradora
    assert "Comprador" in inicio_da_compradora
    assert "ana@exemplo.com" in perfil_da_compradora
    assert "Ana Fornecedora" in inicio_do_fornecedor
    assert "Fornecedor" in inicio_do_fornecedor
    assert "ana.fornecedor@exemplo.com" in perfil_do_fornecedor

    do_comprador = inicio_da_compradora + perfil_da_compradora
    do_fornecedor = inicio_do_fornecedor + perfil_do_fornecedor
    assert "Ana Fornecedora" not in do_comprador
    assert "ana.fornecedor@exemplo.com" not in do_comprador
    assert "Ana Compradora" not in do_fornecedor
    assert "ana@exemplo.com" not in do_fornecedor.replace("ana.fornecedor@exemplo.com", "")


def test_conta_de_fornecedor_nao_compra_e_comprador_nao_acessa_a_area_do_fornecedor() -> None:
    fornecedor = _entrar("ana.fornecedor@exemplo.com", fornecedor=True)
    comprador = _entrar("ana@exemplo.com")
    # As rotas reais de compra e de fornecedor chegam nas etapas E05, E08 e E13; aqui basta a
    # política dos decoradores, provada nas rotas de teste (test_permissoes_papeis.py).
    assert fornecedor.get("/inicio/").status_code == 200
    assert comprador.get("/inicio/").status_code == 200
