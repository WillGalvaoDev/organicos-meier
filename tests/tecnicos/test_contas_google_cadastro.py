"""E02-07: cadastro com Google a partir de um convite (acceptance A-9 a A-15)."""

import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core import mail
from django.test import Client

from apps.contas.convites import MetodoCadastro, consumir_convite
from apps.contas.models import Conta, Convite, EmailBanido
from apps.nucleo.auditoria import EntradaAuditoria
from tests.fabricas import ContaFactory, ConviteFactory, FornecedorFactory

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.apoio.urls")]

T = datetime(2026, 10, 14, 15, 0, 0, tzinfo=UTC)
SENHA = "senha-forte-9271!"
RECUSA = "Não foi possível entrar com essa conta Google."
INVALIDO = "Este convite não é mais válido. Solicite um novo convite ao administrador."
CONCLUIR = "/entrar/google/concluir/"


def _convite(**campos: Any) -> tuple[Convite, str]:
    token = secrets.token_urlsafe(32)
    return ConviteFactory.create(token_hash=Convite.hash_do_token(token), **campos), token


def _retorno(
    client: Client, *, email: str = "bia@x.com", nome: str = "Bia G", uid: str = "g-9"
) -> Any:
    dados = {"sub": uid, "name": nome, "email": email, "email_verified": True}
    return client.post("/teste/retorno-google/", {"extra_data": json.dumps(dados)})


def _contagens() -> tuple[int, int, int]:
    return Conta.objects.count(), SocialAccount.objects.count(), EmailAddress.objects.count()


def _autenticado(client: Client) -> bool:
    return "_auth_user_id" in client.session


def _iniciar(client: Client, token: str) -> Any:
    return client.post(f"/convite/{token}/google/")


def test_cadastro_com_google_cria_conta_vinculada_e_consome_o_convite(client: Client) -> None:
    # A-9
    convite, token = _convite(email_normalizado="bia@x.com")
    inicio = _iniciar(client, token)
    assert inicio.status_code == 302
    assert inicio["Location"].startswith("https://accounts.google.com/")
    assert client.session["convite_pendente"] == token

    retorno = _retorno(client, email="Bia@x.com", nome="Bia G")
    assert retorno.status_code == 302
    assert retorno["Location"] == CONCLUIR
    formulario = client.get(CONCLUIR)
    assert formulario.status_code == 200
    assert 'value="Bia G"' in formulario.content.decode()
    assert not _autenticado(client)

    conclusao = client.post(CONCLUIR, {"nome": "Bia"})
    assert conclusao.status_code == 302
    assert conclusao["Location"] == "/inicio/"
    conta = Conta.objects.get(email_normalizado="bia@x.com")
    assert conta.nome == "Bia"
    assert conta.papel == "comprador"
    assert not conta.has_usable_password()
    endereco = EmailAddress.objects.get(user=conta)
    assert (endereco.verified, endereco.primary) == (True, True)
    assert SocialAccount.objects.get().user == conta
    convite.refresh_from_db()
    assert convite.consumido_em is not None
    assert convite.conta_criada == conta
    assert client.session["_auth_user_id"] == str(conta.pk)
    assert "convite_pendente" not in client.session
    assert EntradaAuditoria.objects.filter(acao="convite.consumir").count() == 1


@pytest.mark.acceptance
def test_google_com_outro_email_nao_cadastra_pelo_convite(
    client: Client,
) -> None:  # A-10, cenário 1
    convite, token = _convite(email_normalizado="bia@x.com")
    _iniciar(client, token)
    antes = _contagens()
    retorno = _retorno(client, email="outra@x.com")
    assert retorno.status_code == 302
    assert retorno["Location"] == "/entrar/"
    assert RECUSA in client.get("/entrar/").content.decode()
    assert _contagens() == antes
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert "convite_pendente" not in client.session
    assert not _autenticado(client)


def test_post_adulterado_na_conclusao_e_ignorado(client: Client) -> None:  # A-11
    f1 = FornecedorFactory.create(nome="F1")
    f2 = FornecedorFactory.create(nome="F2")
    _, token = _convite(fornecedor=True, fornecedor_id=f1.pk, email_normalizado="ze@x.com")
    _iniciar(client, token)
    _retorno(client, email="ze@x.com")
    client.post(CONCLUIR, {"nome": "Zé", "papel": "comprador", "fornecedor": f2.pk})
    conta = Conta.objects.get(email_normalizado="ze@x.com")
    assert conta.papel == "fornecedor"
    assert conta.fornecedor == f1


