"""E02-09: consentimento de WhatsApp (acceptance A-6 a A-9)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import Client

from apps.contas.models import Conta
from apps.nucleo.auditoria import EntradaAuditoria
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

T = datetime(2026, 10, 14, 15, 0, 0, tzinfo=UTC)
SENHA = "senha-forte-9271!"
NUMERO = "(21) 99999-8888"
E164 = "+5521999998888"


def _logado(**campos: Any) -> tuple[Client, Conta]:
    conta = ContaFactory.create(email_normalizado="ana@x.com", nome="Ana", **campos)
    conta.set_password(SENHA)
    conta.save()
    cliente = Client()
    cliente.post("/entrar/", {"login": "ana@x.com", "password": SENHA})
    return cliente, conta


def _salvar(cliente: Client, conta: Conta, **dados: Any) -> Any:
    base = {"nome": conta.nome, "telefone": conta.telefone or ""}
    return cliente.post("/perfil/", {**base, **dados})


def _auditorias(acao: str) -> list[EntradaAuditoria]:
    return list(EntradaAuditoria.objects.filter(acao=acao))


def test_consentir_com_telefone_grava_o_instante_e_audita_sem_o_numero(relogio: Any) -> None:
    # A-6
    cliente, conta = _logado(telefone=E164)
    relogio.congelar(T)
    resposta = _salvar(cliente, conta, whatsapp="on")
    assert resposta.status_code == 302
    conta.refresh_from_db()
    assert conta.whatsapp_consentido_em == T
    (entrada,) = _auditorias("perfil.whatsapp_consentir")
    assert entrada.alteracoes == {"conta": conta.pk}
    assert entrada.autor_id == str(conta.pk)
    assert E164 not in str(entrada.alteracoes)
    assert "99999" not in str(entrada.alteracoes)


def test_consentir_e_informar_o_telefone_na_mesma_gravacao() -> None:
    cliente, conta = _logado()
    _salvar(cliente, conta, telefone=NUMERO, whatsapp="on")
    conta.refresh_from_db()
    assert conta.telefone == E164
    assert conta.whatsapp_consentido_em is not None
    assert len(_auditorias("perfil.whatsapp_consentir")) == 1


def test_marcar_sem_telefone_e_recusado() -> None:  # A-7
    cliente, conta = _logado()
    resposta = _salvar(cliente, conta, whatsapp="on")
    assert resposta.status_code == 200
    assert resposta.context["form"].errors
    conta.refresh_from_db()
    assert conta.whatsapp_consentido_em is None
    assert _auditorias("perfil.whatsapp_consentir") == []


def test_desmarcar_revoga_e_audita() -> None:  # A-8 (a)
    cliente, conta = _logado(telefone=E164, whatsapp_consentido_em=T)
    _salvar(cliente, conta)  # a caixa não vem marcada
    conta.refresh_from_db()
    assert conta.whatsapp_consentido_em is None
    assert conta.telefone == E164
    assert len(_auditorias("perfil.whatsapp_revogar")) == 1


def test_remover_o_telefone_revoga_o_consentimento() -> None:  # A-8 (b)
    cliente, conta = _logado(telefone=E164, whatsapp_consentido_em=T)
    _salvar(cliente, conta, telefone="", whatsapp="on")
    conta.refresh_from_db()
    assert conta.telefone is None
    assert conta.whatsapp_consentido_em is None
    assert len(_auditorias("perfil.whatsapp_revogar")) == 1


def test_trocar_o_numero_revoga_o_consentimento() -> None:  # A-8 (c)
    cliente, conta = _logado(telefone=E164, whatsapp_consentido_em=T)
    _salvar(cliente, conta, telefone="(21) 98888-7777", whatsapp="on")
    conta.refresh_from_db()
    assert conta.telefone == "+5521988887777"
    assert conta.whatsapp_consentido_em is None  # aceitar de novo para o número novo
    assert len(_auditorias("perfil.whatsapp_revogar")) == 1
    assert _auditorias("perfil.whatsapp_consentir") == []


def test_aceitar_de_novo_depois_de_trocar_o_numero() -> None:
    cliente, conta = _logado(telefone=E164, whatsapp_consentido_em=T)
    _salvar(cliente, conta, telefone="(21) 98888-7777", whatsapp="on")
    conta.refresh_from_db()
    _salvar(cliente, conta, whatsapp="on")
    conta.refresh_from_db()
    assert conta.whatsapp_consentido_em is not None
    assert len(_auditorias("perfil.whatsapp_consentir")) == 1


def test_manter_o_consentimento_ativo_nao_gera_auditoria_nem_muda_o_instante(
    relogio: Any,
) -> None:
    cliente, conta = _logado(telefone=E164, whatsapp_consentido_em=T)
    relogio.congelar(datetime(2026, 11, 1, tzinfo=UTC))
    _salvar(cliente, conta, whatsapp="on", nome="Ana Souza")
    conta.refresh_from_db()
    assert conta.whatsapp_consentido_em == T
    assert _auditorias("perfil.whatsapp_consentir") == []
    assert _auditorias("perfil.whatsapp_revogar") == []


def test_banco_recusa_consentimento_sem_telefone() -> None:  # A-9
    conta = ContaFactory.create()
    with pytest.raises(IntegrityError, match="conta_whatsapp_exige_telefone"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE contas_conta SET whatsapp_consentido_em = now() WHERE id = %s", [conta.pk]
            )
    conta.refresh_from_db()
    assert conta.whatsapp_consentido_em is None


@pytest.mark.parametrize(
    "telefone", ["21999998888", "+5521", "+55219999988889999", "+5501999998888"]
)
def test_banco_so_aceita_telefone_e164_brasileiro(telefone: str) -> None:
    conta = ContaFactory.create()
    with pytest.raises(IntegrityError, match="conta_telefone_e164"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE contas_conta SET telefone = %s WHERE id = %s", [telefone, conta.pk]
            )
