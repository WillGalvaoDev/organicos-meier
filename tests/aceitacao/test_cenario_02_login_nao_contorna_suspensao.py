"""Cenário 2 da especificação funcional: o login por Google ou link não contorna a suspensão
(E16-07, lacuna).

A suspensão deixa a conta entrar para acompanhar pedidos, mas não comprar (§2). O que se prova aqui
é que o canal de entrada (Google ou link) não devolve o que a suspensão tirou: a sessão abre e,
depois, a adição de interesse é recusada. Testes de caracterização: o comportamento já existia
(E02-07, E02-06 e E05-05), então passaram na primeira execução.
"""

import json
import re
from typing import Any

import pytest
from django.core import mail
from django.test import Client

from apps.contas.models import Conta, Situacao
from tests.apoio.interesses import cenario
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db(transaction=True)

EMAIL = "ana@x.com"


def _tentar_adicionar_interesse(client: Client) -> int:
    _rodada, produto, _estoque = cenario("20")
    resposta = client.post("/interesses/", {"produto": produto.pk, "quantidade": "3"})
    return int(resposta.status_code)


@pytest.mark.urls("tests.apoio.urls")
def test_google_de_conta_suspensa_entra_mas_nao_adiciona_interesse(client: Client) -> None:
    conta = ContaFactory.create(email_normalizado=EMAIL, suspensa=True)
    dados = {"sub": "google-1", "name": "Ana G", "email": EMAIL, "email_verified": True}
    client.post("/teste/retorno-google/", {"extra_data": json.dumps(dados)})
    assert "_auth_user_id" in client.session  # o canal abriu a sessão
    assert _tentar_adicionar_interesse(client) == 403  # a suspensão continua valendo
    _verificar_sem_reserva(conta)


def test_link_de_conta_suspensa_entra_mas_nao_adiciona_interesse(client: Client) -> None:
    conta = ContaFactory.create(email_normalizado=EMAIL)
    Client().post("/entrar/link/", {"email": EMAIL})
    token = re.findall(r"/entrar/link/([A-Za-z0-9_-]+)/", str(mail.outbox[-1].body))[0]
    Conta.objects.filter(pk=conta.pk).update(situacao=Situacao.SUSPENSA)
    client.post(f"/entrar/link/{token}/")
    assert "_auth_user_id" in client.session  # o canal abriu a sessão
    assert _tentar_adicionar_interesse(client) == 403  # a suspensão continua valendo
    _verificar_sem_reserva(conta)


def _verificar_sem_reserva(conta: Any) -> None:
    from apps.interesses.models import ParcelaDeInteresse

    assert not ParcelaDeInteresse.objects.filter(comprador=conta).exists()
