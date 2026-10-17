"""E04-02: emissão de eventos e fila de envios (acceptance A-1 a A-6, A-8 a A-11 e A-14)."""

import logging
from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError
from django.test.utils import CaptureQueriesContext

from apps.notificacoes.emissao import (
    ChaveDeEventoReutilizada,
    emitir_evento,
    emitir_evento_para_varios,
)
from apps.notificacoes.eventos import Evento
from apps.notificacoes.models import Envio, Notificacao, SituacaoEnvio
from apps.notificacoes.servicos import NotificacaoInvalida
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

RODAPE = (
    "Você recebeu este aviso porque tem conta no Orgânicos Méier. "
    "As notificações também ficam no seu perfil do site."
)
INSTANTE = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def _estorno(conta: Any, **extra: Any) -> Notificacao:
    dados: dict[str, Any] = {
        "titulo": "Estorno",
        "corpo": "R$ 10,00",
        "link": "/historico/",
        "chave": "estorno:1:7",
    }
    dados.update(extra)
    with transaction.atomic():
        return emitir_evento(Evento.ESTORNO, conta, **dados)


def test_emitir_cria_a_notificacao_e_o_envio_de_email(
    settings: Any, relogio: RelogioControlado
) -> None:  # A-1
    settings.ORIGEM_PUBLICA = "https://om.test"
    relogio.congelar(INSTANTE)
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    notificacao = _estorno(conta)
    assert Notificacao.objects.count() == 1
    envio = Envio.objects.get()
    assert envio.notificacao_id == notificacao.pk
    assert envio.conta_id == conta.pk
    assert envio.canal == "email"
    assert envio.tipo == "estorno"
    assert envio.situacao == SituacaoEnvio.PENDENTE
    assert envio.destino == "ana@x.com"
    assert envio.assunto == "Orgânicos Méier: Estorno"
    assert envio.corpo == "R$ 10,00\n\nAcesse: https://om.test/historico/\n\n" + RODAPE
    assert envio.tentativas == 0
    assert envio.criado_em == INSTANTE
    assert envio.proxima_tentativa_em == envio.criado_em
    assert envio.concluido_em is None
    assert envio.chave == "estorno:1:7:email"


def test_corpo_sem_link_nao_tem_linha_de_acesso(settings: Any) -> None:  # A-1
    settings.ORIGEM_PUBLICA = "https://om.test/"
    conta = ContaFactory.create()
    _estorno(conta, link=None)
    assert Envio.objects.get().corpo == "R$ 10,00\n\n" + RODAPE


def test_assunto_e_cortado_em_150_caracteres() -> None:  # A-1
    conta = ContaFactory.create()
    _estorno(conta, titulo="t" * 150)
    assunto = Envio.objects.get().assunto
    assert len(assunto) == 150
    assert assunto.startswith("Orgânicos Méier: ttt")


def test_evento_so_de_site_nao_cria_envio() -> None:  # A-2
    conta = ContaFactory.create()
    with transaction.atomic():
        emitir_evento(Evento.PRECO_ALTERADO, conta, titulo="Preço", corpo="c", chave="p:1")
    assert Notificacao.objects.count() == 1
    assert Envio.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_emitir_fora_de_transacao_e_recusado() -> None:  # A-3
    conta = ContaFactory.create()
    with pytest.raises(TransactionManagementError):
        emitir_evento(Evento.ESTORNO, conta, titulo="t", corpo="c", chave="k")
    assert Notificacao.objects.count() == 0
    assert Envio.objects.count() == 0


def _emitir_e_falhar(conta: Any) -> None:
    with transaction.atomic():
        emitir_evento(Evento.ESTORNO, conta, titulo="t", corpo="c", chave="k")
        raise RuntimeError


def test_transacao_desfeita_nao_deixa_nada() -> None:  # A-4
    conta = ContaFactory.create()
    with pytest.raises(RuntimeError):
        _emitir_e_falhar(conta)
    assert Notificacao.objects.count() == 0
    assert Envio.objects.count() == 0


@pytest.mark.acceptance
def test_emissao_repetida_nao_duplica(settings: Any) -> None:  # A-5, cenário 17
    settings.ORIGEM_PUBLICA = "https://om.test"
    conta = ContaFactory.create()
    primeira = _estorno(conta)
    segunda = _estorno(conta)
    assert segunda.pk == primeira.pk
    assert Notificacao.objects.count() == 1
    assert Envio.objects.count() == 1


