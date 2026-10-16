"""E02-03: área administrativa restrita (acceptance A-6 a A-8)."""

from typing import Any

import pytest
from django.test import Client

from tests.apoio.admin_fluxos import criar_administrador
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("fornecedor", [False, True], ids=["comprador", "fornecedor"])
def test_outros_papeis_recebem_403(client: Client, fornecedor: bool) -> None:  # A-6
    conta = ContaFactory.create(fornecedor=fornecedor)
    client.force_login(conta)
    assert client.get("/administracao/").status_code == 403
    assert client.post("/administracao/").status_code == 403


def test_visitante_anonimo_vai_para_o_login(client: Client) -> None:  # A-7
    resposta = client.get("/administracao/")
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_administrador_sem_prova_de_passkey_na_sessao_nao_acessa(
    client: Client, webauthn: Any
) -> None:  # A-8
    from tests.apoio.admin_fluxos import cadastrar_passkey, entrar_por_senha

    admin = criar_administrador()
    entrar_por_senha(client)
    cadastrar_passkey(client)
    client.logout()
    client.force_login(admin)  # sessão sem registro de autenticação por passkey
    resposta = client.get("/administracao/")
    assert resposta.status_code == 302
    assert "/seguranca/webauthn/reauthenticate/" in resposta["Location"]


def test_administrador_logado_por_force_login_sem_passkey_cadastrada_nao_acessa(
    client: Client,
) -> None:
    client.force_login(criar_administrador())
    resposta = client.get("/administracao/")
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/seguranca/webauthn/add/")