def test_convite_que_expira_antes_da_conclusao_e_recusado(client: Client, relogio: Any) -> None:
    # A-12 (expiração)
    convite, token = _convite(email_normalizado="bia@x.com", emitido_em=T)
    relogio.congelar(T + timedelta(hours=1))
    _iniciar(client, token)
    _retorno(client)
    relogio.congelar(T + timedelta(hours=24))
    antes = _contagens()
    resposta = client.post(CONCLUIR, {"nome": "Bia"})
    assert resposta.status_code == 302
    assert resposta["Location"] == "/entrar/"
    assert _contagens() == antes
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert not _autenticado(client)


def test_convite_consumido_por_senha_antes_da_conclusao_e_recusado(client: Client) -> None:
    # A-12 (consumo por senha)
    _, token = _convite(email_normalizado="bia@x.com")
    _iniciar(client, token)
    _retorno(client)
    consumir_convite(token, "Bia Senha", SENHA, metodo=MetodoCadastro.SENHA)
    contagens = _contagens()
    resposta = client.post(CONCLUIR, {"nome": "Bia"})
    assert resposta["Location"] == "/entrar/"
    assert _contagens() == contagens
    assert Conta.objects.filter(email_normalizado="bia@x.com").count() == 1
    assert Conta.objects.get(email_normalizado="bia@x.com").nome == "Bia Senha"
    assert SocialAccount.objects.count() == 0
    assert not _autenticado(client)


def _consumido() -> str:
    return _convite(consumido=True)[1]


def _expirado() -> str:
    return _convite(emitido_em=datetime(2020, 1, 1, tzinfo=UTC))[1]


def _banido() -> str:
    _, token = _convite(email_normalizado="banido@x.com")
    EmailBanido.objects.create(
        email_normalizado="banido@x.com",
        banido_por=ContaFactory.create(email_normalizado="q@x.com"),
    )
    return token


@pytest.mark.parametrize("preparar", [_consumido, _expirado, _banido])
def test_convite_invalido_nao_inicia_o_fluxo_do_google(client: Client, preparar: Any) -> None:
    # A-13
    token = preparar()
    resposta = _iniciar(client, token)
    assert resposta.status_code == 410
    assert INVALIDO in resposta.content.decode()
    assert "convite_pendente" not in client.session


def test_conclusao_aberta_diretamente_sem_convite_pendente_e_recusada(client: Client) -> None:
    # A-14
    antes = _contagens()
    for resposta in (client.get(CONCLUIR), client.post(CONCLUIR, {"nome": "Bia"})):
        assert resposta.status_code == 302
        assert resposta["Location"] == "/entrar/"
    retorno = _retorno(client, email="nova@x.com")  # sem convite pendente: recusado
    assert retorno["Location"] == "/entrar/"
    assert client.post(CONCLUIR, {"nome": "Bia"})["Location"] == "/entrar/"
    assert _contagens() == antes
    assert not _autenticado(client)


def test_conclusao_com_convite_pendente_mas_sem_retorno_do_google_e_recusada(
    client: Client,
) -> None:
    _, token = _convite(email_normalizado="bia@x.com")
    _iniciar(client, token)
    antes = _contagens()
    resposta = client.post(CONCLUIR, {"nome": "Bia"})
    assert resposta["Location"] == "/entrar/"
    assert _contagens() == antes


@pytest.mark.parametrize("nome", ["", "   ", "x" * 151])
def test_nome_invalido_na_conclusao_devolve_o_formulario(client: Client, nome: str) -> None:
    convite, token = _convite(email_normalizado="bia@x.com")
    _iniciar(client, token)
    _retorno(client)
    resposta = client.post(CONCLUIR, {"nome": nome})
    assert resposta.status_code == 200
    assert resposta.context["form"].errors
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert Conta.objects.filter(email_normalizado="bia@x.com").count() == 0
    # continua possível concluir com um nome válido
    assert client.post(CONCLUIR, {"nome": "Bia"}).status_code == 302


