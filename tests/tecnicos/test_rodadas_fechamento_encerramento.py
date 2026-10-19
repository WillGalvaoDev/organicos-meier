"""E06-05: encerramento do fechamento e remoção de excedentes (acceptance A-1 a A-13)."""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from apps.catalogo.models import Produto, Unidade
from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.interesses.servicos import adicionar_interesse, interesse_do_comprador
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas import avisos, fechamento
from apps.rodadas.fechamento import (
    encerrar_fechamento,
    encerrar_fechamentos_vencidos,
    iniciar_fechamento,
    prorrogar_fechamento,
)
from apps.rodadas.models import Etapa, Rodada
from tests.apoio.interesses import cenario, parcelas, pendente, reservada, sem_minimo
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, EstoqueDaRodadaFactory, ParcelaFactory, ProdutoFactory

pytestmark = pytest.mark.django_db

D = Decimal
T0 = datetime(2026, 11, 2, 13, 30, tzinfo=UTC)
T = datetime(2026, 11, 3, 13, 30, tzinfo=UTC)
MS = timedelta(milliseconds=1)
ACAO = "rodada.encerrar_fechamento"
EVENTO = "excedentes_removidos"


def admin() -> Conta:
    return Conta.objects.get(papel="administrador")


def montar(**produto: Any) -> tuple[Rodada, Produto]:
    """Sítio Boa Terra, sem mínimo; Ovos a R$ 10,00 com múltiplo 12 e sem limite."""
    campos = {"nome": "Ovos", "preco": D("10.00"), "multiplo": D("12"), **produto}
    rodada, p, _ = cenario(None, **campos)
    Fornecedor.objects.filter(pk=rodada.fornecedor_id).update(nome="Sítio Boa Terra")
    sem_minimo(rodada)
    return rodada, p


def comprar(conta: Conta, produto: Produto, quantidade: str) -> None:
    adicionar_interesse(conta, produto, quantidade)


def iniciar(relogio: RelogioControlado, rodada: Rodada) -> None:
    relogio.congelar(T0)
    iniciar_fechamento(admin(), rodada)


def avisos_de(conta: Conta) -> list[Notificacao]:
    return list(Notificacao.objects.filter(conta=conta, evento=EVENTO).order_by("pk"))


def reservado(conta: Conta, produto: Produto) -> Decimal:
    return interesse_do_comprador(conta, produto).reservado


@pytest.mark.acceptance
def test_as_ultimas_adicoes_perdem_o_excedente(relogio: RelogioControlado) -> None:
    # A-1, cenário 7
    rodada, p = montar()
    a, b = ContaFactory.create(), ContaFactory.create()
    relogio.congelar(T0 - timedelta(hours=1))
    comprar(a, p, "8")
    comprar(b, p, "10")
    iniciar(relogio, rodada)
    relogio.congelar(T)
    resultado = encerrar_fechamento(rodada)
    assert resultado is not None
    assert resultado.etapa_final == Etapa.FECHAMENTO_ENCERRADO
    assert resultado.removidas == {p.pk: D("6")}
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO_ENCERRADO
    assert reservado(a, p) == D("8")
    (parcela_b,) = parcelas(p, b)
    assert (parcela_b.situacao, parcela_b.quantidade_reservada) == (
        SituacaoParcela.ATIVA,
        D("4"),
    )
    assert parcela_b.quantidade_original == D("10")
    (aviso,) = avisos_de(b)
    assert aviso.titulo == "Excedentes removidos: Ovos"
    assert "6 unidade de Ovos não completaram caixa" in aviso.corpo
    assert "Continuam no seu interesse: 4 unidade" in aviso.corpo
    assert aviso.corpo == (
        "No fim do fechamento da rodada de Sítio Boa Terra, 6 unidade de Ovos não completaram "
        "caixa e foram removidas do seu interesse. Continuam no seu interesse: 4 unidade."
    )
    assert aviso.link == "/carrinho/"
    assert avisos_de(a) == []
    (entrada,) = EntradaAuditoria.objects.filter(acao=ACAO)
    assert entrada.autor_tipo == "sistema"
    assert entrada.alteracoes["removidas"] == [[parcela_b.pk, p.pk, "6.000"]]


def test_sai_primeiro_a_parcela_mais_recente(relogio: RelogioControlado) -> None:  # A-2
    rodada, p = montar()
    a, b = ContaFactory.create(), ContaFactory.create()
    comprar(a, p, "6")
    comprar(b, p, "4")
    comprar(a, p, "5")
    iniciar(relogio, rodada)
    relogio.congelar(T)
    encerrar_fechamento(rodada)
    primeira, segunda = parcelas(p, a)
    assert (primeira.quantidade_reservada, segunda.quantidade_reservada) == (D("6"), D("2"))
    assert reservado(b, p) == D("4")
    (aviso,) = avisos_de(a)
    assert "3 unidade de Ovos" in aviso.corpo
    assert "Continuam no seu interesse: 8 unidade" in aviso.corpo


