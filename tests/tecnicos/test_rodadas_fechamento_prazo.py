"""E06-03: bloqueio pelo prazo nas ações (acceptance A-1 a A-7)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django.db import transaction
from django.test import Client

from apps.catalogo.models import Produto
from apps.contas.models import Conta
from apps.contas.moderacao import suspender
from apps.interesses.consultas import total_reservado
from apps.interesses.fila import alocar_pendentes
from apps.interesses.servicos import (
    adicionar_interesse,
    definir_interesse,
    interesse_do_comprador,
    reduzir_interesse,
    remover_pendente,
)
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.tempo import agora
from apps.rodadas.condicoes import MENSAGEM_INTERESSES, InteressesBloqueados, aceita_interesses
from apps.rodadas.fechamento import iniciar_fechamento
from apps.rodadas.models import Etapa, Rodada
from tests.apoio.interesses import auditorias, cenario, pendente, reservada
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
T0 = datetime(2026, 11, 2, 13, 30, tzinfo=UTC)
T = datetime(2026, 11, 3, 13, 30, tzinfo=UTC)  # prazo do fechamento iniciado em T0
MS = timedelta(milliseconds=1)


def admin() -> Conta:
    return Conta.objects.get(papel="administrador")


def em_fechamento(relogio: RelogioControlado) -> tuple[Rodada, Produto, Conta]:
    """Rodada de F em fechamento por `iniciar_fechamento` às T0; A com 10 reservados."""
    relogio.congelar(T0)
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    a = ContaFactory.create()
    reservada(a, produto, 10)
    iniciar_fechamento(admin(), rodada)
    return rodada, produto, a


def total_de_auditorias() -> int:
    return EntradaAuditoria.objects.filter(acao__startswith="interesse.").count()


@pytest.mark.acceptance
def test_a_fronteira_do_prazo_e_exclusiva(relogio: RelogioControlado) -> None:
    # A-1, §15 validar prazo nas ações
    rodada, produto, _ = em_fechamento(relogio)
    b = ContaFactory.create()
    relogio.congelar(T - MS)
    assert adicionar_interesse(b, produto, "1").reservado == D("1")
    for instante in (T, T + MS):
        relogio.congelar(instante)
        with pytest.raises(InteressesBloqueados) as erro:
            adicionar_interesse(b, produto, "1")
        assert erro.value.codigo == "prazo_encerrado"
        assert str(erro.value) == MENSAGEM_INTERESSES
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO


def test_depois_do_prazo_o_comprador_nao_altera_nada(relogio: RelogioControlado) -> None:  # A-2
    _, produto, a = em_fechamento(relogio)
    relogio.congelar(T + timedelta(minutes=1))
    antes = total_de_auditorias()
    for acao in (
        lambda: reduzir_interesse(a, produto, "1"),
        lambda: definir_interesse(a, produto, "5"),
        lambda: definir_interesse(a, produto, "0"),
    ):
        with pytest.raises(InteressesBloqueados) as erro:
            acao()
        assert erro.value.codigo == "prazo_encerrado"
    assert interesse_do_comprador(a, produto).reservado == D("10")
    assert total_de_auditorias() == antes


def test_depois_do_prazo_a_fila_nao_e_atendida(relogio: RelogioControlado) -> None:  # A-3
    rodada, produto, _ = em_fechamento(relogio)
    c = ContaFactory.create()
    espera = pendente(c, produto, 3)
    relogio.congelar(T + timedelta(minutes=1))
    with transaction.atomic():
        assert alocar_pendentes(rodada.fornecedor) == 0
    espera.refresh_from_db()
    assert (espera.situacao, espera.quantidade_pendente) == ("pendente", D("3"))
    assert auditorias("interesse.alocar_pendentes") == []


def test_depois_do_prazo_remover_pendente_e_suspender_continuam(
    relogio: RelogioControlado,
) -> None:  # A-4
    _, produto, a = em_fechamento(relogio)
    pendente(a, produto, 2)
    c = ContaFactory.create()
    espera = pendente(c, produto, 3)
    relogio.congelar(T + timedelta(minutes=1))
    assert remover_pendente(a, produto, "2").pendente == 0
    suspender(admin(), a)
    assert total_reservado(produto) == 0
    espera.refresh_from_db()
    assert (espera.situacao, espera.quantidade_pendente) == ("pendente", D("3"))


def test_depois_do_prazo_as_telas_nao_oferecem_quantidade(relogio: RelogioControlado) -> None:
    # A-5
    rodada, produto, a = em_fechamento(relogio)
    pendente(a, produto, 2)
    relogio.congelar(T + timedelta(minutes=1))
    cliente = Client()
    cliente.force_login(a)
    for url in ("/carrinho/", f"/catalogo/{rodada.fornecedor_id}/"):
        html = cliente.get(url).content.decode()
        assert 'action="/interesses/"' not in html, url
    assert 'action="/interesses/pendentes/remover/"' in cliente.get("/carrinho/").content.decode()
    resposta = cliente.post("/interesses/", {"produto": produto.pk, "quantidade": "5"})
    assert resposta.status_code == 409
    assert MENSAGEM_INTERESSES in resposta.content.decode()


def test_fechamento_sem_prazo_e_erro_de_invariante() -> None:  # A-6
    rodada, _, _ = cenario("20", etapa=Etapa.INTERESSE)
    Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.FECHAMENTO)
    rodada.refresh_from_db()
    with pytest.raises(RuntimeError):
        aceita_interesses(rodada, agora())


def test_aceita_interesses_por_etapa() -> None:  # A-7
    assert aceita_interesses(Rodada(etapa=Etapa.INTERESSE), T0) is True
    assert aceita_interesses(Rodada(etapa=Etapa.INTERESSE), T + timedelta(days=400)) is True
    for etapa in (Etapa.FECHAMENTO_ENCERRADO, Etapa.PAGAMENTO, Etapa.AGUARDANDO_FORNECEDOR):
        assert aceita_interesses(Rodada(etapa=etapa), T0) is False
