"""E04-04: canal de WhatsApp simulado, número e consentimento (A-1 a A-8, A-12 e A-13)."""

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from django.core import mail
from django.db import transaction

from apps.contas.models import Conta
from apps.contas.perfil import atualizar_perfil
from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento
from apps.notificacoes.models import Envio, TentativaDeEnvio
from apps.notificacoes.processamento import processar_envios
from apps.notificacoes.whatsapp import (
    CanalWhatsAppDesligado,
    CanalWhatsAppSimulado,
    obter_canal_whatsapp,
)
from apps.nucleo.tempo import agora
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
NUMERO = "+5521999990000"


def _com_consentimento(**extra: Any) -> Conta:
    return ContaFactory.create(telefone=NUMERO, whatsapp_consentido_em=agora(), **extra)


def _emitir(evento: Evento, conta: Conta, chave: str = "k:1", link: str | None = None) -> None:
    with transaction.atomic():
        emitir_evento(
            evento, conta, titulo="Retirada liberada", corpo="Corpo", link=link, chave=chave
        )


def test_retirada_liberada_cria_e_envia_email_e_whatsapp(
    settings: Any, simulador_whatsapp: CanalWhatsAppSimulado
) -> None:  # A-1
    settings.ORIGEM_PUBLICA = "https://om.test"
    conta = _com_consentimento()
    _emitir(Evento.RETIRADA_LIBERADA, conta, link="/retiradas/")
    assert sorted(Envio.objects.values_list("canal", flat=True)) == ["email", "whatsapp"]
    assert processar_envios() == 2
    assert {e.canal: e.situacao for e in Envio.objects.all()} == {
        "email": "enviado",
        "whatsapp": "enviado",
    }
    assert [(m.numero, m.texto) for m in simulador_whatsapp.mensagens] == [
        (NUMERO, "Retirada liberada https://om.test/retiradas/")
    ]
    assert Envio.objects.get(canal="whatsapp").destino == ""
    assert Envio.objects.get(canal="whatsapp").chave == "k:1:whatsapp"


def test_mensagem_sem_link_leva_so_o_titulo(
    simulador_whatsapp: CanalWhatsAppSimulado,
) -> None:  # A-1
    conta = _com_consentimento()
    _emitir(Evento.RETIRADA_LIBERADA, conta)
    processar_envios()
    assert [m.texto for m in simulador_whatsapp.mensagens] == ["Retirada liberada"]


def test_sem_telefone_ou_sem_consentimento_so_ha_email() -> None:  # A-2
    sem_telefone = ContaFactory.create()
    sem_consentimento = ContaFactory.create(telefone=NUMERO)
    _emitir(Evento.RETIRADA_LIBERADA, sem_telefone, chave="a")
    _emitir(Evento.RETIRADA_LIBERADA, sem_consentimento, chave="b")
    assert sorted(Envio.objects.values_list("canal", flat=True)) == ["email", "email"]


def test_evento_sem_whatsapp_na_matriz() -> None:  # A-3
    _emitir(Evento.ESTORNO, _com_consentimento())
    assert sorted(Envio.objects.values_list("canal", flat=True)) == ["email"]


def test_canal_desligado_nao_cria_envio_de_whatsapp(settings: Any) -> None:  # A-4
    settings.CANAL_WHATSAPP = "desligado"
    _emitir(Evento.PAGAMENTO_ABERTO, _com_consentimento())
    assert sorted(Envio.objects.values_list("canal", flat=True)) == ["email"]


def test_consentimento_revogado_antes_do_envio_cancela(
    simulador_whatsapp: CanalWhatsAppSimulado,
) -> None:  # A-5
    conta = _com_consentimento()
    _emitir(Evento.RETIRADA_LIBERADA, conta)
    atualizar_perfil(conta, nome=conta.nome, telefone=NUMERO, whatsapp=False)
    processar_envios()
    envio = Envio.objects.get(canal="whatsapp")
    assert envio.situacao == "cancelado"
    assert envio.motivo_cancelamento == "sem_consentimento"
    assert envio.concluido_em is not None
    assert envio.tentativas == 0
    assert TentativaDeEnvio.objects.filter(envio=envio).count() == 0
    assert simulador_whatsapp.mensagens == []
    assert Envio.objects.get(canal="email").situacao == "enviado"
    assert len(mail.outbox) == 1


