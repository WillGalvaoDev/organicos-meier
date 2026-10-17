"""E04-05: e-mails de acesso no registro de envios (acceptance A-1 a A-7, A-9 e A-10)."""

import logging
import re
from typing import Any

import pytest
from django.core import mail
from django.db import transaction
from django.test import Client

from apps.contas.convites import emitir_convite
from apps.contas.models import Conta, Convite, LinkDeAcesso
from apps.notificacoes.models import Envio, TentativaDeEnvio
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db(transaction=True)

ROTA_CONVITES = "/administracao/convites/"
FALHA = "tests.apoio.email_falho.BackendQueFalha"
FALHA_NA_TELA = "Convite criado, mas o e-mail não pôde ser enviado. Emita um novo convite."


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def _convidar(client: Client, email: str) -> Any:
    return client.post(ROTA_CONVITES, {"email": email, "papel": "comprador", "fornecedor": ""})


def _sem_csrf(resposta: Any) -> str:
    return re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', "", resposta.content.decode())


def test_convite_registra_o_envio(admin_client: Client) -> None:  # A-1
    resposta = _convidar(admin_client, "novo@x.com")
    assert resposta.status_code == 302
    assert len(mail.outbox) == 1
    convite = Convite.objects.get()
    envio = Envio.objects.get()
    assert envio.tipo == "acesso:convite"
    assert envio.canal == "email"
    assert envio.conta is None
    assert envio.notificacao is None
    assert envio.destino == "novo@x.com"
    assert envio.assunto == mail.outbox[0].subject
    assert envio.corpo == ""
    assert envio.chave == f"acesso:convite:{convite.pk}"
    assert (envio.situacao, envio.tentativas) == ("enviado", 1)
    assert envio.concluido_em is not None
    tentativa = TentativaDeEnvio.objects.get()
    assert (tentativa.envio_id, tentativa.numero, tentativa.resultado) == (envio.pk, 1, "sucesso")


def test_convite_emitido_pelo_servico_marca_email_enviado(admin_client: Client) -> None:  # A-1
    admin = Conta.objects.get(papel="administrador")
    convite = emitir_convite(admin, "novo@x.com", "comprador")
    assert convite.email_enviado is True
    assert Envio.objects.get().situacao == "enviado"


def test_falha_no_envio_do_convite_e_registrada(settings: Any, admin_client: Client) -> None:  # A-2
    settings.EMAIL_BACKEND = FALHA
    resposta = _convidar(admin_client, "novo@x.com")
    assert resposta.status_code == 302
    assert FALHA_NA_TELA in admin_client.get(ROTA_CONVITES).content.decode()
    envio = Envio.objects.get()
    assert (envio.situacao, envio.tentativas) == ("falhou", 1)
    assert envio.concluido_em is not None
    tentativa = TentativaDeEnvio.objects.get()
    assert (tentativa.resultado, tentativa.erro) == ("falha", "ConnectionError")
    _convidar(admin_client, "novo2@x.com")
    assert Envio.objects.filter(tipo="acesso:convite").count() == 2


def test_falha_no_servico_deixa_email_enviado_falso(
    settings: Any, admin_client: Client
) -> None:  # A-2
    settings.EMAIL_BACKEND = FALHA
    admin = Conta.objects.get(papel="administrador")
    assert emitir_convite(admin, "novo@x.com", "comprador").email_enviado is False


def test_link_de_acesso_registra_o_envio(client: Client) -> None:  # A-3
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    client.post("/entrar/link/", {"email": "ana@x.com"})
    link = LinkDeAcesso.objects.get()
    envio = Envio.objects.get()
    assert envio.tipo == "acesso:link_de_acesso"
    assert envio.conta_id == conta.pk
    assert envio.chave == f"acesso:link_de_acesso:{link.pk}"
    assert envio.corpo == ""
    assert (envio.situacao, envio.tentativas) == ("enviado", 1)
    assert len(mail.outbox) == 1


def test_link_para_email_sem_conta_nao_envia_nem_registra(client: Client) -> None:  # A-4
    ContaFactory.create(email_normalizado="ana@x.com")
    com_conta = client.post("/entrar/link/", {"email": "ana@x.com"})
    mail.outbox.clear()
    antes = Envio.objects.count()
    sem_conta = client.post("/entrar/link/", {"email": "ninguem@x.com"})
    assert Envio.objects.count() == antes
    assert mail.outbox == []
    assert _sem_csrf(sem_conta) == _sem_csrf(com_conta)


