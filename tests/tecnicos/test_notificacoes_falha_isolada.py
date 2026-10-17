"""E04-04: a falha do canal externo fica isolada (cenário 24; acceptance A-9 e A-10)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import transaction
from django.test import Client

from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento
from apps.notificacoes.models import Envio, Notificacao, TentativaDeEnvio
from apps.notificacoes.processamento import processar_envios
from apps.notificacoes.whatsapp import CanalWhatsAppSimulado
from apps.nucleo.tempo import agora
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.models import ModeloContador
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

T0 = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
NUMERO = "+5521999990000"


def _comprador() -> Any:
    return ContaFactory.create(telefone=NUMERO, whatsapp_consentido_em=agora())


@pytest.mark.acceptance
@pytest.mark.django_db
def test_falha_no_whatsapp_nao_desfaz_o_fato_nem_a_notificacao(
    relogio: RelogioControlado, simulador_whatsapp: CanalWhatsAppSimulado
) -> None:  # cenário 24
    relogio.congelar(T0)
    simulador_whatsapp.falhar_sempre()
    conta = _comprador()
    with transaction.atomic():
        fato = ModeloContador.objects.create(valor=7)  # o "pagamento" do teste
        emitir_evento(
            Evento.PAGAMENTO_ABERTO,
            conta,
            titulo="Pagamento aberto",
            corpo="Pague em 24 horas.",
            chave="pagamento_aberto:1",
        )
    emitida = list(Notificacao.objects.order_by("pk").values())
    for espera in (timedelta(0), timedelta(minutes=1), timedelta(minutes=10)):
        relogio.avancar(espera)
        processar_envios()  # nenhuma exceção chega aqui
    whatsapp = Envio.objects.get(canal="whatsapp")
    assert (whatsapp.situacao, whatsapp.tentativas) == ("falhou", 3)
    assert TentativaDeEnvio.objects.filter(envio=whatsapp).count() == 3
    assert {e.situacao for e in Envio.objects.filter(canal="email")} == {"enviado"}
    fato.refresh_from_db()
    assert fato.valor == 7
    assert list(Notificacao.objects.order_by("pk").values()) == emitida
    cliente = Client()
    cliente.force_login(conta)
    pagina = cliente.get("/notificacoes/").content.decode()
    assert "Pagamento aberto" in pagina
    assert "Pague em 24 horas." in pagina


@pytest.mark.acceptance
@pytest.mark.django_db(transaction=True)
def test_nada_e_tentado_antes_da_confirmacao_da_transacao(
    simulador_whatsapp: CanalWhatsAppSimulado,
) -> None:  # cenário 24, infra 7
    simulador_whatsapp.falhar_sempre()
    conta = _comprador()

    def emissora(barreira: Any) -> None:
        with transaction.atomic():
            emitir_evento(
                Evento.PAGAMENTO_ABERTO, conta, titulo="t", corpo="c", chave="pagamento_aberto:1"
            )
            barreira.wait(timeout=10)  # a outra conexão processa com a transação aberta
            barreira.wait(timeout=30)

    def processadora(barreira: Any) -> int:
        barreira.wait(timeout=10)
        feitas = processar_envios()
        barreira.wait(timeout=30)
        return feitas

    resultados = executar_em_paralelo(emissora, processadora)
    assert resultados[0].excecao is None, resultados[0].excecao
    assert resultados[1].excecao is None, resultados[1].excecao
    assert resultados[1].valor == 0
    assert TentativaDeEnvio.objects.count() == 0
    assert processar_envios() == 2  # e-mail e WhatsApp, agora confirmados
    assert Envio.objects.get(canal="whatsapp").tentativas == 1


@pytest.mark.django_db(transaction=True)
def test_falha_whatsapp_preserva_fato_emitido_na_mesma_transacao() -> None:
    # probe do revisor de 0b52010 (corpo original)
    from datetime import UTC, datetime, timedelta

    import time_machine

    from apps.notificacoes.whatsapp import SIMULADOR
    from apps.nucleo.tempo import agora
    from tests.apoio.models import ModeloContador

    SIMULADOR.reiniciar()
    SIMULADOR.falhar_sempre()
    try:
        with time_machine.travel(datetime(2026, 10, 17, 15, tzinfo=UTC), tick=False) as relogio:
            conta = ContaFactory.create(telefone="+5521999990000", whatsapp_consentido_em=agora())
            with transaction.atomic():
                fato = ModeloContador.objects.create(valor=7)
                n = emitir_evento(
                    Evento.PAGAMENTO_ABERTO, conta, titulo="Aberto", corpo="c", chave="fato:1"
                )
            for minutos in (0, 1, 10):
                relogio.shift(timedelta(minutes=minutos))
                processar_envios()
            fato.refresh_from_db()
            assert fato.valor == 7
            assert Notificacao.objects.get(pk=n.pk).corpo == "c"
            e = Envio.objects.get(canal="whatsapp")
            assert (e.situacao, e.tentativas) == ("falhou", 3)
            assert Envio.objects.get(canal="email").situacao == "enviado"
    finally:
        SIMULADOR.reiniciar()
