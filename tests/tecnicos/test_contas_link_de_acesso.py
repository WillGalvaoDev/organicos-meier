"""E02-06: link de acesso por e-mail (acceptance A-1 a A-12 e A-14 a A-17)."""

import hashlib
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.core import mail
from django.db import IntegrityError, connection, transaction
from django.test import Client

from apps.contas.link_de_acesso import LinkInvalido, usar_link
from apps.contas.models import Conta, EmailBanido, LinkDeAcesso, Situacao
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db(transaction=True)

T = datetime(2026, 10, 14, 15, 0, 0, tzinfo=UTC)
MS = timedelta(milliseconds=1)
PADRAO = "Se houver uma conta para este e-mail, enviaremos um link de acesso válido por 15 minutos."
INVALIDO = "Este link de acesso não é mais válido. Peça um novo."
ROTA = "/entrar/link/"


def _pedir(client: Client, email: str) -> Any:
    return client.post(ROTA, {"email": email})


def _token_do_ultimo_email() -> str:
    achados = re.findall(r"/entrar/link/([A-Za-z0-9_-]+)/", str(mail.outbox[-1].body))
    assert achados, mail.outbox[-1].body
    return str(achados[0])


def _autenticado(client: Client) -> bool:
    return "_auth_user_id" in client.session


def _link_para(email: str = "ana@x.com", **campos: Any) -> tuple[Conta, str]:
    conta = ContaFactory.create(email_normalizado=email, **campos)
    _pedir(Client(), email)
    return conta, _token_do_ultimo_email()


def test_pedido_cria_link_e_envia_email_para_o_endereco_normalizado(client: Client) -> None:  # A-1
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    resposta = _pedir(client, "  ANA@x.com")
    assert resposta.status_code == 200
    assert PADRAO in resposta.content.decode()
    link = LinkDeAcesso.objects.get()
    assert link.conta == conta
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["ana@x.com"]
    corpo = str(mail.outbox[0].body)
    assert re.search(r"http://testserver/entrar/link/[A-Za-z0-9_-]+/", corpo)
    assert "15 minutos" in corpo
    assert not re.search(r"\d{2}:\d{2}", corpo)  # só a validade em minutos, sem horário


def test_get_mostra_o_botao_sem_autenticar_nem_consumir(client: Client) -> None:  # A-2
    _, token = _link_para()
    resposta = client.get(f"{ROTA}{token}/")
    assert resposta.status_code == 200
    assert "Entrar" in resposta.content.decode()
    assert not _autenticado(client)
    assert LinkDeAcesso.objects.get().usado_em is None


def test_post_autentica_e_consome(client: Client) -> None:  # A-3
    conta, token = _link_para()
    resposta = client.post(f"{ROTA}{token}/")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/inicio/"
    assert client.session["_auth_user_id"] == str(conta.pk)
    assert LinkDeAcesso.objects.get().usado_em is not None


def test_link_usado_nao_autentica_de_novo(client: Client) -> None:  # A-4
    _, token = _link_para()
    client.post(f"{ROTA}{token}/")
    outro = Client()
    resposta = outro.post(f"{ROTA}{token}/")
    assert resposta.status_code == 410
    assert INVALIDO in resposta.content.decode()
    assert not _autenticado(outro)


@pytest.mark.parametrize(
    ("deslocamento", "aceito"),
    [(-MS, True), (timedelta(0), False), (MS, False)],
    ids=["um_ms_antes", "no_limite", "um_ms_depois"],
)
def test_fronteira_de_15_minutos(
    client: Client, relogio: Any, deslocamento: timedelta, aceito: bool
) -> None:  # A-5
    relogio.congelar(T)
    _, token = _link_para()
    relogio.congelar(T + timedelta(minutes=15) + deslocamento)
    resposta = client.post(f"{ROTA}{token}/")
    if aceito:
        assert resposta.status_code == 302
        assert _autenticado(client)
    else:
        assert resposta.status_code == 410
        assert not _autenticado(client)


def test_email_sem_conta_tem_a_mesma_resposta_e_nao_envia(client: Client) -> None:  # A-6
    ContaFactory.create(email_normalizado="ana@x.com")
    existente = _pedir(client, "ana@x.com")
    mail.outbox.clear()
    LinkDeAcesso.objects.all().delete()
    inexistente = _pedir(Client(), "ninguem@x.com")
    assert inexistente.status_code == existente.status_code
    assert inexistente.content == existente.content
    assert LinkDeAcesso.objects.count() == 0
    assert len(mail.outbox) == 0


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize("variacao", ["ana@x.com", "ANA@x.com", "  Ana@X.COM "])
@pytest.mark.parametrize("caso", ["banido", "removido"])
def test_banido_ou_removido_nao_recebe_link(
    client: Client, caso: str, variacao: str
) -> None:  # A-7
    # cenário 58, T-24 (link)
    ContaFactory.create(
        email_normalizado="ana@x.com",
        situacao=Situacao.REMOVIDA if caso == "removido" else Situacao.ATIVA,
    )
    if caso == "banido":
        EmailBanido.objects.create(
            email_normalizado="ana@x.com",
            banido_por=ContaFactory.create(email_normalizado="q@x.com"),
        )
    resposta = _pedir(client, variacao)
    assert resposta.status_code == 200
    assert PADRAO in resposta.content.decode()
    assert LinkDeAcesso.objects.count() == 0
    assert len(mail.outbox) == 0


