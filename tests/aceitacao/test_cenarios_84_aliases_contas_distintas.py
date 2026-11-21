"""Cenário 84 (§16): `usuario@gmail.com` e `usuario+teste@gmail.com` podem pertencer a contas
distintas (E16-07 regra 2-G): duas contas criadas pelo cadastro por convite, uma por e-mail."""

import pytest
from django.test import Client

from apps.contas.models import Conta
from tests.tecnicos.test_convites_cadastro import _cadastrar, _convite

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

BASE = "usuario@gmail.com"
ALIAS = "usuario+teste@gmail.com"


def test_cenario_84_aliases_com_mais_sao_contas_distintas(client: Client) -> None:
    _, token_da_base = _convite(email_normalizado=BASE)
    _, token_do_alias = _convite(email_normalizado=ALIAS)
    outro = Client()
    assert _cadastrar(client, token_da_base, nome="Base").status_code == 302
    assert _cadastrar(outro, token_do_alias, nome="Alias").status_code == 302
    contas = list(Conta.objects.filter(email_normalizado__in=[BASE, ALIAS]).order_by("pk"))
    assert [c.email_normalizado for c in contas] == [BASE, ALIAS]
    assert contas[0].pk != contas[1].pk
    assert [c.nome for c in contas] == ["Base", "Alias"]
    assert client.session["_auth_user_id"] == str(contas[0].pk)
    assert outro.session["_auth_user_id"] == str(contas[1].pk)
