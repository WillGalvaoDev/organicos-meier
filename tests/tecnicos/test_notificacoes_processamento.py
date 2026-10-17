"""E04-03: processamento da fila de e-mails e retentativas (A-1 a A-5, A-7, A-8, A-12)."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.db import transaction
from django.test import Client

from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento
from apps.notificacoes.models import Envio, Notificacao, TentativaDeEnvio
from apps.notificacoes.processamento import processar_envios
from tests.apoio.email_falho import BackendComFalhas, BackendQueFalhaPara
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, EnvioFactory

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
MINUTO = timedelta(minutes=1)
DEZ_MINUTOS = timedelta(minutes=10)
BACKEND_COM_FALHAS = "tests.apoio.email_falho.BackendComFalhas"
BACKEND_QUE_FALHA = "tests.apoio.email_falho.BackendQueFalha"


class BackendComEndereco(BaseEmailBackend):
    """Levanta uma exceção cuja mensagem contém o endereço (A-8)."""

    def send_messages(self, email_messages: Any) -> int:
        raise ConnectionError(f"falha para {email_messages[0].to[0]}")


def test_envio_com_sucesso(relogio: RelogioControlado) -> None:  # A-1
    relogio.congelar(T0)
    envio = EnvioFactory.create(destino="ana@x.com", assunto="Orgânicos Méier: Estorno", corpo="C")
    assert processar_envios() == 1
    assert len(mail.outbox) == 1
    mensagem = mail.outbox[0]
    assert (mensagem.to, mensagem.subject, mensagem.body) == (
        ["ana@x.com"],
        "Orgânicos Méier: Estorno",
        "C",
    )
    envio.refresh_from_db()
    assert (envio.situacao, envio.tentativas, envio.concluido_em) == ("enviado", 1, T0)
    tentativa = TentativaDeEnvio.objects.get()
    assert (tentativa.envio_id, tentativa.numero, tentativa.resultado) == (envio.pk, 1, "sucesso")
    assert tentativa.erro == ""
    assert tentativa.iniciada_em == tentativa.concluida_em == T0


def test_duas_falhas_e_depois_sucesso(settings: Any, relogio: RelogioControlado) -> None:  # A-2
    settings.EMAIL_BACKEND = BACKEND_COM_FALHAS
    BackendComFalhas.configurar(falhas=2)
    relogio.congelar(T0)
    envio = EnvioFactory.create()
    assert processar_envios() == 1  # t0: falha
    relogio.avancar(timedelta(seconds=59))
    assert processar_envios() == 0
    relogio.avancar(timedelta(seconds=1))  # t0 + 60 s: falha
    assert processar_envios() == 1
    relogio.avancar(DEZ_MINUTOS - timedelta(seconds=1))
    assert processar_envios() == 0
    relogio.avancar(timedelta(seconds=1))  # t0 + 60 s + 10 min: sucesso
    assert processar_envios() == 1
    assert [t.iniciada_em for t in TentativaDeEnvio.objects.order_by("numero")] == [
        T0,
        T0 + MINUTO,
        T0 + MINUTO + DEZ_MINUTOS,
    ]
    assert [t.resultado for t in TentativaDeEnvio.objects.order_by("numero")] == [
        "falha",
        "falha",
        "sucesso",
    ]
    envio.refresh_from_db()
    assert (envio.situacao, envio.tentativas) == ("enviado", 3)
    assert len(mail.outbox) == 1


def test_tres_falhas_encerram_o_envio(settings: Any, relogio: RelogioControlado) -> None:  # A-3
    settings.EMAIL_BACKEND = BACKEND_QUE_FALHA
    relogio.congelar(T0)
    envio = EnvioFactory.create()
    for espera in (timedelta(0), MINUTO, DEZ_MINUTOS):
        relogio.avancar(espera)
        assert processar_envios() == 1
    tentativas = list(TentativaDeEnvio.objects.order_by("numero"))
    assert [(t.numero, t.resultado, t.erro) for t in tentativas] == [
        (1, "falha", "ConnectionError"),
        (2, "falha", "ConnectionError"),
        (3, "falha", "ConnectionError"),
    ]
    envio.refresh_from_db()
    assert (envio.situacao, envio.tentativas) == ("falhou", 3)
    assert envio.concluido_em is not None
    relogio.avancar(timedelta(days=1))
    assert processar_envios() == 0
    assert TentativaDeEnvio.objects.count() == 3


def test_falha_num_envio_nao_impede_os_seguintes(
    settings: Any, relogio: RelogioControlado
) -> None:  # A-4
    settings.EMAIL_BACKEND = "tests.apoio.email_falho.BackendQueFalhaPara"
    BackendQueFalhaPara.configurar(destinos={"a@x.com"})
    relogio.congelar(T0)
    primeiro = EnvioFactory.create(destino="a@x.com")
    outros = [EnvioFactory.create(destino=f"{n}@x.com") for n in "bc"]
    assert processar_envios() == 3
    primeiro.refresh_from_db()
    assert (primeiro.situacao, primeiro.tentativas) == ("pendente", 1)
    assert primeiro.proxima_tentativa_em == T0 + MINUTO
    for outro in outros:
        outro.refresh_from_db()
        assert outro.situacao == "enviado"
    assert len(mail.outbox) == 2


def test_limite_de_envios_por_chamada(relogio: RelogioControlado) -> None:  # A-5
    relogio.congelar(T0)
    for _ in range(5):
        EnvioFactory.create()
    assert processar_envios(limite=2) == 2
    assert Envio.objects.filter(situacao="pendente", tentativas=0).count() == 3
    assert len(mail.outbox) == 2


def test_envio_agendado_para_o_futuro_nao_e_tentado(
    settings: Any, relogio: RelogioControlado
) -> None:  # A-12
    settings.EMAIL_BACKEND = BACKEND_COM_FALHAS
    BackendComFalhas.configurar(falhas=0)
    relogio.congelar(T0)
    EnvioFactory.create(proxima_tentativa_em=T0 + MINUTO)
    assert processar_envios() == 0
    assert BackendComFalhas.chamadas == 0
    assert TentativaDeEnvio.objects.count() == 0


def test_falha_do_email_nao_altera_a_notificacao(
    settings: Any, relogio: RelogioControlado
) -> None:  # A-7, cenário 24 (e-mail)
    settings.EMAIL_BACKEND = BACKEND_QUE_FALHA
    relogio.congelar(T0)
    conta = ContaFactory.create()
    with transaction.atomic():
        emitir_evento(
            Evento.ESTORNO, conta, titulo="Estorno", corpo="R$ 10,00", link=None, chave="e:1"
        )
    antes = Notificacao.objects.filter().values().get()
    for espera in (timedelta(0), MINUTO, DEZ_MINUTOS):
        relogio.avancar(espera)
        processar_envios()
    assert Envio.objects.get().situacao == "falhou"
    assert Notificacao.objects.filter().values().get() == antes
    cliente = Client()
    cliente.force_login(conta)
    pagina = cliente.get("/notificacoes/").content.decode()
    assert "Estorno" in pagina
    assert "R$ 10,00" in pagina
    assert "Nova" in pagina


def test_log_de_falha_sem_dados_pessoais(
    settings: Any, relogio: RelogioControlado, caplog: pytest.LogCaptureFixture
) -> None:  # A-8
    settings.EMAIL_BACKEND = "tests.tecnicos.test_notificacoes_processamento.BackendComEndereco"
    caplog.set_level(logging.DEBUG)
    relogio.congelar(T0)
    envio = EnvioFactory.create(destino="ana@x.com", assunto="Orgânicos Méier: Estorno")
    for espera in (timedelta(0), MINUTO, DEZ_MINUTOS):
        relogio.avancar(espera)
        processar_envios()
    niveis = [r.levelname for r in caplog.records if r.name.startswith("apps.notificacoes")]
    assert niveis.count("WARNING") == 2
    assert niveis.count("ERROR") == 1
    for registro in caplog.records:
        texto = registro.getMessage()
        assert "ana@x.com" not in texto
        assert "Estorno" not in texto
    mensagens = " ".join(r.getMessage() for r in caplog.records)
    assert f"envio={envio.pk}" in mensagens
    assert "ConnectionError" in mensagens
    assert {t.erro for t in TentativaDeEnvio.objects.all()} == {"ConnectionError"}
