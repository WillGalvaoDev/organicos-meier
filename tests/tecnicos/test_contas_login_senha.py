"""E02-02: login por e-mail e senha (acceptance A-1 a A-8, A-12, A-16, A-17, A-20)."""

from typing import Any

import pytest
from allauth.usersessions.models import UserSession
from django.test import Client, RequestFactory

from apps.contas.adaptadores import AdaptadorConta
from apps.contas.models import Conta, EmailBanido, Situacao
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

SENHA = "senha-forte-9271!"
GENERICA = "Não foi possível entrar com esses dados."


def _conta(**campos: Any) -> Conta:
    conta = ContaFactory.create(**campos)
    conta.set_password(SENHA)
    conta.save()
    return conta


def _entrar(client: Client, email: str, senha: str = SENHA) -> Any:
    return client.post("/entrar/", {"login": email, "password": senha})


def _autenticado(client: Client) -> bool:
    return "_auth_user_id" in client.session


def _banir(email: str) -> None:
    quem = ContaFactory.create(email_normalizado="quem.baniu@x.com")
    EmailBanido.objects.create(email_normalizado=email, banido_por=quem)


def test_login_com_email_exato_entra_e_mostra_o_nome(client: Client) -> None:  # A-1
    _conta(email_normalizado="ana@x.com", nome="Ana Souza")
    resposta = _entrar(client, "ana@x.com")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/inicio/"
    assert _autenticado(client)
    assert "Ana Souza" in client.get("/inicio/").content.decode()


@pytest.mark.parametrize("digitado", ["  ANA@x.com ", "Ana@X.COM"])
def test_login_normaliza_o_email_digitado(client: Client, digitado: str) -> None:  # A-2
    _conta(email_normalizado="ana@x.com")
    _entrar(client, digitado)
    assert _autenticado(client)


def test_login_com_senha_errada_ou_email_inexistente_tem_a_mesma_mensagem(
    client: Client,
) -> None:  # A-3
    _conta(email_normalizado="ana@x.com")
    errada = _entrar(client, "ana@x.com", "senha-errada-123!")
    inexistente = _entrar(client, "ninguem@x.com")
    assert not _autenticado(client)
    for resposta in (errada, inexistente):
        assert resposta.status_code == 200
        assert GENERICA in resposta.content.decode()


@pytest.mark.tecnico
@pytest.mark.parametrize("digitado", ["ana@x.com", "ANA@X.COM", "  ana@x.com  "])
def test_login_de_email_banido_e_recusado_com_a_mensagem_generica(
    client: Client, digitado: str
) -> None:  # A-4, T-24 (senha)
    _conta(email_normalizado="ana@x.com")
    _banir("ana@x.com")
    resposta = _entrar(client, digitado)
    assert not _autenticado(client)
    assert resposta.status_code == 200
    assert GENERICA in resposta.content.decode()


def test_login_de_conta_removida_e_recusado_sem_pagina_de_conta_inativa(
    client: Client,
) -> None:  # A-5
    _conta(email_normalizado="ana@x.com", situacao=Situacao.REMOVIDA)
    resposta = _entrar(client, "ana@x.com")
    assert not _autenticado(client)
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert GENERICA in html
    assert "inativ" not in html.lower()


def test_login_de_conta_suspensa_entra(client: Client) -> None:  # A-6
    _conta(email_normalizado="ana@x.com", suspensa=True)
    _entrar(client, "ana@x.com")
    assert _autenticado(client)


@pytest.mark.tecnico
def test_login_de_alias_nao_e_afetado_pelo_banimento_do_endereco_base(
    client: Client,
) -> None:  # A-7, T-24 (senha)
    _banir("ana@x.com")
    _conta(email_normalizado="ana+1@x.com")
    _entrar(client, "ana+1@x.com")
    assert _autenticado(client)


def test_login_por_senha_do_administrador_sem_passkey_fica_restrito(client: Client) -> None:
    # A-8 da E02-02, substituído pelo A-14 da E02-03: a recusa temporária acabou. A sessão
    # existe, mas só alcança o cadastro da primeira passkey.
    _conta(administrador=True, email_normalizado="admin@x.com")
    resposta = _entrar(client, "admin@x.com")
    assert resposta.status_code == 302
    assert _autenticado(client)
    restrita = client.get("/administracao/")
    assert restrita.status_code == 302
    assert restrita["Location"].startswith("/seguranca/webauthn/add/")


def test_cadastro_aberto_inexistente(client: Client) -> None:  # A-12
    from django.urls import NoReverseMatch, reverse

    try:
        rota = reverse("account_signup")
    except NoReverseMatch:
        rota = None
    dados = {"email": "novo@x.com", "password1": SENHA, "password2": SENHA}
    for caminho in [rota, "/cadastro/", "/accounts/signup/", "/signup/"]:
        if caminho is None:
            continue
        assert client.get(caminho).status_code in (302, 403, 404)
        assert client.post(caminho, dados).status_code in (302, 403, 404)
    assert not Conta.objects.filter(email_normalizado="novo@x.com").exists()
    assert AdaptadorConta().is_open_for_signup(RequestFactory().get("/")) is False


def test_sair_so_por_post(client: Client) -> None:  # A-16
    _conta(email_normalizado="ana@x.com")
    _entrar(client, "ana@x.com")
    client.get("/sair/")
    assert _autenticado(client)
    client.post("/sair/")
    assert not _autenticado(client)


def test_sair_exige_csrf() -> None:
    conta = _conta(email_normalizado="ana@x.com")
    cliente = Client(enforce_csrf_checks=True)
    cliente.force_login(conta)
    assert cliente.post("/sair/").status_code == 403
    assert "_auth_user_id" in cliente.session


def test_inicio_exige_login(client: Client) -> None:  # A-17
    resposta = client.get("/inicio/")
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_inicio_mostra_nome_e_papel(client: Client) -> None:
    _conta(email_normalizado="ana@x.com", nome="Ana Souza")
    _entrar(client, "ana@x.com")
    html = client.get("/inicio/").content.decode()
    assert "Ana Souza" in html
    assert "comprador" in html.lower()


def test_login_registra_sessao_no_usersessions(client: Client) -> None:  # A-20
    conta = _conta(email_normalizado="ana@x.com")
    _entrar(client, "ana@x.com")
    assert UserSession.objects.filter(user=conta).exists()


def test_login_sem_email_verificado_e_recusado_sem_erro_de_servidor(client: Client) -> None:
    conta = _conta(email_normalizado="ana@x.com")
    conta.emailaddress_set.all().delete()  # type: ignore[attr-defined]
    resposta = _entrar(client, "ana@x.com")
    assert resposta.status_code == 200
    assert not _autenticado(client)
    assert GENERICA in resposta.content.decode()


def test_login_sessao_e_do_banco(client: Client, settings: Any) -> None:
    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
