"""E03-02: abertura de rodada (acceptance A-1 a A-4, A-6, A-7 e A-16)."""

from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import Client
from django.utils import timezone

from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.condicoes import travar_condicoes
from apps.rodadas.models import ETAPAS_ATIVAS, Etapa, Rodada
from apps.rodadas.servicos import RodadaAtivaExistente, abrir_rodada
from apps.rodadas.sinais import rodada_aberta
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, FornecedorFactory, RodadaFactory

pytestmark = pytest.mark.django_db

MENSAGEM = "Este fornecedor já tem uma rodada ativa."


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def test_abertura_cria_rodada_em_interesse_e_audita(admin_client: Client) -> None:  # A-1
    fornecedor = FornecedorFactory.create()
    antes = timezone.now()
    resposta = admin_client.post(f"/administracao/fornecedores/{fornecedor.pk}/rodadas/abrir/")
    assert resposta.status_code == 302
    assert resposta["Location"] == f"/administracao/fornecedores/{fornecedor.pk}/"
    rodada = Rodada.objects.get()
    assert rodada.fornecedor_id == fornecedor.pk
    assert rodada.etapa == Etapa.INTERESSE
    assert rodada.aberta_em >= antes
    assert rodada.aberta_por.papel == "administrador"
    entrada = EntradaAuditoria.objects.get(acao="rodada.abrir")
    assert entrada.alteracoes == {"rodada": rodada.pk, "fornecedor": fornecedor.pk}
    detalhe = admin_client.get(resposta["Location"]).content.decode()
    assert "Interesse" in detalhe
    assert "Sem rodada ativa" not in detalhe


@pytest.mark.parametrize("etapa", ETAPAS_ATIVAS)
def test_recusa_quando_ja_ha_rodada_ativa(etapa: Etapa) -> None:  # A-2
    admin = ContaFactory.create(administrador=True)
    rodada = RodadaFactory.create(etapa=etapa)
    with pytest.raises(RodadaAtivaExistente, match=MENSAGEM):
        abrir_rodada(admin, rodada.fornecedor)
    assert Rodada.objects.filter(fornecedor=rodada.fornecedor).count() == 1
    assert EntradaAuditoria.objects.count() == 0


def test_recusa_pela_rota_mostra_a_mensagem(admin_client: Client) -> None:
    rodada = RodadaFactory.create(etapa=Etapa.PAGAMENTO)
    resposta = admin_client.post(
        f"/administracao/fornecedores/{rodada.fornecedor_id}/rodadas/abrir/", follow=True
    )
    assert MENSAGEM in resposta.content.decode()
    assert Rodada.objects.count() == 1


@pytest.mark.parametrize("etapa", [Etapa.DISPONIVEL_PARA_RETIRADA, Etapa.CANCELADA])
def test_abre_quando_a_ultima_rodada_terminou(etapa: Etapa) -> None:  # A-3
    admin = ContaFactory.create(administrador=True)
    antiga = RodadaFactory.create(etapa=etapa)
    nova = abrir_rodada(admin, antiga.fornecedor)
    assert nova.pk is not None
    assert nova.pk != antiga.pk
    assert Rodada.objects.filter(fornecedor=antiga.fornecedor).count() == 2
    assert nova.etapa == Etapa.INTERESSE
    antiga.refresh_from_db()
    assert antiga.etapa == etapa


def test_banco_recusa_segunda_rodada_ativa() -> None:  # A-4
    rodada = RodadaFactory.create(etapa=Etapa.FECHAMENTO)
    sql = (
        "INSERT INTO rodadas_rodada (fornecedor_id, etapa, aberta_em, aberta_por_id) "
        "VALUES (%s, 'interesse', now(), %s)"
    )
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, [rodada.fornecedor_id, rodada.aberta_por_id])
    assert Rodada.objects.count() == 1


def test_receptor_que_falha_desfaz_a_abertura() -> None:  # A-6
    admin = ContaFactory.create(administrador=True)
    fornecedor = FornecedorFactory.create()

    def receptor(sender: Any, **kwargs: Any) -> None:
        raise RuntimeError("falha do receptor")

    rodada_aberta.connect(receptor, weak=False)
    try:
        with pytest.raises(RuntimeError):
            abrir_rodada(admin, fornecedor)
    finally:
        rodada_aberta.disconnect(receptor)
    assert Rodada.objects.count() == 0
    assert EntradaAuditoria.objects.count() == 0


def test_receptor_e_chamado_uma_vez_dentro_da_transacao() -> None:  # A-7
    admin = ContaFactory.create(administrador=True)
    fornecedor = FornecedorFactory.create()
    chamadas: list[tuple[Any, bool]] = []

    def receptor(sender: Any, rodada: Rodada, **kwargs: Any) -> None:
        chamadas.append((rodada, connection.in_atomic_block))

    rodada_aberta.connect(receptor, weak=False)
    try:
        criada = abrir_rodada(admin, fornecedor)
    finally:
        rodada_aberta.disconnect(receptor)
    assert len(chamadas) == 1
    assert chamadas[0][0].pk == criada.pk
    assert chamadas[0][1] is True


@pytest.mark.django_db(transaction=True)
def test_travar_condicoes_fora_de_transacao_falha() -> None:  # A-16
    fornecedor = FornecedorFactory.create()
    RodadaFactory.create(fornecedor=fornecedor)
    assert not connection.in_atomic_block
    with pytest.raises(transaction.TransactionManagementError):
        travar_condicoes(fornecedor)
