"""E02-03: nova autenticação por passkey (acceptance A-9 e A-10).

Fronteira observada no allauth 65.19.7: a nova autenticação vale quando
`agora - última_autenticação < ACCOUNT_REAUTHENTICATION_TIMEOUT` (300 s), ou seja, o limite é
EXCLUSIVO: exatamente 300 s depois já exige outra. A spec previa limite inclusivo; o spec manda
registrar o comportamento real do allauth, e a função própria segue o mesmo critério.
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.test import Client

from tests.apoio.admin_fluxos import (
    administrador_com_passkey,
    entrar_com_passkey_direta,
    reautenticar_por_passkey,
)

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.apoio.urls")]

T = datetime(2026, 10, 14, 15, 0, 0, tzinfo=UTC)
ROTA = "/teste/acao-sensivel/"


def _admin_logado(client: Client, relogio: Any, webauthn: Any) -> tuple[Any, bytes]:
    conta, credencial_id = administrador_com_passkey(client)
    relogio.congelar(T)
    entrar_com_passkey_direta(client, credencial_id, conta)
    return conta, credencial_id


def test_acao_sensivel_logo_depois_do_login_nao_pede_nova_autenticacao(
    client: Client, relogio: Any, webauthn: Any
) -> None:  # A-9
    _admin_logado(client, relogio, webauthn)
    resposta = client.get(ROTA)
    assert resposta.status_code == 200
    assert "ação sensível executada" in resposta.content.decode()


def test_acao_sensivel_dentro_do_prazo_ainda_vale(
    client: Client, relogio: Any, webauthn: Any
) -> None:
    _admin_logado(client, relogio, webauthn)
    relogio.avancar(timedelta(seconds=299, milliseconds=900))
    assert client.get(ROTA).status_code == 200


@pytest.mark.parametrize("segundos", [300, 301])
def test_acao_sensivel_no_limite_e_depois_exige_nova_autenticacao_por_passkey(
    client: Client, relogio: Any, webauthn: Any, segundos: int
) -> None:  # A-10
    _admin_logado(client, relogio, webauthn)
    relogio.avancar(timedelta(seconds=segundos))
    resposta = client.get(ROTA)
    assert resposta.status_code == 302
    assert "/seguranca/webauthn/reauthenticate/" in resposta["Location"]
    assert f"next={ROTA}" in resposta["Location"].replace("%2F", "/")


def test_nova_autenticacao_por_passkey_libera_e_volta_para_a_acao(
    client: Client, relogio: Any, webauthn: Any
) -> None:  # A-10
    conta, credencial_id = _admin_logado(client, relogio, webauthn)
    relogio.avancar(timedelta(seconds=301))
    assert client.get(ROTA).status_code == 302
    resposta = reautenticar_por_passkey(client, credencial_id, conta, destino=ROTA)
    assert resposta.status_code == 302
    assert resposta["Location"] == ROTA
    assert client.get(ROTA).status_code == 200


def test_nova_autenticacao_por_senha_nao_libera(
    client: Client, relogio: Any, webauthn: Any
) -> None:  # A-10
    _admin_logado(client, relogio, webauthn)
    relogio.avancar(timedelta(seconds=301))
    sessao = client.session
    sessao["account_authentication_methods"] = [
        *sessao["account_authentication_methods"],
        {"method": "password", "at": time.time(), "reauthenticated": True},
    ]
    sessao.save()
    resposta = client.get(ROTA)
    assert resposta.status_code == 302
    assert "/seguranca/webauthn/reauthenticate/" in resposta["Location"]


def test_acao_sensivel_exige_ser_administrador(client: Client) -> None:
    from tests.fabricas import ContaFactory

    client.force_login(ContaFactory.create())
    assert client.get(ROTA).status_code == 403


def test_acao_sensivel_anonimo_vai_para_o_login(client: Client) -> None:
    resposta = client.get(ROTA)
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")