def test_abaixo_de_uma_caixa_sai_tudo(relogio: RelogioControlado) -> None:  # A-3
    rodada, p = montar()
    a = ContaFactory.create()
    comprar(a, p, "7")
    iniciar(relogio, rodada)
    relogio.congelar(T)
    encerrar_fechamento(rodada)
    (parcela,) = parcelas(p, a)
    assert parcela.situacao == SituacaoParcela.REMOVIDA
    (aviso,) = avisos_de(a)
    assert "7 unidade de Ovos" in aviso.corpo
    assert "Continuam no seu interesse: 0 unidade" in aviso.corpo


def test_total_exato_nao_remove_nem_avisa(relogio: RelogioControlado) -> None:  # A-4
    rodada, p = montar()
    a, b = ContaFactory.create(), ContaFactory.create()
    comprar(a, p, "12")
    comprar(b, p, "12")
    iniciar(relogio, rodada)
    relogio.congelar(T)
    resultado = encerrar_fechamento(rodada)
    assert resultado is not None
    assert resultado.removidas == {}
    assert Notificacao.objects.filter(evento=EVENTO).count() == 0
    (entrada,) = EntradaAuditoria.objects.filter(acao=ACAO)
    assert entrada.alteracoes["removidas"] == []
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO_ENCERRADO


def test_multiplo_fracionario(relogio: RelogioControlado) -> None:  # A-5
    rodada, k = montar(
        unidade=Unidade.KG, multiplo=D("1"), incremento=D("0.25"), nome="Queijo", preco=D("10.00")
    )
    a, b = ContaFactory.create(), ContaFactory.create()
    comprar(a, k, "1.5")
    comprar(b, k, "1.25")
    iniciar(relogio, rodada)
    relogio.congelar(T)
    encerrar_fechamento(rodada)
    assert reservado(a, k) == D("1.5")
    assert reservado(b, k) == D("0.5")
    (aviso,) = avisos_de(b)
    assert "0,75 kg de Queijo" in aviso.corpo


def test_parcela_com_pendencia_vira_pendente(relogio: RelogioControlado) -> None:  # A-6
    rodada, p = montar()
    a = ContaFactory.create()
    parcela = ParcelaFactory.create(
        comprador=a,
        produto=p,
        quantidade_original=D("8"),
        quantidade_reservada=D("5"),
        quantidade_pendente=D("3"),
    )
    iniciar(relogio, rodada)
    relogio.congelar(T)
    encerrar_fechamento(rodada)
    parcela.refresh_from_db()
    assert (parcela.situacao, parcela.quantidade_reservada, parcela.quantidade_pendente) == (
        SituacaoParcela.PENDENTE,
        D("0"),
        D("3"),
    )


def test_produto_sem_multiplo_fica_intacto(relogio: RelogioControlado) -> None:  # A-7
    rodada, _produto = montar()
    q = ProdutoFactory.create(
        fornecedor=rodada.fornecedor, unidade=Unidade.UNIDADE, nome="Mel", multiplo=None
    )
    EstoqueDaRodadaFactory.create(rodada=rodada, produto=q, limite=None)
    a = ContaFactory.create()
    comprar(a, q, "7")
    iniciar(relogio, rodada)
    relogio.congelar(T)
    encerrar_fechamento(rodada)
    assert reservado(a, q) == D("7")
    assert avisos_de(a) == []


def test_o_encerramento_acontece_uma_unica_vez_e_so_no_prazo(
    relogio: RelogioControlado,
) -> None:  # A-8
    rodada, p = montar()
    a, b = ContaFactory.create(), ContaFactory.create()
    comprar(a, p, "8")
    comprar(b, p, "10")
    iniciar(relogio, rodada)
    relogio.congelar(T - MS)
    assert encerrar_fechamento(rodada) is None
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO
    assert EntradaAuditoria.objects.filter(acao=ACAO).count() == 0
    relogio.congelar(T)
    assert encerrar_fechamento(rodada) is not None
    assert encerrar_fechamento(rodada) is None
    assert EntradaAuditoria.objects.filter(acao=ACAO).count() == 1
    assert len(avisos_de(b)) == 1