def test_conta_criada_pelo_google_define_senha_pela_recuperacao(
    client: Client, django_capture_on_commit_callbacks: Any
) -> None:  # A-15
    _, token = _convite(email_normalizado="bia@x.com")
    _iniciar(client, token)
    _retorno(client)
    client.post(CONCLUIR, {"nome": "Bia"})
    client.post("/sair/")
    mail.outbox.clear()
    novo = Client()
    with django_capture_on_commit_callbacks(execute=True):
        novo.post("/recuperar-acesso/", {"email": "bia@x.com"})
    assert len(mail.outbox) == 1
    link = re.findall(r"https?://[^\s]+/recuperar-acesso/chave/[^\s]+", str(mail.outbox[0].body))[0]
    caminho = "/" + link.split("/", 3)[3]
    pagina = novo.get(caminho, follow=True)
    formulario = str(pagina.redirect_chain[-1][0])
    novo.post(formulario, {"password1": SENHA, "password2": SENHA}, follow=True)
    entrada = Client()
    entrada.post("/entrar/", {"login": "bia@x.com", "password": SENHA})
    assert _autenticado(entrada)


def test_cadastro_por_google_exige_post_e_visitante_anonimo(client: Client) -> None:
    _, token = _convite()
    assert client.get(f"/convite/{token}/google/").status_code == 405
    client.force_login(ContaFactory.create(email_normalizado="ana@x.com"))
    resposta = client.post(f"/convite/{token}/google/")
    assert "Saia da conta atual" in resposta.content.decode()
    assert "convite_pendente" not in client.session


def test_botao_de_cadastro_com_google_aparece_na_pagina_do_convite(
    client: Client, settings: Any
) -> None:
    _, token = _convite()
    assert "Cadastrar com Google" in client.get(f"/convite/{token}/").content.decode()
    settings.GOOGLE_CLIENT_ID = ""
    assert "Cadastrar com Google" not in client.get(f"/convite/{token}/").content.decode()


def test_novo_login_com_google_limpa_o_convite_pendente_de_uma_conta_existente(
    client: Client,
) -> None:
    _, token = _convite(email_normalizado="bia@x.com")
    _iniciar(client, token)
    ContaFactory.create(email_normalizado="ana@x.com")
    _retorno(client, email="ana@x.com", uid="g-ana")
    assert "convite_pendente" not in client.session


# --- Correção E02-R03: e-mail verificado em qualquer formato do Google ---------------------

USERINFO = {
    "id": "google-revisor",
    "email": "google@x.com",
    "verified_email": True,
    "name": "Google",
}


def _retorno_com(client: Client, dados: dict[str, Any]) -> Any:
    return client.post("/teste/retorno-google/", {"extra_data": json.dumps(dados)})


# Teste do revisor (E02-10/review.md, revalidação 8f4dc36), copiado sem alteração do corpo.
# Nome original: test_google_userinfo_verificado_conclui_cadastro
@pytest.mark.django_db
@pytest.mark.urls("tests.apoio.urls")
def test_google_userinfo_verificado_conclui_cadastro(client):  # type: ignore[no-untyped-def]
    token = "token-revisor-google"  # noqa: S105
    ConviteFactory.create(email_normalizado="google@x.com", token_hash=Convite.hash_do_token(token))
    assert client.post(f"/convite/{token}/google/").status_code == 302
    dados = {
        "id": "google-revisor",
        "email": "google@x.com",
        "verified_email": True,
        "name": "Google",
    }
    retorno = client.post("/teste/retorno-google/", {"extra_data": json.dumps(dados)})
    assert retorno.status_code == 302
    assert retorno["Location"] == "/entrar/google/concluir/"
    resposta = client.post("/entrar/google/concluir/", {"nome": "Google"})
    assert resposta["Location"] == "/inicio/"
    assert Conta.objects.filter(email_normalizado="google@x.com").exists()


def test_formato_userinfo_tem_o_mesmo_resultado_do_cadastro_com_id_token(client: Client) -> None:
    # A-18
    convite, token = _convite(email_normalizado="google@x.com")
    _iniciar(client, token)
    retorno = _retorno_com(client, USERINFO)
    assert retorno["Location"] == CONCLUIR
    conclusao = client.post(CONCLUIR, {"nome": "Google"})
    assert conclusao["Location"] == "/inicio/"
    conta = Conta.objects.get(email_normalizado="google@x.com")
    assert SocialAccount.objects.get().user == conta
    assert not conta.has_usable_password()
    convite.refresh_from_db()
    assert convite.conta_criada == conta
    assert client.session["_auth_user_id"] == str(conta.pk)


