"""E02-07: login com Google em contas existentes (acceptance A-1 a A-8 e A-16).

O retorno do Google é simulado sem rede: a rota de teste monta o `SocialLogin` como o callback
real (`sociallogin_from_response`) e o entrega a `complete_social_login`, a API de conclusão de
login social do allauth 65.19.7. O adaptador do projeto não é substituído.
"""

import json
from typing import Any

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.test import Client

from apps.contas.models import Conta, EmailBanido, Situacao
from tests.fabricas import ContaFactory

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.apoio.urls")]

RECUSA = "Não foi possível entrar com essa conta Google."


def _retorno(
    client: Client,
    *,
    uid: str = "google-1",
    email: str | None = "ana@x.com",
    verificado: bool | None = True,
    nome: str = "Ana G",
) -> Any:
    dados: dict[str, Any] = {"sub": uid, "name": nome}
    if email is not None:
        dados["email"] = email
    if verificado is not None:
        dados["email_verified"] = verificado
    return client.post("/teste/retorno-google/", {"extra_data": json.dumps(dados)})


def _contagens() -> tuple[int, int, int]:
    return Conta.objects.count(), SocialAccount.objects.count(), EmailAddress.objects.count()


def _autenticado(client: Client) -> bool:
    return "_auth_user_id" in client.session


def _recusado(client: Client, resposta: Any, antes: tuple[int, int, int]) -> None:
    assert resposta.status_code == 302
    assert resposta["Location"] == "/entrar/"
    assert RECUSA in client.get("/entrar/").content.decode()
    assert not _autenticado(client)
    assert _contagens() == antes


def _banir(email: str) -> None:
    EmailBanido.objects.create(
        email_normalizado=email, banido_por=ContaFactory.create(email_normalizado="q@x.com")
    )


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_conta_existente_entra_pelo_email_e_vincula_a_conta_social(client: Client) -> None:
    # A-1, cenário 82, T-35
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    antes = Conta.objects.count()
    resposta = _retorno(client, email="Ana@X.com")
    assert resposta.status_code == 302
    assert client.session["_auth_user_id"] == str(conta.pk)
    social = SocialAccount.objects.get()
    assert social.user == conta
    assert (social.provider, social.uid) == ("google", "google-1")
    assert Conta.objects.count() == antes


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_segundo_login_com_o_mesmo_uid_entra_na_mesma_conta(client: Client) -> None:
    # A-2, cenário 82
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    _retorno(client)
    outro = Client()
    _retorno(outro, email="ANA@x.com")
    assert outro.session["_auth_user_id"] == str(conta.pk)
    assert SocialAccount.objects.count() == 1


def test_email_do_google_diferente_do_da_conta_vinculada_e_recusado(client: Client) -> None:  # A-3
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    _retorno(client)
    outro = Client()
    antes = _contagens()
    resposta = _retorno(outro, email="outra@x.com")
    _recusado(outro, resposta, antes)
    assert SocialAccount.objects.get().user == conta


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_sem_conta_e_sem_convite_nao_cria_nada(client: Client) -> None:  # A-4, cenário 82, T-35
    antes = _contagens()
    resposta = _retorno(client, email="nova@x.com")
    _recusado(client, resposta, antes)


@pytest.mark.parametrize("verificado", [False, None], ids=["nao_verificado", "sem_campo"])
def test_email_nao_verificado_pelo_google_e_recusado(
    client: Client, verificado: bool | None
) -> None:
    # A-5
    ContaFactory.create(email_normalizado="ana@x.com")
    antes = _contagens()
    resposta = _retorno(client, verificado=verificado)
    _recusado(client, resposta, antes)


def test_google_sem_email_e_recusado(client: Client) -> None:  # A-5
    ContaFactory.create(email_normalizado="ana@x.com")
    antes = _contagens()
    resposta = _retorno(client, email=None)
    _recusado(client, resposta, antes)


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize("caso", ["banido", "removido"])
def test_banido_ou_removido_nao_entra_pelo_google(client: Client, caso: str) -> None:
    # A-6, cenários 2 e 58, T-24 (Google)
    if caso == "banido":
        ContaFactory.create(email_normalizado="ana@x.com")
        _banir("ana@x.com")
        email = " ANA@x.com"
    else:
        ContaFactory.create(email_normalizado="rem@x.com", situacao=Situacao.REMOVIDA)
        email = "rem@x.com"
    antes = _contagens()
    resposta = _retorno(client, email=email)
    _recusado(client, resposta, antes)


def test_administrador_nao_entra_pelo_google(client: Client) -> None:  # A-7
    ContaFactory.create(administrador=True, email_normalizado="admin@x.com")
    antes = _contagens()
    resposta = _retorno(client, email="admin@x.com")
    _recusado(client, resposta, antes)


def test_conta_suspensa_entra_pelo_google(client: Client) -> None:  # A-8
    ContaFactory.create(email_normalizado="ana@x.com", suspensa=True)
    _retorno(client)
    assert _autenticado(client)


@pytest.mark.acceptance
def test_alias_de_email_banido_entra_normalmente(client: Client) -> None:  # A-16, cenário 59
    _banir("ana@x.com")
    ContaFactory.create(email_normalizado="ana+1@x.com")
    _retorno(client, email="ana+1@x.com")
    assert _autenticado(client)


def test_conta_social_vinculada_a_conta_removida_depois_e_recusada(client: Client) -> None:
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    _retorno(client)
    Conta.objects.filter(pk=conta.pk).update(situacao=Situacao.REMOVIDA)
    outro = Client()
    antes = _contagens()
    resposta = _retorno(outro)
    _recusado(outro, resposta, antes)


def test_login_com_google_registra_o_metodo_na_sessao(client: Client) -> None:
    ContaFactory.create(email_normalizado="ana@x.com")
    _retorno(client)
    metodos = [r["method"] for r in client.session["account_authentication_methods"]]
    assert metodos[-1] == "socialaccount"


def test_botao_do_google_na_tela_de_entrar_depende_da_configuracao(
    client: Client, settings: Any
) -> None:
    assert "Entrar com Google" in client.get("/entrar/").content.decode()
    settings.GOOGLE_CLIENT_ID = ""
    assert "Entrar com Google" not in client.get("/entrar/").content.decode()


def test_inicio_do_login_com_google_redireciona_para_o_google(client: Client) -> None:
    resposta = client.post("/entrar/google/login/")
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("https://accounts.google.com/")


def test_login_com_conta_social_ja_vinculada_nao_regrava_a_conta(client: Client) -> None:
    # E02-R01 (vínculo Google), caso 1: confere no allauth 65.19.7 que esse caminho não faz
    # `user.save()` sem `update_fields`; a única atualização de `contas_conta` é o `last_login`.
    import re

    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    ContaFactory.create(email_normalizado="ana@x.com")
    _retorno(client)  # cria o vínculo (caso 2)
    outro = Client()
    with CaptureQueriesContext(connection) as consultas:
        _retorno(outro)  # caso 1: conta social já vinculada
    assert _autenticado(outro)
    atualizacoes = [
        c["sql"] for c in consultas.captured_queries if c["sql"].startswith('UPDATE "contas_conta"')
    ]
    for sql in atualizacoes:
        assert set(re.findall(r'"(\w+)" =', sql.split(" WHERE ")[0])) == {"last_login"}, sql
