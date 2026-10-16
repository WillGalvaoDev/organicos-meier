"""E02-08: remoção, banimento e sessões (acceptance A-5 a A-10 e A-17)."""

from typing import Any

import pytest
from allauth.usersessions.models import UserSession
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import Client

from apps.contas.convites import emitir_convite
from apps.contas.models import Conta, Convite, EmailBanido, EmailEmUso, Situacao
from apps.contas.moderacao import remover
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.admin_fluxos import administrador_logado
from tests.apoio.urls import CHAMADAS_DA_ROTA_AUTENTICADA
from tests.fabricas import ContaFactory, ConviteFactory

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.apoio.urls")]

SENHA = "senha-forte-9271!"
ENCERRADA = "Sua sessão foi encerrada."


def _sessoes_da_conta(conta: Conta) -> int:
    alvo = str(conta.pk)
    return sum(1 for s in Session.objects.all() if s.get_decoded().get("_auth_user_id") == alvo)


def _clientes(conta: Conta, quantidade: int = 2) -> list[Client]:
    """Sessões abertas por login real (por senha): o `usersessions` registra no login."""
    conta.set_password(SENHA)
    conta.save()
    clientes = [Client() for _ in range(quantidade)]
    for cliente in clientes:
        cliente.post("/entrar/", {"login": conta.email_normalizado, "password": SENHA})
        assert "_auth_user_id" in cliente.session
    return clientes


def _remover_pela_tela(admin_client: Client, conta: Conta) -> Any:
    pagina = admin_client.get(f"/administracao/usuarios/{conta.pk}/remover/")
    assert pagina.status_code == 200
    assert "A remoção é definitiva e bane o e-mail." in pagina.content.decode()
    return admin_client.post(f"/administracao/usuarios/{conta.pk}/remover/")


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_remocao_bane_o_email_e_apaga_as_sessoes(client: Client, webauthn: Any) -> None:
    # A-5, cenários 20, 58, 83, T-24, T-36
    administrador_logado(client)
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    primeiro, segundo = _clientes(conta)
    assert _sessoes_da_conta(conta) == 2
    assert UserSession.objects.filter(user=conta).count() == 2

    resposta = _remover_pela_tela(client, conta)
    assert resposta.status_code == 302

    conta.refresh_from_db()
    assert conta.situacao == Situacao.REMOVIDA
    banido = EmailBanido.objects.get(email_normalizado="ana@x.com")
    assert banido.banido_por.papel == "administrador"
    assert banido.banido_em is not None
    assert _sessoes_da_conta(conta) == 0
    assert UserSession.objects.filter(user=conta).count() == 0
    for cliente in (primeiro, segundo):
        resposta = cliente.get("/inicio/")
        assert resposta.status_code == 302
        assert resposta["Location"].startswith("/entrar/")
    assert EntradaAuditoria.objects.filter(acao="conta.remover").count() == 1


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A-6, cenário 83, T-24, T-36: sessão criada na corrida com a remoção
    admin = ContaFactory.create(administrador=True)
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    sessoes = _clientes(conta, 4)  # uma única troca de senha: as quatro sessões valem
    para_get, para_post = sessoes[:2], sessoes[2:]
    monkeypatch.setattr("apps.contas.moderacao.encerrar_sessoes", lambda conta: 0)
    remover(admin, conta)
    assert _sessoes_da_conta(conta) == 4  # nada foi apagado
    CHAMADAS_DA_ROTA_AUTENTICADA.clear()

    for cliente in para_get:
        resposta = cliente.get("/teste/rota-autenticada/")
        assert resposta.status_code == 302
        assert resposta["Location"] == "/entrar/"
        assert "_auth_user_id" not in cliente.session
        assert ENCERRADA in cliente.get("/entrar/").content.decode()
    for cliente in para_post:
        resposta = cliente.post("/teste/rota-autenticada/")
        assert resposta.status_code == 403
        assert "_auth_user_id" not in cliente.session
    assert CHAMADAS_DA_ROTA_AUTENTICADA == []  # a view nunca executou


def test_middleware_recusa_conta_com_email_banido_mesmo_ativa() -> None:  # A-6 (banimento)
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    (cliente,) = _clientes(conta, 1)
    EmailBanido.objects.create(
        email_normalizado="ana@x.com", banido_por=ContaFactory.create(administrador=True)
    )
    CHAMADAS_DA_ROTA_AUTENTICADA.clear()
    resposta = cliente.get("/teste/rota-autenticada/")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/entrar/"
    assert CHAMADAS_DA_ROTA_AUTENTICADA == []


