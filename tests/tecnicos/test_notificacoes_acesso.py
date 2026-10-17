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


# --- E04-R02: nenhum e-mail de acesso sai antes da confirmação (A-12 a A-16) ---


def _tres_fluxos(client: Client, admin: Conta, comprador: Conta) -> tuple[Any, Any]:
    recuperacao = client.post("/recuperar-acesso/", {"email": comprador.email_normalizado})
    emitir_convite(admin, "novo@x.com", "comprador")
    link = client.post("/entrar/link/", {"email": comprador.email_normalizado})
    return recuperacao, link


def test_os_tres_fluxos_so_enviam_e_registram_apos_a_confirmacao(
    client: Client, webauthn: Any
) -> None:  # A-12
    administrador_logado(Client())
    admin = Conta.objects.get(papel="administrador")
    comprador = ContaFactory.create(email_normalizado="ana@x.com")
    with transaction.atomic():
        _tres_fluxos(client, admin, comprador)
        assert len(mail.outbox) == 0
        assert Envio.objects.count() == 0
    assert len(mail.outbox) == 3
    envios = {e.tipo: e for e in Envio.objects.all()}
    assert set(envios) == {"acesso:conta_allauth", "acesso:convite", "acesso:link_de_acesso"}
    for envio in envios.values():
        assert envio.situacao == "enviado"
        tentativa = TentativaDeEnvio.objects.get(envio=envio)
        assert tentativa.resultado == "sucesso"
    allauth = envios["acesso:conta_allauth"]
    assert allauth.modelo == "account/email/password_reset_key"
    assert allauth.conta_id == comprador.pk


def test_rollback_nao_deixa_email_nem_registro_em_nenhum_dos_tres(
    client: Client, webauthn: Any
) -> None:  # A-13
    administrador_logado(Client())
    admin = Conta.objects.get(papel="administrador")
    comprador = ContaFactory.create(email_normalizado="ana@x.com")
    with pytest.raises(RuntimeError), transaction.atomic():  # noqa: PT012
        recuperacao, link = _tres_fluxos(client, admin, comprador)
        assert (recuperacao.status_code, link.status_code) == (302, 200)
        raise RuntimeError("rollback deliberado")
    assert len(mail.outbox) == 0
    assert Envio.objects.count() == 0
    assert TentativaDeEnvio.objects.count() == 0


@pytest.mark.parametrize("com_transacao", [False, True])
def test_falha_do_canal_na_recuperacao_responde_igual_e_so_depois_do_commit(
    settings: Any, client: Client, com_transacao: bool
) -> None:  # A-14
    from tests.apoio.email_falho import BackendQueFalhaPara

    ContaFactory.create(email_normalizado="ok@x.com")
    ContaFactory.create(email_normalizado="ana@x.com")
    sucesso = client.post("/recuperar-acesso/", {"email": "ok@x.com"})
    pagina_ok = _sem_csrf(client.get(sucesso["Location"]))
    settings.EMAIL_BACKEND = "tests.apoio.email_falho.BackendQueFalhaPara"
    BackendQueFalhaPara.configurar(destinos={"ana@x.com"})
    if com_transacao:
        with transaction.atomic():
            falha = client.post("/recuperar-acesso/", {"email": "ana@x.com"})
            assert BackendQueFalhaPara.chamadas == 0
        assert BackendQueFalhaPara.chamadas == 1
    else:
        falha = client.post("/recuperar-acesso/", {"email": "ana@x.com"})
        assert BackendQueFalhaPara.chamadas == 1
    assert (falha.status_code, falha["Location"]) == (sucesso.status_code, sucesso["Location"])
    assert _sem_csrf(client.get(falha["Location"])) == pagina_ok
    envio = Envio.objects.get(destino="ana@x.com")
    assert envio.situacao == "falhou"
    assert TentativaDeEnvio.objects.get(envio=envio).erro == "ConnectionError"


def test_falha_ao_gravar_o_registro_da_recuperacao_nao_quebra_o_fluxo(
    client: Client, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:  # A-15
    from django.db import DatabaseError

    ContaFactory.create(email_normalizado="ok@x.com")
    sucesso = client.post("/recuperar-acesso/", {"email": "ok@x.com"})
    mail.outbox.clear()
    ContaFactory.create(email_normalizado="ana@x.com")

    def estourar(*args: Any, **kwargs: Any) -> Any:
        raise DatabaseError("falha ao gravar")

    monkeypatch.setattr(Envio.objects, "create", estourar)
    caplog.set_level(logging.DEBUG)
    resposta = client.post("/recuperar-acesso/", {"email": "ana@x.com"})
    assert (resposta.status_code, resposta["Location"]) == (
        sucesso.status_code,
        sucesso["Location"],
    )
    assert len(mail.outbox) == 1
    assert Envio.objects.filter(destino="ana@x.com").count() == 0
    erros = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
    assert any("acesso:conta_allauth" in e for e in erros)
    assert "ana@x.com" not in caplog.text


def test_o_link_de_redefinicao_nao_vai_para_banco_log_nem_sessao(
    client: Client, caplog: pytest.LogCaptureFixture
) -> None:  # A-16
    caplog.set_level(logging.DEBUG)
    ContaFactory.create(email_normalizado="ana@x.com")
    with transaction.atomic():
        client.post("/recuperar-acesso/", {"email": "ana@x.com"})
    corpo = str(mail.outbox[0].body)
    link = re.findall(r"https?://\S+/recuperar-acesso/chave/\S+", corpo)[0]
    token = link.rstrip("/").rsplit("/", 1)[-1]
    colunas = " ".join(
        str(v)
        for modelo in (Envio, TentativaDeEnvio)
        for linha in modelo.objects.values()
        for v in linha.values()
    )
    sessao = str(dict(client.session.items()))
    for segredo in (link, token):
        assert segredo not in colunas
        assert segredo not in caplog.text
        assert segredo not in sessao


# --- probes do revisor de 0b52010 (corpo original) ---


def test_recuperacao_rollback_nao_envia_email(client: Client) -> None:
    conta = ContaFactory.create()
    with pytest.raises(RuntimeError), transaction.atomic():  # noqa: PT012
        resposta = client.post("/recuperar-acesso/", {"email": conta.email_normalizado})
        assert resposta.status_code == 302
        raise RuntimeError("rollback deliberado")
    assert Envio.objects.count() == 0
    assert len(mail.outbox) == 0, "email saiu, mas seu registro foi desfeito pelo rollback"


def test_recuperacao_so_envia_apos_commit(client: Client) -> None:
    conta = ContaFactory.create()
    with transaction.atomic():
        resposta = client.post("/recuperar-acesso/", {"email": conta.email_normalizado})
        assert resposta.status_code == 302
        antes_do_commit = len(mail.outbox)
    assert len(mail.outbox) == 1
    assert Envio.objects.count() == 1
    assert antes_do_commit == 0, "email enviado antes do commit"


def test_link_rollback_nao_envia_email(client: Client) -> None:
    conta = ContaFactory.create()
    with pytest.raises(RuntimeError), transaction.atomic():  # noqa: PT012
        resposta = client.post("/entrar/link/", {"email": conta.email_normalizado})
        assert resposta.status_code == 200
        raise RuntimeError("rollback deliberado")
    assert Envio.objects.count() == 0
    assert len(mail.outbox) == 0
