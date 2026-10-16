"""E02-02: recuperação de acesso (acceptance A-10, A-11, A-13 a A-15)."""

import re
from typing import Any

import pytest
from django.core import mail
from django.test import Client

from apps.contas.models import Conta, EmailBanido, Situacao
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

SENHA = "senha-forte-9271!"
NOVA = "outra-senha-forte-5530!"


def _conta(**campos: Any) -> Conta:
    conta = ContaFactory.create(**campos)
    conta.set_password(SENHA)
    conta.save()
    return conta


def _pedir(client: Client, email: str) -> Any:
    return client.post("/recuperar-acesso/", {"email": email}, follow=True)


def _link_do_ultimo_email() -> str:
    corpo = str(mail.outbox[-1].body)
    achados = re.findall(r"https?://[^\s]+/recuperar-acesso/chave/[^\s]+", corpo)
    assert achados, corpo
    return str("/" + achados[0].split("/", 3)[3])


def _formulario_da_chave(client: Client, link: str) -> str:
    resposta = client.get(link, follow=True)
    assert resposta.status_code == 200
    return str(resposta.redirect_chain[-1][0]) if resposta.redirect_chain else link


def _banir(email: str) -> None:
    quem = ContaFactory.create(email_normalizado="quem.baniu@x.com")
    EmailBanido.objects.create(email_normalizado=email, banido_por=quem)


def test_recuperacao_envia_um_email_com_link_para_o_endereco_normalizado(
    client: Client,
) -> None:  # A-10
    _conta(email_normalizado="ana@x.com")
    resposta = _pedir(client, " Ana@X.com")
    assert resposta.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["ana@x.com"]
    _link_do_ultimo_email()


def test_recuperacao_responde_igual_para_qualquer_email_e_nao_envia(client: Client) -> None:  # A-11
    _conta(email_normalizado="ana@x.com")
    referencia = _pedir(client, "ana@x.com")
    assert len(mail.outbox) == 1
    mail.outbox.clear()

    _conta(email_normalizado="banida@x.com")
    _banir("banida@x.com")
    _conta(email_normalizado="removida@x.com", situacao=Situacao.REMOVIDA)
    for email in ["ninguem@x.com", "banida@x.com", "removida@x.com"]:
        resposta = _pedir(Client(), email)
        assert len(mail.outbox) == 0, email
        assert resposta.status_code == referencia.status_code
        assert resposta.redirect_chain == referencia.redirect_chain
        assert resposta.templates[0].name == referencia.templates[0].name


def test_recuperacao_inclui_o_administrador_para_definir_a_primeira_senha(
    client: Client,
) -> None:
    ContaFactory.create(administrador=True, email_normalizado="admin@x.com")
    _pedir(client, "admin@x.com")
    assert len(mail.outbox) == 1


def test_redefinicao_troca_a_senha_e_o_link_so_vale_uma_vez(client: Client) -> None:  # A-13
    conta = _conta(email_normalizado="ana@x.com")
    _pedir(client, "ana@x.com")
    link = _link_do_ultimo_email()

    url_do_formulario = _formulario_da_chave(client, link)
    resposta = client.post(url_do_formulario, {"password1": NOVA, "password2": NOVA}, follow=True)
    assert resposta.status_code == 200
    conta.refresh_from_db()
    assert conta.check_password(NOVA)
    assert not conta.check_password(SENHA)
    assert "_auth_user_id" not in client.session  # sem login automático

    entrada = Client()
    assert entrada.post("/entrar/", {"login": "ana@x.com", "password": SENHA}).status_code == 200
    assert "_auth_user_id" not in entrada.session
    entrada.post("/entrar/", {"login": "ana@x.com", "password": NOVA})
    assert "_auth_user_id" in entrada.session

    reuso = Client().get(link, follow=True)
    assert "inválido ou expirou" in reuso.content.decode()


def test_redefinicao_e_recusada_se_o_email_for_banido_depois_do_envio(
    client: Client,
) -> None:  # A-14
    conta = _conta(email_normalizado="ana@x.com")
    _pedir(client, "ana@x.com")
    link = _link_do_ultimo_email()
    _banir("ana@x.com")
    url_do_formulario = _formulario_da_chave(client, link)
    resposta = client.post(url_do_formulario, {"password1": NOVA, "password2": NOVA}, follow=True)
    conta.refresh_from_db()
    assert conta.check_password(SENHA)
    assert not conta.check_password(NOVA)
    assert resposta.status_code == 200


def test_redefinicao_e_recusada_se_a_conta_for_removida_depois_do_envio(client: Client) -> None:
    conta = _conta(email_normalizado="ana@x.com")
    _pedir(client, "ana@x.com")
    link = _link_do_ultimo_email()
    Conta.objects.filter(pk=conta.pk).update(situacao=Situacao.REMOVIDA)
    url_do_formulario = _formulario_da_chave(client, link)
    client.post(url_do_formulario, {"password1": NOVA, "password2": NOVA}, follow=True)
    conta.refresh_from_db()
    assert conta.check_password(SENHA)


