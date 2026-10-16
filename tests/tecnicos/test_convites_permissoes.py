"""E02-04: permissões da emissão de convites (acceptance A-11 e A-12)."""

from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client

from apps.contas.convites import emitir_convite
from apps.contas.models import Convite
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

ROTA = "/administracao/convites/"


@pytest.mark.parametrize("fornecedor", [False, True], ids=["comprador", "fornecedor"])
def test_outros_papeis_recebem_403_e_nada_e_gravado(
    client: Client, fornecedor: bool
) -> None:  # A-11
    client.force_login(ContaFactory.create(fornecedor=fornecedor))
    assert client.get(ROTA).status_code == 403
    dados = {"email": "bia@x.com", "papel": "comprador", "fornecedor": ""}
    assert client.post(ROTA, dados).status_code == 403
    assert Convite.objects.count() == 0


def test_visitante_anonimo_vai_para_o_login(client: Client) -> None:  # A-11
    for resposta in (client.get(ROTA), client.post(ROTA, {"email": "bia@x.com"})):
        assert resposta.status_code == 302
        assert resposta["Location"].startswith("/entrar/")
    assert Convite.objects.count() == 0


def test_administrador_sem_passkey_na_sessao_nao_emite(client: Client, webauthn: Any) -> None:
    client.force_login(ContaFactory.create(administrador=True))
    resposta = client.post(ROTA, {"email": "bia@x.com", "papel": "comprador", "fornecedor": ""})
    assert resposta.status_code == 302
    assert Convite.objects.count() == 0


@pytest.mark.parametrize("fornecedor", [False, True], ids=["comprador", "fornecedor"])
def test_servico_recusa_autor_que_nao_e_administrador(fornecedor: bool) -> None:  # A-12
    autor = ContaFactory.create(fornecedor=fornecedor)
    with pytest.raises(PermissionDenied):
        emitir_convite(autor, "bia@x.com", "comprador")
    assert Convite.objects.count() == 0
