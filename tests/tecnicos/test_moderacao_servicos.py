"""E02-08: serviços de moderação (acceptance A-1 a A-4, A-11, A-12, A-14 e A-19)."""

from typing import Any

import pytest
from allauth.usersessions.models import UserSession
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.test import Client

from apps.contas.models import Conta, EmailBanido, Situacao
from apps.contas.moderacao import (
    ModeracaoInvalida,
    conta_suspensa,
    reativar,
    remover,
    suspender,
)
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin() -> Conta:
    return ContaFactory.create(administrador=True, email_normalizado="admin@x.com")


def _situacao(conta: Conta) -> str:
    conta.refresh_from_db()
    return str(conta.situacao)


def _auditorias(acao: str) -> int:
    return EntradaAuditoria.objects.filter(acao=acao).count()


@pytest.mark.acceptance
def test_suspender_pela_tela_nao_encerra_a_sessao_nem_bane(  # A-1, cenário 60
    client: Client, webauthn: Any
) -> None:
    administrador_logado(client)
    comprador = ContaFactory.create(email_normalizado="ana@x.com")
    comprador.set_password("senha-forte-9271!")
    comprador.save()
    sessao_do_comprador = Client()
    sessao_do_comprador.post("/entrar/", {"login": "ana@x.com", "password": "senha-forte-9271!"})
    resposta = client.post(f"/administracao/usuarios/{comprador.pk}/suspender/")
    assert resposta.status_code == 302
    assert _situacao(comprador) == Situacao.SUSPENSA
    assert EmailBanido.objects.count() == 0
    assert sessao_do_comprador.get("/inicio/").status_code == 200
    assert _auditorias("conta.suspender") == 1


def test_auditoria_da_suspensao_nao_tem_email(admin: Conta) -> None:
    comprador = ContaFactory.create(email_normalizado="ana@x.com")
    suspender(admin, comprador)
    entrada = EntradaAuditoria.objects.get(acao="conta.suspender")
    assert entrada.autor_id == str(admin.pk)
    assert entrada.alteracoes == {
        "conta": comprador.pk,
        "situacao_anterior": "ativa",
        "situacao_nova": "suspensa",
    }
    assert "ana@x.com" not in str(entrada.alteracoes)


def test_sinal_de_suspensao_roda_dentro_da_transacao(admin: Conta) -> None:  # A-2
    chamadas: list[tuple[Any, bool]] = []

    def receptor(sender: Any, conta: Conta, **kwargs: Any) -> None:
        chamadas.append((conta, transaction.get_connection().in_atomic_block))

    comprador = ContaFactory.create()
    conta_suspensa.connect(receptor, weak=False)
    try:
        suspender(admin, comprador)
    finally:
        conta_suspensa.disconnect(receptor)
    assert len(chamadas) == 1
    assert chamadas[0][0].pk == comprador.pk
    assert chamadas[0][1] is True


def test_receptor_que_falha_desfaz_a_suspensao(admin: Conta) -> None:  # A-3
    def receptor(sender: Any, conta: Conta, **kwargs: Any) -> None:
        raise RuntimeError("efeito de etapa futura falhou")

    comprador = ContaFactory.create()
    conta_suspensa.connect(receptor, weak=False)
    try:
        with pytest.raises(RuntimeError):
            suspender(admin, comprador)
    finally:
        conta_suspensa.disconnect(receptor)
    assert _situacao(comprador) == Situacao.ATIVA
    assert _auditorias("conta.suspender") == 0


@pytest.mark.acceptance
def test_reativar_volta_a_ativa_sem_restaurar_nada(admin: Conta) -> None:  # A-4, cenários 19 e 60
    comprador = ContaFactory.create(suspensa=True, nome="Ana")
    antes = dict(Conta.objects.filter(pk=comprador.pk).values().get())
    reativar(admin, comprador)
    depois = dict(Conta.objects.filter(pk=comprador.pk).values().get())
    assert depois.pop("situacao") == "ativa"
    assert antes.pop("situacao") == "suspensa"
    assert antes == depois
    assert _auditorias("conta.reativar") == 1
    assert EmailBanido.objects.count() == 0


@pytest.mark.parametrize("acao", [suspender, reativar, remover])
def test_administrador_nunca_e_alvo(admin: Conta, acao: Any) -> None:  # A-11
    with pytest.raises(ModeracaoInvalida):
        acao(admin, admin)
    assert _situacao(admin) == Situacao.ATIVA
    assert EntradaAuditoria.objects.count() == 0
    assert EmailBanido.objects.count() == 0


def test_suspender_fornecedor_e_recusado(admin: Conta) -> None:  # A-12 (a)
    fornecedor = ContaFactory.create(fornecedor=True)
    with pytest.raises(ModeracaoInvalida):
        suspender(admin, fornecedor)
    assert _situacao(fornecedor) == Situacao.ATIVA
    assert EntradaAuditoria.objects.count() == 0


def test_suspender_quem_ja_esta_suspenso_e_recusado(admin: Conta) -> None:  # A-12 (b)
    suspenso = ContaFactory.create(suspensa=True)
    with pytest.raises(ModeracaoInvalida):
        suspender(admin, suspenso)
    assert EntradaAuditoria.objects.count() == 0


def test_reativar_quem_esta_ativo_e_recusado(admin: Conta) -> None:  # A-12 (c)
    with pytest.raises(ModeracaoInvalida):
        reativar(admin, ContaFactory.create())
    assert EntradaAuditoria.objects.count() == 0


def test_remover_quem_ja_foi_removido_e_recusado(admin: Conta) -> None:  # A-12 (d)
    removida = ContaFactory.create(situacao=Situacao.REMOVIDA)
    with pytest.raises(ModeracaoInvalida):
        remover(admin, removida)
    assert EntradaAuditoria.objects.count() == 0
    assert EmailBanido.objects.count() == 0


def test_reativar_fornecedor_e_recusado(admin: Conta) -> None:
    with pytest.raises(ModeracaoInvalida):
        reativar(admin, ContaFactory.create(fornecedor=True))


@pytest.mark.parametrize("acao", [suspender, reativar, remover])
def test_outro_autor_que_nao_o_administrador_e_recusado(acao: Any) -> None:  # A-14
    alvo = ContaFactory.create(suspensa=True)
    with pytest.raises(PermissionDenied):
        acao(ContaFactory.create(), alvo)
    with pytest.raises(PermissionDenied):
        acao(ContaFactory.create(fornecedor=True), alvo)
    assert _situacao(alvo) == Situacao.SUSPENSA
    assert EntradaAuditoria.objects.count() == 0
    assert EmailBanido.objects.count() == 0


def test_pode_adicionar_interesse_so_para_comprador_ativo() -> None:  # A-19
    assert ContaFactory.create().pode_adicionar_interesse is True
    assert ContaFactory.create(suspensa=True).pode_adicionar_interesse is False
    assert ContaFactory.create(fornecedor=True).pode_adicionar_interesse is False
    assert ContaFactory.create(situacao=Situacao.REMOVIDA).pode_adicionar_interesse is False
    assert ContaFactory.create(administrador=True).pode_adicionar_interesse is False


def test_suspensao_nao_apaga_sessoes(admin: Conta) -> None:
    comprador = ContaFactory.create(email_normalizado="ana@x.com")
    comprador.set_password("senha-forte-9271!")
    comprador.save()
    cliente = Client()
    cliente.post("/entrar/", {"login": "ana@x.com", "password": "senha-forte-9271!"})
    assert UserSession.objects.filter(user=comprador).exists()
    suspender(admin, comprador)
    assert UserSession.objects.filter(user=comprador).exists()