@pytest.mark.parametrize(
    "fraca",
    ["ab1cd2ef3", "1234567890123", "qwertyuiop"],
    ids=["nove_caracteres", "so_numerica", "comum"],
)
def test_redefinicao_aplica_os_validadores_de_senha(client: Client, fraca: str) -> None:  # A-15
    conta = _conta(email_normalizado="ana@x.com")
    _pedir(client, "ana@x.com")
    url_do_formulario = _formulario_da_chave(client, _link_do_ultimo_email())
    resposta = client.post(url_do_formulario, {"password1": fraca, "password2": fraca}, follow=True)
    assert resposta.status_code == 200
    assert resposta.context["form"].errors
    conta.refresh_from_db()
    assert conta.check_password(SENHA)


def test_redefinicao_de_conta_suspensa_funciona(client: Client) -> None:
    conta = _conta(email_normalizado="ana@x.com", suspensa=True)
    _pedir(client, "ana@x.com")
    assert len(mail.outbox) == 1
    url_do_formulario = _formulario_da_chave(client, _link_do_ultimo_email())
    client.post(url_do_formulario, {"password1": NOVA, "password2": NOVA}, follow=True)
    conta.refresh_from_db()
    assert conta.check_password(NOVA)


def _tentar_redefinir(client: Client, conta: Conta, senha: str) -> Any:
    _pedir(client, conta.email_normalizado)
    url_do_formulario = _formulario_da_chave(client, _link_do_ultimo_email())
    return client.post(url_do_formulario, {"password1": senha, "password2": senha}, follow=True)


def _codigos_de_erro(resposta: Any, campo: str = "password1") -> list[str]:
    erros = resposta.context["form"].errors.as_data().get(campo, [])
    return [str(erro.code) for erro in erros]


def test_redefinicao_recusa_senha_semelhante_ao_nome(client: Client) -> None:  # A-22, E02-R04
    conta = _conta(email_normalizado="ana@x.com", nome="Marina Quintela Abreu")
    resposta = _tentar_redefinir(client, conta, "MarinaQuintelaAbreu")
    assert resposta.status_code == 200
    assert "password_too_similar" in _codigos_de_erro(resposta)
    assert "parecida" in resposta.content.decode() or "semelhante" in resposta.content.decode()
    conta.refresh_from_db()
    assert conta.check_password(SENHA)
    assert not conta.check_password("MarinaQuintelaAbreu")


def test_redefinicao_recusa_senha_semelhante_ao_email(client: Client) -> None:  # A-23, E02-R04
    conta = _conta(email_normalizado="quintelaabreu2026@exemplo.com", nome="Beatriz")
    resposta = _tentar_redefinir(client, conta, "quintelaabreu2026")
    assert resposta.status_code == 200
    assert "password_too_similar" in _codigos_de_erro(resposta)
    conta.refresh_from_db()
    assert conta.check_password(SENHA)
    assert not conta.check_password("quintelaabreu2026")


def test_redefinicao_aceita_senha_sem_relacao_com_a_conta(client: Client) -> None:
    conta = _conta(email_normalizado="ana@x.com", nome="Marina Quintela Abreu")
    resposta = _tentar_redefinir(client, conta, "cavalo-lanterna-7391!")
    assert resposta.status_code == 200
    conta.refresh_from_db()
    assert conta.check_password("cavalo-lanterna-7391!")


def test_redefinicao_preserva_suspensao_feita_depois_da_leitura(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-25 (E02-R01, recuperação)
    from apps.contas import formularios
    from apps.contas.moderacao import suspender
    from apps.nucleo.auditoria import EntradaAuditoria

    admin = ContaFactory.create(administrador=True)
    conta = _conta(email_normalizado="ana@x.com")
    _pedir(client, "ana@x.com")
    url_do_formulario = _formulario_da_chave(client, _link_do_ultimo_email())

    original = formularios.verificar_acesso  # type: ignore[attr-defined]

    def intercalado(alvo: Conta, email: str, metodo: Any) -> None:
        original(alvo, email, metodo)  # a revalidação passa: a conta ainda está ativa
        suspender(admin, Conta.objects.get(pk=alvo.pk))  # suspensa depois da leitura do link

    monkeypatch.setattr(formularios, "verificar_acesso", intercalado)
    client.post(url_do_formulario, {"password1": NOVA, "password2": NOVA}, follow=True)
    conta.refresh_from_db()
    assert conta.check_password(NOVA)
    assert not conta.check_password(SENHA)
    assert conta.situacao == Situacao.SUSPENSA
    assert EntradaAuditoria.objects.filter(acao="conta.reativar").count() == 0