@pytest.mark.acceptance
def test_a_tarefa_nao_mexe_no_que_nao_venceu(relogio: RelogioControlado) -> None:
    # A-9, cenário 4
    relogio.congelar(T0)
    em_interesse, p, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), p, 20)
    em_fechamento, p2, _ = cenario("20", etapa=Etapa.FECHAMENTO, preco=D("10.00"))
    reservada(ContaFactory.create(), p2, 20)
    assert encerrar_fechamentos_vencidos() == 0
    assert Rodada.objects.get(pk=em_interesse.pk).etapa == Etapa.INTERESSE
    assert Rodada.objects.get(pk=em_fechamento.pk).etapa == Etapa.FECHAMENTO


def test_uma_rodada_com_falha_nao_impede_as_outras(
    monkeypatch: pytest.MonkeyPatch, relogio: RelogioControlado, caplog: pytest.LogCaptureFixture
) -> None:  # A-10
    relogio.congelar(T0)
    tres = []
    for _ in range(3):
        rodada, produto, _ = cenario("20", etapa=Etapa.FECHAMENTO, preco=D("10.00"))
        sem_minimo(rodada)  # a spec parte de fornecedor sem mínimo; o retorno é da E06-06
        tres.append(rodada)
        reservada(ContaFactory.create(email_normalizado=f"sigilo{rodada.pk}@x.com"), produto, 5)
    relogio.congelar(T + timedelta(minutes=1))
    original = fechamento.encerrar_fechamento

    def com_falha(rodada: Rodada) -> Any:
        if rodada.pk == tres[1].pk:
            raise RuntimeError("falha simulada")
        return original(rodada)

    monkeypatch.setattr(fechamento, "encerrar_fechamento", com_falha)
    caplog.set_level(logging.DEBUG)
    assert encerrar_fechamentos_vencidos() == 2
    etapas = [Rodada.objects.get(pk=r.pk).etapa for r in tres]
    assert etapas == [Etapa.FECHAMENTO_ENCERRADO, Etapa.FECHAMENTO, Etapa.FECHAMENTO_ENCERRADO]
    assert str(tres[1].pk) in caplog.text
    assert "RuntimeError" in caplog.text
    assert "sigilo" not in caplog.text
    assert "@" not in caplog.text
    monkeypatch.setattr(fechamento, "encerrar_fechamento", original)
    assert encerrar_fechamentos_vencidos() == 1
    assert Rodada.objects.get(pk=tres[1].pk).etapa == Etapa.FECHAMENTO_ENCERRADO


def test_a_tarefa_esta_registrada_como_periodica() -> None:  # A-11
    from procrastinate.contrib.django import app

    from apps.rodadas import tarefas

    nome = "encerrar_fechamentos_vencidos"
    candidatas = [p for p in app.periodic_registry.periodic_tasks.values() if p.task.name == nome]
    assert len(candidatas) == 1
    assert candidatas[0].cron == "* * * * *"
    assert candidatas[0].task.queueing_lock == nome
    assert tarefas.NOME_DA_TAREFA == nome


def test_falha_no_aviso_desfaz_o_encerramento(
    monkeypatch: pytest.MonkeyPatch, relogio: RelogioControlado
) -> None:  # A-12
    rodada, p = montar()
    a, b = ContaFactory.create(), ContaFactory.create()
    comprar(a, p, "8")
    comprar(b, p, "10")
    iniciar(relogio, rodada)
    relogio.congelar(T)

    def estoura(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("falha na emissão")

    monkeypatch.setattr(avisos, "emitir_evento", estoura)
    with pytest.raises(RuntimeError):
        encerrar_fechamento(rodada)
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO
    assert reservado(b, p) == D("10")
    assert EntradaAuditoria.objects.filter(acao=ACAO).count() == 0
    assert ParcelaDeInteresse.objects.filter(produto=p, situacao="removida").count() == 0


def test_a_prorrogacao_adia_o_encerramento(relogio: RelogioControlado) -> None:  # A-13
    rodada, p = montar()
    comprar(ContaFactory.create(), p, "12")
    iniciar(relogio, rodada)
    relogio.congelar(T - timedelta(hours=1))
    prorrogar_fechamento(admin(), rodada, T + timedelta(hours=1))
    relogio.congelar(T + timedelta(minutes=1))
    assert encerrar_fechamentos_vencidos() == 0
    relogio.congelar(T + timedelta(hours=1))
    assert encerrar_fechamentos_vencidos() == 1
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO_ENCERRADO


def test_pendencia_de_outro_comprador_nao_e_tocada(relogio: RelogioControlado) -> None:
    rodada, p = montar()
    a, c = ContaFactory.create(), ContaFactory.create()
    comprar(a, p, "7")
    espera = pendente(c, p, 4)
    iniciar(relogio, rodada)
    relogio.congelar(T)
    encerrar_fechamento(rodada)
    espera.refresh_from_db()
    assert (espera.situacao, espera.quantidade_pendente) == (SituacaoParcela.PENDENTE, D("4"))
