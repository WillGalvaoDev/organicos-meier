"""E09-03: alertas financeiros (acceptance A-1 a A-9, A-11 e A-12)."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError

from apps.contas.models import Conta, Papel
from apps.financeiro.alertas import (
    abrir_alerta,
    alertas_abertos,
    resolver_alerta,
)
from apps.financeiro.models import AlertaFinanceiro, Gravidade, TipoDeAlerta
from apps.notificacoes.eventos import CANAIS_POR_EVENTO, DESTINATARIO_POR_EVENTO, Canal, Evento
from apps.notificacoes.models import Envio, Notificacao, TentativaDeEnvio
from apps.notificacoes.processamento import processar_envios
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)
LOG = "apps.financeiro.alertas"
TITULO_CRITICO = "Alerta crítico: saldo do provedor abaixo das obrigações"
BACKEND_QUE_FALHA = "tests.apoio.email_falho.BackendQueFalha"
RESERVA = TipoDeAlerta.RESERVA_INSUFICIENTE.value


@pytest.fixture
def admin() -> Conta:
    return ContaFactory.create(administrador=True)


@pytest.fixture
def comprador() -> Conta:
    return ContaFactory.create()


def _notificacoes(conta: Conta) -> list[Notificacao]:
    return list(Notificacao.objects.filter(conta=conta, evento="alerta_financeiro").order_by("pk"))


def _unica(conta: Conta) -> Notificacao:
    notificacoes = _notificacoes(conta)
    assert len(notificacoes) == 1, f"notificações do alerta: {len(notificacoes)}"
    return notificacoes[0]


def _abrir(tipo: str = RESERVA, chave: str = "geral", **dados: Any) -> AlertaFinanceiro:
    with transaction.atomic():
        return abrir_alerta(tipo, chave, dados or {"sem_cobertura": "50.00", "livre": "20.00"})


def test_abrir_o_alerta_avisa_so_o_administrador(
    admin: Conta, comprador: Conta, caplog: pytest.LogCaptureFixture
) -> None:  # A-1
    caplog.set_level(logging.INFO, logger=LOG)
    alerta = _abrir()
    assert alerta.gravidade == Gravidade.AVISO
    assert alerta.resolvido_em is None
    assert alerta.dados == {"sem_cobertura": "50.00", "livre": "20.00"}
    notificacao = _unica(admin)
    assert notificacao.titulo == "Reserva insuficiente"
    assert "R$ 50,00" in notificacao.corpo
    assert "R$ 20,00" in notificacao.corpo
    assert notificacao.link == "/administracao/financeiro/"  # E09-08: a tela financeira
    assert notificacao.chave == f"alerta_financeiro:{alerta.pk}:{admin.pk}"
    (envio,) = Envio.objects.filter(notificacao=notificacao)
    assert (envio.canal, envio.destino) == ("email", admin.email_normalizado)
    assert _notificacoes(comprador) == []
    avisos = [r for r in caplog.records if r.name == LOG and r.levelno == logging.WARNING]
    assert len(avisos) == 1
    assert RESERVA in avisos[0].getMessage()
    assert "geral" in avisos[0].getMessage()


def test_abrir_de_novo_devolve_o_existente_sem_novo_aviso(admin: Conta) -> None:  # A-2
    primeiro = _abrir()
    segundo = _abrir(sem_cobertura="99.00", livre="1.00")
    assert segundo.pk == primeiro.pk
    assert segundo.dados == {"sem_cobertura": "50.00", "livre": "20.00"}
    assert AlertaFinanceiro.objects.count() == 1
    assert len(_notificacoes(admin)) == 1


def test_depois_de_resolvido_a_mesma_situacao_abre_outro_alerta(
    admin: Conta, relogio: RelogioControlado
) -> None:  # A-3
    relogio.congelar(T0)
    primeiro = _abrir()
    relogio.congelar(T0 + timedelta(hours=1))
    with transaction.atomic():
        resolvido = resolver_alerta(RESERVA, "geral", motivo="cobertura")
    assert resolvido is not None
    assert resolvido.pk == primeiro.pk
    primeiro.refresh_from_db()
    assert primeiro.resolvido_em == T0 + timedelta(hours=1)
    assert primeiro.motivo_da_resolucao == "cobertura"
    segundo = _abrir()
    assert segundo.pk != primeiro.pk
    assert AlertaFinanceiro.objects.count() == 2
    assert len(_notificacoes(admin)) == 2  # a resolução não avisa; a nova abertura, sim


def test_resolver_sem_alerta_aberto_devolve_none() -> None:  # A-4
    with transaction.atomic():
        assert resolver_alerta(RESERVA, "geral", motivo="cobertura") is None
    assert AlertaFinanceiro.objects.count() == 0


def test_o_alerta_critico_tem_titulo_corpo_e_log_de_erro(
    admin: Conta, caplog: pytest.LogCaptureFixture
) -> None:  # A-5
    caplog.set_level(logging.INFO, logger=LOG)
    alerta = _abrir("invariante_violado", "geral", diferenca="-10.00")
    assert alerta.gravidade == Gravidade.CRITICO
    notificacao = _unica(admin)
    assert notificacao.titulo == TITULO_CRITICO
    assert "R$ 10,00" in notificacao.corpo
    assert "Utilizações da reserva e retiradas de receita estão bloqueadas." in notificacao.corpo
    assert [r.levelno for r in caplog.records if r.name == LOG] == [logging.ERROR]


@pytest.mark.parametrize(
    ("tipo", "dados", "titulo", "trechos"),
    [
        (
            "pagamento_sem_conciliacao",
            {"id_externo": "sim-7", "valor": "45.90"},
            "Pagamento sem conciliação",
            ["sim-7", "R$ 45,90"],
        ),
        (
            "divergencia_na_conciliacao",
            {"data": "2026-11-02", "diferenca": "3.10"},
            "Divergência na conciliação diária",
            ["2026-11-02", "R$ 3,10"],
        ),
        (
            "divergencia_na_conciliacao",
            {"data": "2026-11-02", "id_movimento": "mov-9"},
            "Divergência na conciliação diária",
            ["2026-11-02", "mov-9"],
        ),
        (
            "aprovado_apos_a_margem",
            {"pedido": 12, "valor": "94.35"},
            "Pagamento aprovado depois da margem",
            ["12", "R$ 94,35", "gerou obrigação de devolução integral"],
        ),
        (
            "duplicidade",
            {"pedido": 12, "valor": "94.35"},
            "Pagamento em duplicidade",
            ["12", "R$ 94,35", "gerou obrigação de devolução integral"],
        ),
    ],
)
def test_titulo_e_corpo_de_cada_tipo(
    admin: Conta, tipo: str, dados: dict[str, Any], titulo: str, trechos: list[str]
) -> None:  # A-5
    _abrir(tipo, "k", **dados)
    notificacao = _unica(admin)
    assert notificacao.titulo == titulo
    for trecho in trechos:
        assert trecho in notificacao.corpo


@pytest.mark.parametrize(
    ("tipo", "chave", "dados"),
    [
        ("tipo_inexistente", "geral", {}),
        (RESERVA, "", {}),
        (RESERVA, "c" * 65, {}),
        (RESERVA, "geral", {"token": "x"}),
    ],
    ids=["tipo", "chave_vazia", "chave_longa", "segredo"],
)
def test_entradas_invalidas_sao_recusadas(
    admin: Conta, tipo: str, chave: str, dados: dict[str, Any]
) -> None:  # A-6
    with pytest.raises(ValueError):  # noqa: PT011
        with transaction.atomic():
            abrir_alerta(tipo, chave, dados)
    assert AlertaFinanceiro.objects.count() == 0
    assert Notificacao.objects.count() == 0


def test_email_que_falha_nao_desfaz_o_alerta(
    admin: Conta, settings: Any, relogio: RelogioControlado
) -> None:  # A-7, §12
    settings.EMAIL_BACKEND = BACKEND_QUE_FALHA
    relogio.congelar(T0)
    alerta = _abrir()
    assert processar_envios() == 1
    alerta.refresh_from_db()
    assert alerta.resolvido_em is None
    assert len(_notificacoes(admin)) == 1
    assert [t.resultado for t in TentativaDeEnvio.objects.all()] == ["falha"]
    (envio,) = Envio.objects.all()
    assert envio.situacao != "enviado"


def test_alertas_abertos_pondo_o_critico_primeiro(admin: Conta, relogio: RelogioControlado) -> None:
    relogio.congelar(T0)  # A-8
    primeiro = _abrir(RESERVA)
    relogio.congelar(T0 + timedelta(minutes=1))
    segundo = _abrir(
        "divergencia_na_conciliacao", "2026-11-02", data="2026-11-02", diferenca="1.00"
    )
    relogio.congelar(T0 + timedelta(minutes=2))
    critico = _abrir("invariante_violado", "geral", diferenca="-5.00")
    assert [a.pk for a in alertas_abertos()] == [critico.pk, primeiro.pk, segundo.pk]
    assert [a.pk for a in alertas_abertos(RESERVA)] == [primeiro.pk]
    with transaction.atomic():
        resolver_alerta(RESERVA, "geral", motivo="cobertura")
    assert [a.pk for a in alertas_abertos()] == [critico.pk, segundo.pk]


def test_transacao_desfeita_nao_deixa_alerta_nem_aviso(admin: Conta) -> None:  # A-9
    with pytest.raises(RuntimeError):  # noqa: PT012
        with transaction.atomic():
            abrir_alerta(RESERVA, "geral", {"sem_cobertura": "1.00", "livre": "0.00"})
            raise RuntimeError("falha depois de abrir")
    assert AlertaFinanceiro.objects.count() == 0
    assert Notificacao.objects.count() == 0
    assert Envio.objects.count() == 0


def test_o_catalogo_do_evento_novo() -> None:  # A-11
    evento = Evento("alerta_financeiro")
    assert CANAIS_POR_EVENTO[evento] == frozenset({Canal.SITE, Canal.EMAIL})
    assert DESTINATARIO_POR_EVENTO[evento] == Papel.ADMINISTRADOR
    comprador = {e for e, papel in DESTINATARIO_POR_EVENTO.items() if papel == Papel.COMPRADOR}
    assert len(comprador) == 12
    assert {e for e, p in DESTINATARIO_POR_EVENTO.items() if p == Papel.ADMINISTRADOR} == {
        Evento.FALHA_NO_PEDIDO_FORMAL,
        evento,
    }


def test_sem_administrador_o_alerta_e_gravado_sem_aviso(
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-12
    caplog.set_level(logging.INFO, logger=LOG)
    assert not Conta.objects.filter(papel=Papel.ADMINISTRADOR).exists()
    alerta = _abrir()
    assert alerta.resolvido_em is None
    assert Notificacao.objects.count() == 0
    assert any("nenhum administrador" in r.getMessage() for r in caplog.records if r.name == LOG)


@pytest.mark.django_db(transaction=True)
def test_abrir_e_resolver_exigem_transacao(admin: Conta) -> None:
    assert not connection.in_atomic_block
    with pytest.raises(TransactionManagementError):
        abrir_alerta(RESERVA, "geral", {"sem_cobertura": "1.00", "livre": "0.00"})
    with pytest.raises(TransactionManagementError):
        resolver_alerta(RESERVA, "geral", motivo="cobertura")
    assert AlertaFinanceiro.objects.count() == 0