def test_telefone_removido_tambem_cancela(simulador_whatsapp: CanalWhatsAppSimulado) -> None:  # A-5
    conta = _com_consentimento()
    _emitir(Evento.RETIRADA_LIBERADA, conta)
    atualizar_perfil(conta, nome=conta.nome, telefone=None, whatsapp=False)
    processar_envios()
    envio = Envio.objects.get(canal="whatsapp")
    assert (envio.situacao, envio.motivo_cancelamento) == ("cancelado", "sem_consentimento")
    assert simulador_whatsapp.mensagens == []


def test_canal_desligado_depois_da_emissao_cancela(
    settings: Any, simulador_whatsapp: CanalWhatsAppSimulado
) -> None:  # A-6
    _emitir(Evento.RETIRADA_LIBERADA, _com_consentimento())
    settings.CANAL_WHATSAPP = "desligado"
    processar_envios()
    envio = Envio.objects.get(canal="whatsapp")
    assert (envio.situacao, envio.motivo_cancelamento) == ("cancelado", "canal_desligado")
    assert envio.tentativas == 0
    assert TentativaDeEnvio.objects.filter(envio=envio).count() == 0
    assert simulador_whatsapp.mensagens == []


def test_usa_o_numero_atual_da_conta(simulador_whatsapp: CanalWhatsAppSimulado) -> None:  # A-7
    conta = _com_consentimento()
    _emitir(Evento.RETIRADA_LIBERADA, conta)
    Conta.objects.filter(pk=conta.pk).update(telefone="+5521988887777")
    processar_envios()
    assert [m.numero for m in simulador_whatsapp.mensagens] == ["+5521988887777"]
    for tentativa in TentativaDeEnvio.objects.values():
        assert "+55" not in " ".join(str(v) for v in tentativa.values())


def test_duas_falhas_e_depois_sucesso(
    relogio: RelogioControlado, simulador_whatsapp: CanalWhatsAppSimulado
) -> None:  # A-8
    relogio.congelar(T0)
    simulador_whatsapp.falhar_proximas(2)
    _emitir(Evento.RETIRADA_LIBERADA, _com_consentimento())
    envio = Envio.objects.get(canal="whatsapp")
    for espera in (timedelta(0), timedelta(minutes=1), timedelta(minutes=10)):
        relogio.avancar(espera)
        processar_envios()
    tentativas = TentativaDeEnvio.objects.filter(envio=envio).order_by("numero")
    assert [(t.resultado, t.erro) for t in tentativas] == [
        ("falha", "FalhaNoCanalExterno"),
        ("falha", "FalhaNoCanalExterno"),
        ("sucesso", ""),
    ]
    envio.refresh_from_db()
    assert (envio.situacao, envio.tentativas) == ("enviado", 3)
    assert len(simulador_whatsapp.mensagens) == 1


def test_obter_canal_devolve_a_implementacao_configurada(settings: Any) -> None:  # A-12
    settings.CANAL_WHATSAPP = "simulado"
    assert isinstance(obter_canal_whatsapp(), CanalWhatsAppSimulado)
    settings.CANAL_WHATSAPP = "desligado"
    assert isinstance(obter_canal_whatsapp(), CanalWhatsAppDesligado)


def test_o_processamento_nao_importa_implementacoes() -> None:  # A-12
    codigo = Path("apps/notificacoes/processamento.py").read_text(encoding="utf-8")
    assert "CanalWhatsAppSimulado" not in codigo
    assert "CanalWhatsAppDesligado" not in codigo


def test_log_sem_numero_nem_texto(
    relogio: RelogioControlado,
    simulador_whatsapp: CanalWhatsAppSimulado,
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-13
    caplog.set_level(logging.DEBUG)
    relogio.congelar(T0)
    simulador_whatsapp.falhar_proximas(1)
    _emitir(Evento.RETIRADA_LIBERADA, _com_consentimento())
    for espera in (timedelta(0), timedelta(minutes=1)):
        relogio.avancar(espera)
        processar_envios()
    assert len(simulador_whatsapp.mensagens) == 1
    for registro in caplog.records:
        texto = registro.getMessage()
        assert NUMERO not in texto
        assert "Retirada liberada" not in texto