def test_middleware_deixa_passar_conta_suspensa_e_visitante() -> None:
    suspensa = ContaFactory.create(suspensa=True)
    (cliente,) = _clientes(suspensa, 1)
    assert cliente.get("/inicio/").status_code == 200
    anonimo = Client()
    assert anonimo.get("/entrar/").status_code == 200


def test_remocao_preserva_conta_historico_e_convite() -> None:  # A-7, cenários 20 e 58
    admin = ContaFactory.create(administrador=True)
    convite = ConviteFactory.create(email_normalizado="ana@x.com", consumido=True)
    assert convite.conta_criada is not None
    conta = convite.conta_criada
    remover(admin, conta)
    conta.refresh_from_db()
    assert conta.situacao == Situacao.REMOVIDA
    convite.refresh_from_db()
    assert convite.conta_criada == conta
    assert Convite.objects.filter(pk=convite.pk).exists()
    assert EntradaAuditoria.objects.filter(acao="conta.remover", objeto_id=str(conta.pk)).exists()


@pytest.mark.acceptance
def test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite() -> None:
    # A-8, cenário 58
    admin = ContaFactory.create(administrador=True)
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    conta.set_password(SENHA)
    conta.save()
    remover(admin, conta)

    senha = Client()
    senha.post("/entrar/", {"login": "ana@x.com", "password": SENHA})
    assert "_auth_user_id" not in senha.session

    mail.outbox.clear()
    Client().post("/entrar/link/", {"email": "ANA@x.com"})
    assert len(mail.outbox) == 0

    google = Client()
    resposta = google.post(
        "/teste/retorno-google/",
        {"extra_data": '{"sub": "g1", "email": "ana@x.com", "email_verified": true}'},
    )
    assert resposta["Location"] == "/entrar/"
    assert "_auth_user_id" not in google.session

    for variacao in ("ana@x.com", "  ANA@x.com ", "Ana@X.com"):
        with pytest.raises(EmailEmUso):
            emitir_convite(admin, variacao, "comprador")
    assert Convite.objects.count() == 0


@pytest.mark.acceptance
def test_remocao_afeta_so_o_endereco_exato(client: Client) -> None:  # A-9, cenários 59 e 84
    admin = ContaFactory.create(administrador=True)
    ana = ContaFactory.create(email_normalizado="ana@x.com")
    alias = ContaFactory.create(email_normalizado="ana+1@x.com")
    alias.set_password(SENHA)
    alias.save()
    remover(admin, ana)
    alias.refresh_from_db()
    assert alias.situacao == Situacao.ATIVA
    client.post("/entrar/", {"login": "ana+1@x.com", "password": SENHA})
    assert "_auth_user_id" in client.session
    convite = emitir_convite(admin, "a.na@x.com", "comprador")
    assert convite.email_normalizado == "a.na@x.com"


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa() -> None:
    # A-10, cenário 81, T-36
    admin = ContaFactory.create(administrador=True)
    comprador = ContaFactory.create(email_normalizado="ana@exemplo.com")
    fornecedor = ContaFactory.create(
        fornecedor=True, email_normalizado="ana.fornecedor@exemplo.com"
    )
    fornecedor.set_password(SENHA)
    fornecedor.save()
    (sessao_fornecedor,) = _clientes(fornecedor, 1)
    (sessao_comprador,) = _clientes(comprador, 1)
    remover(admin, comprador)
    assert sessao_fornecedor.get("/inicio/").status_code == 200
    assert sessao_comprador.get("/inicio/").status_code == 302
    novo = Client()
    novo.post("/entrar/", {"login": "ana.fornecedor@exemplo.com", "password": SENHA})
    assert "_auth_user_id" in novo.session


def test_falha_ao_encerrar_sessoes_desfaz_a_remocao(monkeypatch: pytest.MonkeyPatch) -> None:
    # A-17
    admin = ContaFactory.create(administrador=True)
    conta = ContaFactory.create(email_normalizado="ana@x.com")

    def falha(conta: Conta) -> int:
        raise RuntimeError("erro forçado ao apagar sessões")

    monkeypatch.setattr("apps.contas.moderacao.encerrar_sessoes", falha)
    with pytest.raises(RuntimeError):
        remover(admin, conta)
    conta.refresh_from_db()
    assert conta.situacao == Situacao.ATIVA
    assert EmailBanido.objects.count() == 0
    assert EntradaAuditoria.objects.filter(acao="conta.remover").count() == 0
