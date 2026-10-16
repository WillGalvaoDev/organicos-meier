"""Passos reutilizáveis dos testes do administrador com passkey (E02-03)."""

import json
from typing import Any

from django.test import Client

from apps.contas.models import Conta
from tests.apoio.webauthn_falso import autenticacao_json, novo_id_de_credencial, registro_json
from tests.fabricas import ContaFactory

SENHA = "senha-forte-9271!"
EMAIL = "admin@x.com"
ROTA_CADASTRO = "/seguranca/webauthn/add/"
ROTA_ETAPA = "/seguranca/authenticate/"
ROTA_REAUTENTICACAO = "/seguranca/webauthn/reauthenticate/"
ROTA_LOGIN_DIRETO = "/seguranca/webauthn/login/"


def criar_administrador() -> Conta:
    conta = ContaFactory.create(administrador=True, email_normalizado=EMAIL, nome="Adm")
    conta.set_password(SENHA)
    conta.save()
    return conta


def autenticado(client: Client) -> bool:
    return "_auth_user_id" in client.session


def entrar_por_senha(client: Client, senha: str = SENHA) -> Any:
    return client.post("/entrar/", {"login": EMAIL, "password": senha})


def cadastrar_passkey(client: Client, nome: str = "Chave") -> bytes:
    """Cadastra uma passkey (dublê) pela tela real do allauth. Devolve o id da credencial."""
    credencial_id = novo_id_de_credencial()
    resposta = client.post(
        ROTA_CADASTRO, {"name": nome, "credential": json.dumps(registro_json(credencial_id))}
    )
    assert resposta.status_code == 302, resposta.content[:500]
    return credencial_id


def concluir_etapa_de_passkey(client: Client, credencial_id: bytes, conta: Conta) -> Any:
    return client.post(
        ROTA_ETAPA,
        {"credential": json.dumps(autenticacao_json(credencial_id, conta.pk))},
    )


def reautenticar_por_passkey(
    client: Client, credencial_id: bytes, conta: Conta, destino: str = "/administracao/"
) -> Any:
    return client.post(
        f"{ROTA_REAUTENTICACAO}?next={destino}",
        {"credential": json.dumps(autenticacao_json(credencial_id, conta.pk))},
    )


def entrar_com_passkey_direta(client: Client, credencial_id: bytes, conta: Conta) -> Any:
    return client.post(
        ROTA_LOGIN_DIRETO,
        {"credential": json.dumps(autenticacao_json(credencial_id, conta.pk))},
    )


def administrador_com_passkey(client: Client) -> tuple[Conta, bytes]:
    """Administrador com uma passkey, sem sessão aberta no `client`."""
    conta = criar_administrador()
    entrar_por_senha(client)
    credencial_id = cadastrar_passkey(client)
    client.post("/sair/")
    return conta, credencial_id
