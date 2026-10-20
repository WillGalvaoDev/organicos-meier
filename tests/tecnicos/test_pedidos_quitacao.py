"""E08-04: quitação e destino dos pagamentos aprovados (acceptance A-1 a A-15)."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import DatabaseError, connection, transaction
from django.test import Client

from apps.contas.models import Conta
from apps.notificacoes.models import Envio, Notificacao
from apps.notificacoes.processamento import processar_envios
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.consulta import consultar_antes_de_decidir
from apps.pagamentos.models import PagamentoNoProvedor
from apps.pagamentos.provedor import (
    NovaCobranca,
    PagamentoConsultado,
    SituacaoNoProvedor,
    obter_provedor,
)
from apps.pagamentos.sinais import situacao_do_pagamento_mudou
from apps.pagamentos.sincronizacao import sincronizar_pagamento
from apps.pedidos.models import DestinoDoPagamento, Pedido, SituacaoDoPedido
from apps.pedidos.quitacao import ler_referencia
from tests.apoio.pedidos import (
    T0,
    Arranjo,
    cancelar_direto,
    pedido_aberto,
    pedido_avulso,
    sincronizar,
    tentativa_criada,
)
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)
MS = timedelta(milliseconds=1)


@dataclass
class Cenario:
    arranjo: Arranjo
    x: Pedido
    sim: Any
    p: str  # a cobrança simulada pendente da tentativa de A (criada às 14:00)


@pytest.fixture
def cenario(relogio: RelogioControlado, simulador_pagamentos: Any) -> Cenario:
    arranjo, x = pedido_aberto(relogio)
    tentativa = tentativa_criada(x)
    assert tentativa.id_externo is not None
    return Cenario(arranjo, x, simulador_pagamentos, tentativa.id_externo)


def _situacao(pedido: Pedido) -> SituacaoDoPedido:
    return SituacaoDoPedido.objects.get(pedido=pedido)


def _destino(id_externo: str) -> DestinoDoPagamento:
    destinos: list[DestinoDoPagamento] = list(
        DestinoDoPagamento.objects.filter(pagamento__id_externo=id_externo)
    )
    assert len(destinos) == 1, f"destinos de {id_externo}: {len(destinos)}"
    return destinos[0]


def _avisos(conta: Conta) -> list[Notificacao]:
    return list(
        Notificacao.objects.filter(conta=conta, evento="pagamento_confirmado").order_by("pk")
    )


def _entregar_e_processar(sim: Any) -> None:
    sim.entregar_avisos()
    processar_chamadas()


def _aprovar_e_receber(c: Cenario, relogio: RelogioControlado, quando: Any, chega: Any) -> None:
    """O provedor aprova em `quando`; o aviso e o processamento acontecem em `chega`."""
    relogio.congelar(chega)
    c.sim.aprovar(c.p, em=quando)
    _entregar_e_processar(c.sim)


@pytest.mark.acceptance
def test_aprovacao_no_prazo_quita_o_pedido(cenario: Cenario, relogio: RelogioControlado) -> None:
    # A-1, cenário 25 (parte)
    c = cenario
    _aprovar_e_receber(c, relogio, T0 + 2 * H, T0 + 2 * H + timedelta(minutes=1))
    destino = _destino(c.p)
    assert (destino.destino, destino.motivo, destino.pedido) == ("quita", "", c.x)
    situacao = _situacao(c.x)
    assert situacao.situacao == "pago"
    assert situacao.quitado_por is not None
    assert situacao.quitado_por.id_externo == c.p
    assert situacao.quitado_em == T0 + 2 * H
    assert (situacao.cancelado_em, situacao.motivo_do_cancelamento) == (None, "")
    (auditoria,) = EntradaAuditoria.objects.filter(acao="pedido.quitar")
    assert auditoria.autor_tipo == "sistema"
    assert auditoria.alteracoes["na_margem"] is False
    assert auditoria.alteracoes["pedido"] == c.x.pk
    assert auditoria.alteracoes["id_externo"] == c.p
    assert auditoria.alteracoes["aprovado_em"] == "2026-11-02T15:00:00+00:00"
    assert auditoria.alteracoes["cancelamento_sem_efeito"] is None
    (aviso,) = _avisos(c.arranjo.a)
    assert aviso.titulo == "Pagamento confirmado: F"
    assert aviso.corpo == (
        f"Recebemos o pagamento do seu pedido {c.x.pk} da rodada de F, no valor de R$ 94,35. "
        "O pedido está pago."
    )
    assert aviso.link == f"/pedidos/{c.x.pk}/"
    assert aviso.chave == f"pagamento_confirmado:{c.x.pk}:{c.arranjo.a.pk}"
    assert _avisos(c.arranjo.b) == []


@pytest.mark.acceptance
def test_fronteira_de_48_horas_da_margem(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-2, T-2
    pedido_aberto(relogio)
    sim = simulador_pagamentos
    pedidos = [pedido_avulso(ContaFactory.create(), f"G{i}", "50.00") for i in range(3)]
    ids = [tentativa_criada(pedido).id_externo for pedido in pedidos]
    limite = T0 + 48 * H
    relogio.congelar(limite + H)
    for id_externo, quando in zip(ids, (limite - MS, limite, limite + MS), strict=True):
        assert id_externo is not None
        sim.aprovar(id_externo, em=quando)
    _entregar_e_processar(sim)
    primeiro, segundo, terceiro = pedidos
    for pedido in (primeiro, segundo):
        assert _situacao(pedido).situacao == "pago"
    for id_externo in ids[:2]:
        assert id_externo is not None
        assert _destino(id_externo).destino == "quita"
    margens = [
        a.alteracoes["na_margem"] for a in EntradaAuditoria.objects.filter(acao="pedido.quitar")
    ]
    assert margens == [True, True]
    assert _situacao(terceiro).situacao == "aguardando_pagamento"
    assert ids[2] is not None
    tardio = _destino(ids[2])
    assert (tardio.destino, tardio.motivo) == ("devolucao", "aprovado_apos_a_margem")


@pytest.mark.acceptance
def test_aviso_atrasado_nao_muda_o_horario_de_aprovacao(
    cenario: Cenario, relogio: RelogioControlado
) -> None:  # A-3, T-3, cenário 25
    c = cenario
    aprovado = T0 + 47 * H + timedelta(minutes=59)
    _aprovar_e_receber(c, relogio, aprovado, T0 + 50 * H)
    assert _destino(c.p).destino == "quita"
    situacao = _situacao(c.x)
    assert (situacao.situacao, situacao.quitado_em) == ("pago", aprovado)
    pagamento = PagamentoNoProvedor.objects.get(id_externo=c.p)
    assert pagamento.primeiro_aviso_em == T0 + 50 * H


@pytest.mark.acceptance
def test_aprovacao_depois_da_margem_gera_devolucao(
    cenario: Cenario, relogio: RelogioControlado, caplog: pytest.LogCaptureFixture
) -> None:  # A-4, cenário 26
    c = cenario
    caplog.set_level(logging.WARNING)
    _aprovar_e_receber(c, relogio, T0 + 49 * H, T0 + 50 * H)
    destino = _destino(c.p)
    assert (destino.destino, destino.motivo, destino.pedido) == (
        "devolucao",
        "aprovado_apos_a_margem",
        c.x,
    )
    assert _situacao(c.x).situacao == "aguardando_pagamento"
    assert _avisos(c.arranjo.a) == []
    (auditoria,) = EntradaAuditoria.objects.filter(acao="pagamento.destino")
    assert auditoria.alteracoes == {
        "id_externo": c.p,
        "pedido": c.x.pk,
        "destino": "devolucao",
        "motivo": "aprovado_apos_a_margem",
    }
    avisos = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(c.p in m and "aprovado_apos_a_margem" in m for m in avisos)


def _cobranca_direta(c: Cenario, chave: str, **campos: Any) -> str:
    """Uma cobrança que o sistema não pediu, criada direto no provedor (anomalia simulada)."""
    base: dict[str, Any] = {
        "chave_idempotencia": chave,
        "referencia_externa": c.x.referencia_externa,
        "valor": c.x.total,
        "descricao": "Cobrança de apoio",
        "expira_em": T0 + 30 * H,
    }
    criada = obter_provedor().criar_cobranca(NovaCobranca(**{**base, **campos}))
    return criada.pagamento.id_externo


@pytest.mark.parametrize(
    ("criacao", "esperado"),
    [(T0 + 24 * H - MS, "quita"), (T0 + 24 * H, "devolucao")],
)
def test_iniciado_no_prazo_ou_fora_dele(
    cenario: Cenario, relogio: RelogioControlado, criacao: Any, esperado: str
) -> None:  # A-5, Infra 4.3
    c = cenario
    relogio.congelar(criacao)
    outra = _cobranca_direta(c, "anomalia-1")
    relogio.congelar(T0 + 25 * H)
    c.sim.aprovar(outra, em=T0 + 25 * H)
    sincronizar(outra)
    destino = _destino(outra)
    assert destino.destino == esperado
    if esperado == "devolucao":
        assert destino.motivo == "iniciado_fora_do_prazo"
        assert _situacao(c.x).situacao == "aguardando_pagamento"
    else:
        assert _situacao(c.x).situacao == "pago"


@pytest.mark.acceptance
@pytest.mark.parametrize("ordem", [(1, 2), (2, 1)])
def test_dois_pagamentos_aceitos_so_um_quita(
    cenario: Cenario, relogio: RelogioControlado, ordem: tuple[int, int]
) -> None:  # A-6, cenário 39
    c = cenario
    primeira = c.p
    c.sim.expirar(primeira)
    sincronizar(primeira)
    assert PagamentoNoProvedor.objects.get(id_externo=primeira).situacao == "expirado"
    relogio.congelar(T0 + 1 * H + timedelta(minutes=10))
    segunda_tentativa = tentativa_criada(c.x)
    segunda = segunda_tentativa.id_externo
    assert segunda is not None
    assert segunda != primeira
    relogio.congelar(T0 + 2 * H)
    c.sim.aprovar(primeira, em=T0 + 2 * H - timedelta(minutes=10))
    c.sim.aprovar(segunda, em=T0 + 2 * H - timedelta(minutes=5))
    por_numero = {1: primeira, 2: segunda}
    for numero in ordem:
        sincronizar(por_numero[numero])
    quem_quita = por_numero[ordem[0]]
    quem_duplica = por_numero[ordem[1]]
    assert _destino(quem_quita).destino == "quita"
    duplicado = _destino(quem_duplica)
    assert (duplicado.destino, duplicado.motivo) == ("devolucao", "duplicidade")
    assert duplicado.pagamento.valor == D("94.35")
    situacao = _situacao(c.x)
    assert situacao.situacao == "pago"
    assert situacao.quitado_por is not None
    assert situacao.quitado_por.id_externo == quem_quita
    assert len(_avisos(c.arranjo.a)) == 1
    assert EntradaAuditoria.objects.filter(acao="pedido.quitar").count() == 1
    assert DestinoDoPagamento.objects.filter(pedido=c.x, destino="quita").count() == 1


def test_sincronizar_de_novo_nao_repete_nada(cenario: Cenario, relogio: RelogioControlado) -> None:
    # A-7, Infra 4.2
    c = cenario
    _aprovar_e_receber(c, relogio, T0 + 2 * H, T0 + 2 * H + timedelta(minutes=1))
    assert _destino(c.p).destino == "quita"
    c.sim.reemitir_aviso(c.p)
    _entregar_e_processar(c.sim)
    sincronizar(c.p)
    consultar_antes_de_decidir(c.x.referencia_externa)
    assert DestinoDoPagamento.objects.count() == 1
    assert EntradaAuditoria.objects.filter(acao="pedido.quitar").count() == 1
    assert len(_avisos(c.arranjo.a)) == 1


@pytest.mark.parametrize("referencia", ["om-c999-p1", "abc", "ciclo-de-outro"])
def test_referencia_desconhecida_vai_para_devolucao_sem_pedido(
    cenario: Cenario,
    relogio: RelogioControlado,
    caplog: pytest.LogCaptureFixture,
    referencia: str,
) -> None:  # A-8
    c = cenario
    if referencia == "ciclo-de-outro":
        referencia = f"om-c{c.arranjo.ciclo.pk + 1000}-p{c.x.pk}"
    caplog.set_level(logging.ERROR)
    outra = _cobranca_direta(c, "anomalia-2", referencia_externa=referencia)
    relogio.congelar(T0 + 2 * H)
    c.sim.aprovar(outra, em=T0 + 2 * H)
    sincronizar(outra)
    destino = _destino(outra)
    assert (destino.destino, destino.motivo, destino.pedido) == (
        "sem_pedido",
        "referencia_desconhecida",
        None,
    )
    assert any(r.levelno == logging.ERROR and outra in r.getMessage() for r in caplog.records)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="pagamento.destino")
    assert auditoria.alteracoes["destino"] == "sem_pedido"
    assert auditoria.alteracoes["pedido"] is None
    assert _situacao(c.x).situacao == "aguardando_pagamento"
    assert not EntradaAuditoria.objects.filter(acao="pedido.quitar").exists()


def test_aprovado_sem_horario_nao_gera_destino(
    cenario: Cenario, relogio: RelogioControlado, caplog: pytest.LogCaptureFixture
) -> None:  # A-9
    c = cenario
    caplog.set_level(logging.ERROR)
    resposta = PagamentoConsultado(
        provedor="simulador",
        id_externo="sim-9001",
        referencia_externa=c.x.referencia_externa,
        valor=c.x.total,
        situacao=SituacaoNoProvedor.APROVADO,
        criado_em=T0 + 1 * H,
        aprovado_em=None,
        expira_em=T0 + 24 * H,
        consultado_em=T0 + 2 * H,
    )
    relogio.congelar(T0 + 2 * H)
    with transaction.atomic():
        sincronizar_pagamento(resposta, origem="tarefa")
    assert PagamentoNoProvedor.objects.get(id_externo="sim-9001").situacao == "aprovado"
    assert DestinoDoPagamento.objects.count() == 0
    assert "Pagamento sim-9001 aprovado sem horário de aprovação" in caplog.text
    assert _situacao(c.x).situacao == "aguardando_pagamento"


def test_valor_diferente_do_pedido_vai_para_devolucao(
    cenario: Cenario, relogio: RelogioControlado
) -> None:  # A-10
    c = cenario
    outra = _cobranca_direta(c, "anomalia-3", valor=D("90.00"))
    relogio.congelar(T0 + 2 * H)
    c.sim.aprovar(outra, em=T0 + 2 * H)
    sincronizar(outra)
    destino = _destino(outra)
    assert (destino.destino, destino.motivo) == ("devolucao", "valor_divergente")
    assert _situacao(c.x).situacao == "aguardando_pagamento"


def test_aprovado_antes_da_suspensao_quita_o_pedido_cancelado(
    cenario: Cenario, relogio: RelogioControlado
) -> None:  # A-11, Spec §2
    c = cenario
    relogio.congelar(T0 + 2 * H + timedelta(minutes=30))
    c.sim.aprovar(c.p)  # aprovado no provedor às 15:30
    relogio.congelar(T0 + 3 * H)
    cancelar_direto(c.x, "suspensao", T0 + 3 * H)
    relogio.congelar(T0 + 4 * H)
    sincronizar(c.p)
    assert _destino(c.p).destino == "quita"
    situacao = _situacao(c.x)
    assert situacao.situacao == "pago"
    assert (situacao.cancelado_em, situacao.motivo_do_cancelamento) == (None, "")
    (auditoria,) = EntradaAuditoria.objects.filter(acao="pedido.quitar")
    assert auditoria.alteracoes["cancelamento_sem_efeito"] == "suspensao"
    assert len(_avisos(c.arranjo.a)) == 1


@pytest.mark.parametrize("minutos", [0, 30])
def test_aprovado_na_suspensao_ou_depois_gera_devolucao(
    cenario: Cenario, relogio: RelogioControlado, minutos: int
) -> None:  # A-12
    c = cenario
    relogio.congelar(T0 + 3 * H)
    cancelar_direto(c.x, "suspensao", T0 + 3 * H)
    relogio.congelar(T0 + 3 * H + timedelta(minutes=minutos))
    c.sim.aprovar(c.p, em=T0 + 3 * H + timedelta(minutes=minutos))
    sincronizar(c.p)
    destino = _destino(c.p)
    assert (destino.destino, destino.motivo) == ("devolucao", "pedido_cancelado")
    assert _situacao(c.x).situacao == "cancelado"
    assert _avisos(c.arranjo.a) == []


def test_o_detalhe_mostra_o_pagamento_confirmado(
    cenario: Cenario, relogio: RelogioControlado
) -> None:  # A-13
    c = cenario
    _aprovar_e_receber(c, relogio, T0 + 2 * H, T0 + 2 * H + timedelta(minutes=1))
    cliente = Client()
    cliente.force_login(c.arranjo.a)
    html = cliente.get(f"/pedidos/{c.x.pk}/").content.decode()
    assert "Pago em 02/11/2026 às 12:00 (horário de Brasília)." in html
    assert "Pagar com Pix" not in html
    assert "SIMULADO-" not in html


@pytest.mark.acceptance
def test_falha_do_whatsapp_nao_desfaz_a_quitacao(
    cenario: Cenario, relogio: RelogioControlado, simulador_whatsapp: Any
) -> None:  # A-14, cenário 24 (confirmação real)
    c = cenario
    Conta.objects.filter(pk=c.arranjo.a.pk).update(
        telefone="+5521999990000", whatsapp_consentido_em=T0
    )
    simulador_whatsapp.falhar_sempre()
    _aprovar_e_receber(c, relogio, T0 + 2 * H, T0 + 2 * H + timedelta(minutes=1))
    for espera in (timedelta(0), timedelta(minutes=1), timedelta(minutes=10)):
        relogio.avancar(espera)
        processar_envios()
    assert _situacao(c.x).situacao == "pago"
    assert not Envio.objects.filter(tipo="pagamento_confirmado", canal="whatsapp").exists()
    emails = Envio.objects.filter(tipo="pagamento_confirmado", canal="email")
    assert [e.situacao for e in emails] == ["enviado"]
    cliente = Client()
    cliente.force_login(c.arranjo.a)
    assert "Pagamento confirmado: F" in cliente.get("/notificacoes/").content.decode()


def test_falha_de_outro_receptor_desfaz_a_sincronizacao(
    cenario: Cenario, relogio: RelogioControlado
) -> None:  # A-15
    c = cenario

    def falha(sender: Any, **kwargs: Any) -> None:
        raise RuntimeError("falha de teste")

    situacao_do_pagamento_mudou.connect(falha, weak=False, dispatch_uid="teste.falha")
    try:
        _aprovar_e_receber(c, relogio, T0 + 2 * H, T0 + 2 * H + timedelta(minutes=1))
        assert DestinoDoPagamento.objects.count() == 0
        assert _situacao(c.x).situacao == "aguardando_pagamento"
        assert _avisos(c.arranjo.a) == []
        assert PagamentoNoProvedor.objects.get(id_externo=c.p).situacao == "pendente"
    finally:
        situacao_do_pagamento_mudou.disconnect(dispatch_uid="teste.falha")
    processar_chamadas()
    assert _destino(c.p).destino == "quita"
    assert _situacao(c.x).situacao == "pago"
    assert len(_avisos(c.arranjo.a)) == 1


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("om-c12-p34", (12, 34)),
        ("om-c1-p1", (1, 1)),
        ("abc", None),
        ("om-c12-p", None),
        ("om-c-p3", None),
        ("xom-c1-p2", None),
        ("om-c1-p2x", None),
        ("om-c1-p2\n", None),
        ("OM-C1-P2", None),
        ("", None),
    ],
)
def test_ler_referencia(texto: str, esperado: tuple[int, int] | None) -> None:
    assert ler_referencia(texto) == esperado


def test_destino_so_aceita_insercao_e_e_coerente(cenario: Cenario) -> None:
    c = cenario
    pagamentos = [
        PagamentoNoProvedor.objects.create(
            provedor="simulador",
            ambiente="testes",
            id_externo=f"apoio-{i}",
            referencia_externa=c.x.referencia_externa,
            valor=c.x.total,
            situacao="aprovado",
            criado_no_provedor_em=T0 + H,
            expira_em=T0 + 24 * H,
            aprovado_no_provedor_em=T0 + 2 * H,
        )
        for i in range(8)
    ]
    ok = DestinoDoPagamento.objects.create(
        pagamento=pagamentos[0], pedido=c.x, destino="quita", motivo=""
    )
    recusas: list[dict[str, Any]] = [
        {"pagamento": pagamentos[1], "pedido": c.x, "destino": "quita", "motivo": ""},  # 2º quita
        {"pagamento": pagamentos[2], "pedido": c.x, "destino": "quita", "motivo": "duplicidade"},
        {"pagamento": pagamentos[3], "pedido": c.x, "destino": "devolucao", "motivo": ""},
        {"pagamento": pagamentos[4], "pedido": c.x, "destino": "devolucao", "motivo": "x"},
        {
            "pagamento": pagamentos[5],
            "pedido": None,
            "destino": "devolucao",
            "motivo": "duplicidade",
        },
        {
            "pagamento": pagamentos[6],
            "pedido": c.x,
            "destino": "sem_pedido",
            "motivo": "duplicidade",
        },
        {
            "pagamento": pagamentos[7],
            "pedido": c.x,
            "destino": "sem_pedido",
            "motivo": "referencia_desconhecida",
        },
        {
            "pagamento": pagamentos[0],
            "pedido": c.x,
            "destino": "devolucao",
            "motivo": "duplicidade",
        },
    ]
    for campos in recusas:
        with pytest.raises(DatabaseError), transaction.atomic():
            DestinoDoPagamento.objects.create(**campos)
    ok.destino = "devolucao"
    with pytest.raises(RegistroImutavel):
        ok.save()
    with pytest.raises(RegistroImutavel):
        ok.delete()
    with pytest.raises(RegistroImutavel):
        DestinoDoPagamento.objects.all().update(motivo="duplicidade")
    tabela = DestinoDoPagamento._meta.db_table
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f'UPDATE "{tabela}" SET motivo = %s WHERE id = %s', ["x", ok.pk])  # noqa: S608
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f'DELETE FROM "{tabela}" WHERE id = %s', [ok.pk])  # noqa: S608
    DestinoDoPagamento.objects.create(
        pagamento=pagamentos[1], pedido=None, destino="sem_pedido", motivo="referencia_desconhecida"
    )
    assert DestinoDoPagamento.objects.count() == 2
