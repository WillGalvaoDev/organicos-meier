"""E02-03: gestão de passkeys (acceptance A-11, A-12 e A-15)."""

from typing import Any

import pytest
from allauth.mfa.models import Authenticator
from django.test import Client

from tests.apoio.admin_fluxos import (
    ROTA_CADASTRO,
    administrador_com_passkey,
    cadastrar_passkey,
    entrar_com_passkey_direta,
    reautenticar_por_passkey,
)
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db


def _remover(client: Client, autenticador: Authenticator) -> Any:
    return client.post(f"/seguranca/webauthn/keys/{autenticador.pk}/remove/")


def test_a_ultima_passkey_nao_pode_ser_removida(client: Client, webauthn: Any) -> None:  # A-11
    conta, credencial_id = administrador_com_passkey(client)
    entrar_com_passkey_direta(client, credencial_id, conta)
    unica = Authenticator.objects.get(user=conta)
    resposta = _remover(client, unica)
    assert resposta.status_code in (200, 302, 403)
    assert Authenticator.objects.filter(pk=unica.pk).exists()


def test_com_duas_passkeys_uma_pode_ser_removida_depois_de_nova_autenticacao(
    client: Client, webauthn: Any
) -> None:  # A-12
    conta, primeira = administrador_com_passkey(client)
    entrar_com_passkey_direta(client, primeira, conta)
    cadastrar_passkey(client, nome="Segunda")
    assert Authenticator.objects.filter(user=conta).count() == 2

    reautenticar_por_passkey(client, primeira, conta)
    segunda = Authenticator.objects.filter(user=conta).order_by("-pk").first()
    assert segunda is not None
    _remover(client, segunda)
    assert Authenticator.objects.filter(user=conta).count() == 1


def test_remover_exige_passkey_recente_e_nao_so_senha(
    client: Client, relogio: Any, webauthn: Any
) -> None:
    from datetime import UTC, datetime, timedelta

    conta, primeira = administrador_com_passkey(client)
    relogio.congelar(datetime(2026, 10, 14, 15, 0, tzinfo=UTC))
    entrar_com_passkey_direta(client, primeira, conta)
    cadastrar_passkey(client, nome="Segunda")
    relogio.avancar(timedelta(seconds=400))
    segunda = Authenticator.objects.filter(user=conta).order_by("-pk").first()
    assert segunda is not None
    resposta = _remover(client, segunda)
    assert resposta.status_code == 302
    assert "/seguranca/webauthn/reauthenticate/" in resposta["Location"]
    assert Authenticator.objects.filter(user=conta).count() == 2


def test_cadastrar_outra_passkey_exige_nova_autenticacao_por_passkey(
    client: Client, relogio: Any, webauthn: Any
) -> None:
    from datetime import UTC, datetime, timedelta

    conta, primeira = administrador_com_passkey(client)
    relogio.congelar(datetime(2026, 10, 14, 15, 0, tzinfo=UTC))
    entrar_com_passkey_direta(client, primeira, conta)
    relogio.avancar(timedelta(seconds=400))
    resposta = client.get(ROTA_CADASTRO)
    assert resposta.status_code == 302
    assert "/seguranca/webauthn/reauthenticate/" in resposta["Location"]


@pytest.mark.parametrize("fornecedor", [False, True], ids=["comprador", "fornecedor"])
def test_rotas_de_mfa_sao_so_do_administrador(client: Client, fornecedor: bool) -> None:  # A-15
    client.force_login(ContaFactory.create(fornecedor=fornecedor))
    for caminho in [ROTA_CADASTRO, "/seguranca/", "/seguranca/webauthn/"]:
        assert client.get(caminho).status_code in (403, 404), caminho
    assert client.post(ROTA_CADASTRO, {"credential": "{}"}).status_code in (403, 404)
    assert not Authenticator.objects.exists()