def test_chave_reutilizada_com_outro_corpo_ou_outra_conta() -> None:  # A-6
    conta, outra = ContaFactory.create(), ContaFactory.create()
    _estorno(conta)
    for ajuste in ({"corpo": "R$ 11,00"}, {"titulo": "Outro"}, {"link": "/outro/"}):
        with pytest.raises(ChaveDeEventoReutilizada):
            _estorno(conta, **ajuste)
    with pytest.raises(ChaveDeEventoReutilizada):
        _estorno(outra)
    with pytest.raises(ChaveDeEventoReutilizada), transaction.atomic():
        emitir_evento(
            Evento.PAGAMENTO_CONFIRMADO,
            conta,
            titulo="Estorno",
            corpo="R$ 10,00",
            link="/historico/",
            chave="estorno:1:7",
        )
    assert Notificacao.objects.count() == 1
    assert Envio.objects.count() == 1


def test_papel_errado_para_o_evento() -> None:  # A-8
    comprador = ContaFactory.create()
    administrador = ContaFactory.create(administrador=True)
    with pytest.raises(NotificacaoInvalida), transaction.atomic():
        emitir_evento(Evento.FALHA_NO_PEDIDO_FORMAL, comprador, titulo="t", corpo="c", chave="a")
    with pytest.raises(NotificacaoInvalida), transaction.atomic():
        emitir_evento(Evento.ESTORNO, administrador, titulo="t", corpo="c", chave="b")
    assert Notificacao.objects.count() == 0
    assert Envio.objects.count() == 0


def test_emitir_para_varios_com_conta_repetida() -> None:  # A-9
    a, b, c = (ContaFactory.create() for _ in range(3))
    with transaction.atomic():
        novas = emitir_evento_para_varios(
            Evento.COMUNICADO,
            [a, b, a, c],
            titulo="Aviso",
            corpo="Texto",
            chave_base="comunicado:5",
        )
    assert novas == 3
    assert sorted(Notificacao.objects.values_list("chave", flat=True)) == sorted(
        f"comunicado:5:{conta.pk}" for conta in (a, b, c)
    )
    assert Envio.objects.filter(canal="email").count() == 3
    with transaction.atomic():
        repetida = emitir_evento_para_varios(
            Evento.COMUNICADO, [a, b, c], titulo="Aviso", corpo="Texto", chave_base="comunicado:5"
        )
    assert repetida == 0
    assert Notificacao.objects.count() == 3
    assert Envio.objects.count() == 3


def test_emitir_para_varios_tem_numero_fixo_de_consultas() -> None:  # A-10
    contagens = []
    for n, base in ((1, "um"), (30, "trinta")):
        contas = [ContaFactory.create() for _ in range(n)]
        with CaptureQueriesContext(connection) as consultas, transaction.atomic():
            emitir_evento_para_varios(
                Evento.COMUNICADO, contas, titulo="t", corpo="c", chave_base=base
            )
        contagens.append(len(consultas))
    assert contagens[0] == contagens[1]
    assert contagens[0] <= 8


def test_lista_vazia_devolve_zero_e_nao_grava() -> None:  # A-9 (limite)
    with transaction.atomic():
        assert (
            emitir_evento_para_varios(Evento.COMUNICADO, [], titulo="t", corpo="c", chave_base="x")
            == 0
        )
    assert Notificacao.objects.count() == 0


def test_lote_com_papel_errado_nao_grava_nada() -> None:  # A-11
    a, b = ContaFactory.create(), ContaFactory.create()
    administrador = ContaFactory.create(administrador=True)
    with pytest.raises(NotificacaoInvalida), transaction.atomic():
        emitir_evento_para_varios(
            Evento.COMUNICADO, [a, b, administrador], titulo="t", corpo="c", chave_base="c:1"
        )
    assert Notificacao.objects.count() == 0
    assert Envio.objects.count() == 0


def test_lote_com_chave_reutilizada_nao_grava_nada() -> None:  # A-6 (lote)
    a, b = ContaFactory.create(), ContaFactory.create()
    with transaction.atomic():
        emitir_evento_para_varios(Evento.COMUNICADO, [a], titulo="t", corpo="c", chave_base="c:1")
    with pytest.raises(ChaveDeEventoReutilizada), transaction.atomic():
        emitir_evento_para_varios(
            Evento.COMUNICADO, [a, b], titulo="outro", corpo="c", chave_base="c:1"
        )
    assert Notificacao.objects.count() == 1
    assert Envio.objects.count() == 1


def test_emissao_nao_registra_dados_pessoais_em_log(
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-14
    caplog.set_level(logging.DEBUG)
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    _estorno(conta, link=None)
    with pytest.raises(NotificacaoInvalida), transaction.atomic():
        emitir_evento(Evento.ESTORNO, conta, titulo="Estorno", corpo="R$ 10,00", chave="")
    with pytest.raises(ChaveDeEventoReutilizada):
        _estorno(conta, link=None, corpo="R$ 99,00")
    for registro in caplog.records:
        texto = registro.getMessage()
        assert "ana@x.com" not in texto
        assert "Estorno" not in texto
        assert "R$ 10,00" not in texto