NAO_VERIFICADOS = {
    "verified_email_falso": {"verified_email": False},
    "texto_true": {"email_verified": "true"},
    "conflito": {"email_verified": True, "verified_email": False},
    "sem_chaves": {},
}


@pytest.mark.parametrize("campos", NAO_VERIFICADOS.values(), ids=NAO_VERIFICADOS.keys())
def test_email_nao_verificado_nao_cadastra_pelo_convite(
    client: Client, campos: dict[str, Any]
) -> None:
    # A-19 (convite pendente)
    convite, token = _convite(email_normalizado="google@x.com")
    _iniciar(client, token)
    antes = _contagens()
    retorno = _retorno_com(client, {"id": "g-nv", "email": "google@x.com", "name": "G", **campos})
    if retorno["Location"] == CONCLUIR:  # se o retorno seguiu, a conclusão tem de recusar
        retorno = client.post(CONCLUIR, {"nome": "G"})
    assert retorno["Location"] == "/entrar/"
    assert _contagens() == antes
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert not _autenticado(client)


@pytest.mark.parametrize("campos", NAO_VERIFICADOS.values(), ids=NAO_VERIFICADOS.keys())
def test_email_nao_verificado_nao_entra_em_conta_existente(
    client: Client, campos: dict[str, Any]
) -> None:
    # A-19 (conta existente)
    ContaFactory.create(email_normalizado="google@x.com")
    antes = _contagens()
    retorno = _retorno_com(client, {"id": "g-nv", "email": "google@x.com", "name": "G", **campos})
    assert retorno["Location"] == "/entrar/"
    assert _contagens() == antes
    assert not _autenticado(client)


def test_funcao_unica_interpreta_a_verificacao_do_google() -> None:  # A-20
    from apps.contas.google import email_verificado_do_google

    positivos = [
        {"sub": "1", "email": " Google@X.com ", "email_verified": True},  # ID token
        {"id": "1", "email": "google@x.com", "verified_email": True},  # userinfo
        {"email": "google@x.com", "email_verified": True, "verified_email": True},
    ]
    for dados in positivos:
        assert email_verificado_do_google(dados) == "google@x.com", dados
    negativos: list[dict[str, Any]] = [
        {"email": "google@x.com", "verified_email": False},
        {"email": "google@x.com", "email_verified": "true"},
        {"email": "google@x.com", "email_verified": 1},
        {"email": "google@x.com", "email_verified": True, "verified_email": False},
        {"email": "google@x.com", "email_verified": None},
        {"email": "google@x.com"},
        {"email_verified": True},
        {"email": 123, "email_verified": True},
        {"email": "lixo", "email_verified": True},
        {"email": "", "email_verified": True},
    ]
    for dados in negativos:
        assert email_verificado_do_google(dados) is None, dados
    assert email_verificado_do_google(None) is None


def test_adaptador_e_conclusao_usam_a_mesma_funcao(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-20
    # (1) adaptador: com a função devolvendo None, o retorno do Google é recusado
    ContaFactory.create(email_normalizado="ana@x.com")
    monkeypatch.setattr("apps.contas.google.email_verificado_do_google", lambda dados: None)
    retorno = _retorno_com(client, {"sub": "g1", "email": "ana@x.com", "email_verified": True})
    assert retorno["Location"] == "/entrar/"
    assert not _autenticado(client)
    monkeypatch.undo()

    # (2) conclusão: o retorno passa com a função real; depois ela passa a devolver None
    convite, token = _convite(email_normalizado="bia@x.com")
    _iniciar(client, token)
    retorno = _retorno_com(client, {"sub": "g2", "email": "bia@x.com", "email_verified": True})
    assert retorno["Location"] == CONCLUIR
    monkeypatch.setattr("apps.contas.google.email_verificado_do_google", lambda dados: None)
    resposta = client.post(CONCLUIR, {"nome": "Bia"})
    assert resposta["Location"] == "/entrar/"
    convite.refresh_from_db()
    assert convite.consumido_em is None
    assert not Conta.objects.filter(email_normalizado="bia@x.com").exists()
