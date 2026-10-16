"""E02-03: comando redefinir_passkeys_administrador (acceptance A-13)."""

import io
from typing import Any

import pytest
from allauth.mfa.models import Authenticator
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.admin_fluxos import (
    ROTA_CADASTRO,
    administrador_com_passkey,
    autenticado,
    entrar_com_passkey_direta,
    entrar_por_senha,
)

pytestmark = pytest.mark.django_db


def test_redefinir_remove_passkeys_encerra_sessoes_e_audita(webauthn: Any) -> None:  # A-13
    primeiro = Client()
    conta, credencial_id = administrador_com_passkey(primeiro)
    entrar_com_passkey_direta(primeiro, credencial_id, conta)
    segundo = Client()
    entrar_com_passkey_direta(segundo, credencial_id, conta)
    assert autenticado(primeiro)
    assert autenticado(segundo)

    call_command("redefinir_passkeys_administrador", stdout=io.StringIO())

    assert Authenticator.objects.filter(user=conta).count() == 0
    assert not autenticado(primeiro)
    assert not autenticado(segundo)
    entrada = EntradaAuditoria.objects.get(acao="conta.redefinir_passkeys")
    assert entrada.autor_tipo == "sistema"
    assert entrada.alteracoes == {"conta": conta.pk, "removidas": 1}

    novo = Client()
    entrar_por_senha(novo)
    assert autenticado(novo)  # volta à regra da primeira passkey (A-1)
    resposta = novo.get("/administracao/")
    assert resposta["Location"].startswith(ROTA_CADASTRO)


def test_redefinir_sem_administrador_e_erro() -> None:
    with pytest.raises(CommandError):
        call_command("redefinir_passkeys_administrador", stdout=io.StringIO())


def test_redefinir_nao_mexe_em_sessoes_de_outras_contas(webauthn: Any) -> None:
    from tests.fabricas import ContaFactory

    conta, _ = administrador_com_passkey(Client())
    comprador = ContaFactory.create()
    outro = Client()
    outro.force_login(comprador)
    call_command("redefinir_passkeys_administrador", stdout=io.StringIO())
    assert autenticado(outro)
    assert conta.pk != comprador.pk