def test_link_com_falha_no_envio_responde_igual(settings: Any, client: Client) -> None:  # A-4
    ContaFactory.create(email_normalizado="ana@x.com")
    ContaFactory.create(email_normalizado="bia@x.com")
    sucesso = client.post("/entrar/link/", {"email": "ana@x.com"})
    settings.EMAIL_BACKEND = FALHA
    falha = client.post("/entrar/link/", {"email": "bia@x.com"})
    assert _sem_csrf(falha) == _sem_csrf(sucesso)
    assert sorted(Envio.objects.values_list("situacao", flat=True)) == ["enviado", "falhou"]


def test_recuperacao_de_senha_registra_o_envio(client: Client) -> None:  # A-5
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    client.post("/recuperar-acesso/", {"email": "ana@x.com"})
    envio = Envio.objects.get()
    assert envio.tipo == "acesso:conta_allauth"
    assert envio.modelo == "account/email/password_reset_key"
    assert envio.conta_id == conta.pk
    assert envio.corpo == ""
    assert envio.destino == "ana@x.com"
    assert (envio.situacao, envio.tentativas) == ("enviado", 1)
    assert len(mail.outbox) == 1
    assert "/recuperar-acesso/chave/" in str(mail.outbox[0].body)


def test_recuperacao_para_email_desconhecido_nao_envia_nem_registra(client: Client) -> None:  # A-6
    client.post("/recuperar-acesso/", {"email": "ninguem@x.com"})
    assert mail.outbox == []
    assert Envio.objects.count() == 0


def test_nenhum_segredo_no_banco_nem_no_log(
    admin_client: Client, caplog: pytest.LogCaptureFixture
) -> None:  # A-7
    caplog.set_level(logging.DEBUG)
    ContaFactory.create(email_normalizado="ana@x.com")
    _convidar(admin_client, "novo@x.com")
    Client().post("/entrar/link/", {"email": "ana@x.com"})
    Client().post("/recuperar-acesso/", {"email": "ana@x.com"})
    segredos: list[str] = []
    for mensagem in mail.outbox:
        corpo = str(mensagem.body)
        segredos += re.findall(r"https?://\S+", corpo)
        segredos += re.findall(r"/(?:convite|entrar/link|recuperar-acesso/chave)/([^\s/]+)", corpo)
    assert len(segredos) >= 6
    colunas = " ".join(
        str(v)
        for modelo in (Envio, TentativaDeEnvio)
        for linha in modelo.objects.values()
        for v in linha.values()
    )
    for segredo in segredos:
        assert segredo not in colunas
        assert segredo not in caplog.text


def test_convite_em_transacao_desfeita_nao_envia_nem_registra(admin_client: Client) -> None:  # A-9
    admin = Conta.objects.get(papel="administrador")

    def emitir_e_falhar() -> None:
        with transaction.atomic():
            emitir_convite(admin, "novo@x.com", "comprador")
            raise RuntimeError

    with pytest.raises(RuntimeError):
        emitir_e_falhar()
    assert mail.outbox == []
    assert Envio.objects.count() == 0
    assert Convite.objects.count() == 0


def test_falha_ao_gravar_o_registro_nao_quebra_o_fluxo(
    client: Client, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:  # A-10
    conta = ContaFactory.create(email_normalizado="ana@x.com")

    def estourar(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("falha ao gravar")

    monkeypatch.setattr(Envio.objects, "create", estourar)
    caplog.set_level(logging.DEBUG)
    resposta = client.post("/entrar/link/", {"email": "ana@x.com"})
    assert resposta.status_code == 200
    assert len(mail.outbox) == 1  # o e-mail já tinha saído
    link = LinkDeAcesso.objects.get(conta=conta)
    erros = [r for r in caplog.records if r.levelname == "ERROR"]
    assert any(
        "acesso:link_de_acesso" in r.getMessage() and str(link.pk) in r.getMessage() for r in erros
    )
    assert "ana@x.com" not in caplog.text
