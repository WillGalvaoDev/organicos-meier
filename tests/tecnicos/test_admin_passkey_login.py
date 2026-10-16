"""E02-03: login do administrador com passkey (acceptance A-1 a A-5 e A-14)."""

from typing import Any

import pytest
from django.test import Client

from tests.apoio.admin_fluxos import (
    ROTA_CADASTRO,
    administrador_com_passkey,
    autenticado,
    cadastrar_passkey,
    concluir_etapa_de_passkey,
    criar_administrador,
    entrar_com_passkey_direta,
    entrar_por_senha,
    reautenticar_por_passkey,
)

pytestmark = pytest.mark.django_db


def test_sem_passkey_a_sessao_fica_restrita_ao_cadastro_da_primeira(
    client: Client, webauthn: Any
) -> None:  # A-1 e A-14
    criar_administrador()
    resposta = entrar_por_senha(client)
    assert resposta.status_code == 302
    assert autenticado(client)  # A-14: a sessão existe, mas restrita
    for caminho in ["/administracao/", "/inicio/", "/qualquer/coisa/"]:
        restrita = client.get(caminho)
        assert restrita.status_code == 302, caminho
        assert restrita["Location"].startswith(ROTA_CADASTRO), caminho
    assert client.get(ROTA_CADASTRO).status_code == 200
    client.post("/sair/")
    assert not autenticado(client)


def test_primeira_passkey_nao_da_acesso_a_area_administrativa_na_mesma_sessao(
    client: Client, webauthn: Any
) -> None:  # A-2
    conta = criar_administrador()
    entrar_por_senha(client)
    credencial_id = cadastrar_passkey(client)

    antes = client.get("/administracao/")
    assert antes.status_code == 302
    assert "/seguranca/webauthn/reauthenticate/" in antes["Location"]

    reautenticar_por_passkey(client, credencial_id, conta)
    assert client.get("/administracao/").status_code == 200


def test_com_passkey_a_senha_exige_a_etapa_de_passkey(client: Client, webauthn: Any) -> None:  # A-3
    conta, credencial_id = administrador_com_passkey(client)
    resposta = entrar_por_senha(client)
    assert resposta.status_code == 302
    assert resposta["Location"] == "/seguranca/authenticate/"
    assert not autenticado(client)
    assert client.get("/administracao/").status_code != 200

    concluir_etapa_de_passkey(client, credencial_id, conta)
    assert autenticado(client)
    assert client.get("/administracao/").status_code == 200


def test_etapa_de_passkey_recusada_nao_cria_sessao(client: Client, webauthn: Any) -> None:  # A-4
    conta, credencial_id = administrador_com_passkey(client)
    entrar_por_senha(client)
    webauthn.recusar = True
    concluir_etapa_de_passkey(client, credencial_id, conta)
    assert not autenticado(client)
    resposta = client.get("/administracao/")
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_etapa_de_passkey_abandonada_nao_cria_sessao(client: Client, webauthn: Any) -> None:
    administrador_com_passkey(client)
    entrar_por_senha(client)
    assert not autenticado(client)
    resposta = client.get("/administracao/")
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_senha_errada_nao_chega_na_etapa_de_passkey(client: Client, webauthn: Any) -> None:
    administrador_com_passkey(client)
    resposta = entrar_por_senha(client, "senha-errada-123!")
    assert resposta.status_code == 200
    assert not autenticado(client)


def test_login_por_passkey_direta_libera_a_area_administrativa(
    client: Client, webauthn: Any
) -> None:  # A-5
    conta, credencial_id = administrador_com_passkey(client)
    resposta = entrar_com_passkey_direta(client, credencial_id, conta)
    assert resposta.status_code == 302
    assert autenticado(client)
    assert client.get("/administracao/").status_code == 200


def test_login_por_passkey_direta_respeita_o_banimento_do_email(
    client: Client, webauthn: Any
) -> None:
    from apps.contas.models import EmailBanido

    conta, credencial_id = administrador_com_passkey(client)
    EmailBanido.objects.create(email_normalizado="admin@x.com", banido_por=conta)
    entrar_com_passkey_direta(client, credencial_id, conta)
    assert not autenticado(client)