def test_administrador_nao_recebe_link(client: Client) -> None:  # A-8
    ContaFactory.create(administrador=True, email_normalizado="admin@x.com")
    resposta = _pedir(client, "admin@x.com")
    assert PADRAO in resposta.content.decode()
    assert LinkDeAcesso.objects.count() == 0
    assert len(mail.outbox) == 0


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize("motivo", ["banido", "removido"])
def test_banimento_ou_remocao_depois_do_pedido_bloqueia_o_uso(
    client: Client, motivo: str
) -> None:  # A-9, cenários 2 e 58, T-24 (link)
    conta, token = _link_para()
    if motivo == "banido":
        EmailBanido.objects.create(
            email_normalizado="ana@x.com",
            banido_por=ContaFactory.create(email_normalizado="q@x.com"),
        )
    else:
        Conta.objects.filter(pk=conta.pk).update(situacao=Situacao.REMOVIDA)
    resposta = client.post(f"{ROTA}{token}/")
    assert resposta.status_code == 410
    assert INVALIDO in resposta.content.decode()
    assert not _autenticado(client)
    assert LinkDeAcesso.objects.get().usado_em is None


def test_suspensao_depois_do_pedido_nao_bloqueia(client: Client) -> None:  # A-10
    conta, token = _link_para()
    Conta.objects.filter(pk=conta.pk).update(situacao=Situacao.SUSPENSA)
    client.post(f"{ROTA}{token}/")
    assert _autenticado(client)


def test_alias_de_email_banido_recebe_e_usa_o_link(client: Client) -> None:  # A-11, cenário 59
    EmailBanido.objects.create(
        email_normalizado="ana@x.com", banido_por=ContaFactory.create(email_normalizado="q@x.com")
    )
    _, token = _link_para("ana+1@x.com")
    client.post(f"{ROTA}{token}/")
    assert _autenticado(client)


def test_limite_de_tres_links_em_15_minutos(client: Client, relogio: Any) -> None:  # A-12
    relogio.congelar(T)
    ContaFactory.create(email_normalizado="ana@x.com")
    for _ in range(4):
        resposta = _pedir(client, "ana@x.com")
        assert PADRAO in resposta.content.decode()
    assert LinkDeAcesso.objects.count() == 3
    assert len(mail.outbox) == 3
    relogio.congelar(T + timedelta(minutes=15))
    _pedir(client, "ana@x.com")
    assert LinkDeAcesso.objects.count() == 4
    assert len(mail.outbox) == 4


def test_limite_vale_por_conta(client: Client, relogio: Any) -> None:
    relogio.congelar(T)
    ContaFactory.create(email_normalizado="ana@x.com")
    ContaFactory.create(email_normalizado="bia@x.com")
    for _ in range(4):
        _pedir(client, "ana@x.com")
    _pedir(client, "bia@x.com")
    assert LinkDeAcesso.objects.filter(conta__email_normalizado="bia@x.com").count() == 1


def test_token_alterado_e_recusado(client: Client) -> None:  # A-14
    _, token = _link_para()
    alterado = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert client.get(f"{ROTA}{alterado}/").status_code == 410
    assert client.post(f"{ROTA}{alterado}/").status_code == 410
    assert not _autenticado(client)


def test_token_so_existe_como_hash() -> None:  # A-15
    _, token = _link_para()
    link = LinkDeAcesso.objects.get()
    assert link.token_hash == hashlib.sha256(token.encode()).hexdigest()
    for campo in link._meta.concrete_fields:
        assert token not in str(getattr(link, campo.attname))


def test_dois_links_pendentes_da_mesma_conta_sao_independentes() -> None:  # A-16
    ContaFactory.create(email_normalizado="ana@x.com")
    _pedir(Client(), "ana@x.com")
    primeiro = _token_do_ultimo_email()
    _pedir(Client(), "ana@x.com")
    segundo = _token_do_ultimo_email()
    assert primeiro != segundo
    for token in (primeiro, segundo):
        cliente = Client()
        cliente.post(f"{ROTA}{token}/")
        assert _autenticado(cliente)
    assert LinkDeAcesso.objects.filter(usado_em__isnull=False).count() == 2


def test_email_mal_formado_e_erro_de_formulario(client: Client) -> None:  # A-17
    resposta = _pedir(client, "lixo")
    assert resposta.status_code == 200
    assert resposta.context["form"].errors
    assert PADRAO not in resposta.content.decode()
    assert LinkDeAcesso.objects.count() == 0


def test_link_usado_por_quem_ja_esta_autenticado_troca_a_sessao(client: Client) -> None:
    outra = ContaFactory.create(email_normalizado="outra@x.com")
    client.force_login(outra)
    conta, token = _link_para("ana@x.com")
    client.post(f"{ROTA}{token}/")
    assert client.session["_auth_user_id"] == str(conta.pk)


def test_uso_nao_invalida_os_outros_links_da_conta() -> None:
    ContaFactory.create(email_normalizado="ana@x.com")
    _pedir(Client(), "ana@x.com")
    _pedir(Client(), "ana@x.com")
    token = _token_do_ultimo_email()
    usar_link(token)
    assert LinkDeAcesso.objects.filter(usado_em__isnull=True).count() == 1


def test_servico_levanta_link_invalido_para_token_inexistente() -> None:
    with pytest.raises(LinkInvalido):
        usar_link("nao-existe")


def test_banco_exige_validade_de_15_minutos_e_token_unico() -> None:
    conta = ContaFactory.create(email_normalizado="ana@x.com")

    def inserir(token_hash: str, expira_em: datetime) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO contas_linkdeacesso (conta_id, token_hash, criado_em, expira_em) "
                "VALUES (%s, %s, %s, %s)",
                [conta.pk, token_hash, T, expira_em],
            )

    with pytest.raises(IntegrityError, match="link_validade_15min"), transaction.atomic():
        inserir("a" * 64, T + timedelta(minutes=16))
    inserir("b" * 64, T + timedelta(minutes=15))
    with pytest.raises(IntegrityError), transaction.atomic():
        inserir("b" * 64, T + timedelta(minutes=15))
