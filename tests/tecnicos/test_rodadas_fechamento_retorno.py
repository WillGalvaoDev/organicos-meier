"""E06-06: verificação do mínimo e retorno para interesse (acceptance A-1 a A-9 e A-11)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.db.transaction import TransactionManagementError

from apps.catalogo.models import Produto
from apps.catalogo.servicos import editar_produto
from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import alterar_minimo
from apps.interesses.models import SituacaoParcela
from apps.interesses.servicos import (
    adicionar_interesse,
    interesse_do_comprador,
    reduzir_interesse,
)
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas import avisos
from apps.rodadas.estoque import alterar_estoque
from apps.rodadas.fechamento import (
    TransicaoRecusada,
    encerrar_fechamento,
    iniciar_fechamento,
    prazo_do_fechamento,
    voltar_para_interesse,
)
from apps.rodadas.models import Ciclo, CondicaoDoProdutoNoCiclo, Etapa, Rodada
from tests.apoio.interesses import cenario, parcelas, pendente
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
T0 = datetime(2026, 11, 2, 13, 30, tzinfo=UTC)
T = datetime(2026, 11, 3, 13, 30, tzinfo=UTC)
H = timedelta(hours=1)
RETORNO = "retorno_para_interesse"


def admin() -> Conta:
    return Conta.objects.get(papel="administrador")


def montar(minimo: str, limite: str | None = None) -> tuple[Rodada, Produto, Any]:
    rodada, produto, estoque = cenario(limite, nome="Ovos", preco=D("10.00"), multiplo=D("12"))
    Fornecedor.objects.filter(pk=rodada.fornecedor_id).update(
        nome="Sítio Boa Terra", minimo=D(minimo)
    )
    return rodada, produto, estoque


def comprar(conta: Conta, produto: Produto, quantidade: str) -> None:
    adicionar_interesse(conta, produto, quantidade)


def etapa(rodada: Rodada) -> str:
    return str(Rodada.objects.get(pk=rodada.pk).etapa)


def avisos_de(conta: Conta, evento: str = RETORNO) -> list[Notificacao]:
    return list(Notificacao.objects.filter(conta=conta, evento=evento).order_by("pk"))


def estado_do_a2(
    relogio: RelogioControlado,
) -> tuple[Rodada, Produto, Any, Ciclo, Conta, Conta, Conta]:
    """Mínimo R$ 150,00; A com 15, B com 1 e C com 8; C zera durante o fechamento; no fim,
    A e B somam 16 (12 em caixas, R$ 120,00): o mínimo não é atingido."""
    rodada, produto, estoque = montar("150.00")
    a, b, c = (ContaFactory.create() for _ in range(3))
    comprar(a, produto, "15")
    comprar(b, produto, "1")
    comprar(c, produto, "8")
    relogio.congelar(T0)
    ciclo = iniciar_fechamento(admin(), rodada)
    relogio.congelar(T - H)
    reduzir_interesse(c, produto, "8")
    relogio.congelar(T)
    return rodada, produto, estoque, ciclo, a, b, c


@pytest.mark.acceptance
def test_minimo_atingido_aguarda_o_pagamento(relogio: RelogioControlado) -> None:
    # A-1, cenário 9 (suficiente)
    rodada, produto, _ = montar("100.00")
    a, b = ContaFactory.create(), ContaFactory.create()
    comprar(a, produto, "12")
    comprar(b, produto, "6")
    relogio.congelar(T0)
    iniciar_fechamento(admin(), rodada)
    relogio.congelar(T)
    resultado = encerrar_fechamento(rodada)
    assert resultado is not None
    assert resultado.etapa_final == Etapa.FECHAMENTO_ENCERRADO
    assert etapa(rodada) == Etapa.FECHAMENTO_ENCERRADO
    assert interesse_do_comprador(b, produto).reservado == 0
    assert len(avisos_de(b, "excedentes_removidos")) == 1
    assert Notificacao.objects.filter(evento=RETORNO).count() == 0
    (entrada,) = EntradaAuditoria.objects.filter(acao="rodada.encerrar_fechamento")
    assert entrada.alteracoes["valor_elegivel"] == "120.00"
    assert entrada.alteracoes["minimo"] == "100.00"
    assert entrada.alteracoes["resultado"] == "aguardando_pagamento"


@pytest.mark.acceptance
def test_minimo_nao_atingido_volta_para_interesse(relogio: RelogioControlado) -> None:
    # A-2, cenário 9 (insuficiente)
    rodada, produto, _, ciclo, a, b, c = estado_do_a2(relogio)
    resultado = encerrar_fechamento(rodada)
    assert resultado is not None
    assert resultado.etapa_final == Etapa.INTERESSE
    assert etapa(rodada) == Etapa.INTERESSE
    assert interesse_do_comprador(a, produto).reservado == D("12")
    (parcela_b,) = parcelas(produto, b)
    assert parcela_b.situacao == SituacaoParcela.REMOVIDA
    for conta in (a, b):
        (aviso,) = avisos_de(conta)
        assert aviso.titulo == "Rodada de volta ao interesse: Sítio Boa Terra"
        assert "não há estornos" in aviso.corpo
        assert "150,00" not in aviso.corpo
        assert "120,00" not in aviso.corpo
        assert aviso.chave == f"retorno_para_interesse:{ciclo.pk}:{conta.pk}"
        assert aviso.link == "/carrinho/"
    assert avisos_de(c) == []
    (encerramento,) = EntradaAuditoria.objects.filter(acao="rodada.encerrar_fechamento")
    assert encerramento.alteracoes["resultado"] == "retorno_para_interesse"
    (retorno,) = EntradaAuditoria.objects.filter(acao="rodada.voltar_para_interesse")
    assert retorno.autor_tipo == "sistema"
    assert retorno.alteracoes == {
        "rodada": rodada.pk,
        "ciclo": ciclo.pk,
        "motivo": "minimo_nao_atingido",
    }


def test_reducao_de_preco_so_derruba_no_fim_do_prazo(relogio: RelogioControlado) -> None:  # A-3
    rodada, produto, _ = montar("120.00")
    comprar(ContaFactory.create(), produto, "12")
    relogio.congelar(T0)
    iniciar_fechamento(admin(), rodada)
    relogio.congelar(T - H)
    editar_produto(admin(), produto, preco="9.00")
    relogio.congelar(T - timedelta(minutes=30))
    assert etapa(rodada) == Etapa.FECHAMENTO
    relogio.congelar(T)
    resultado = encerrar_fechamento(rodada)
    assert resultado is not None
    assert resultado.etapa_final == Etapa.INTERESSE


@pytest.mark.acceptance
def test_a_queda_e_a_recuperacao_do_minimo_nao_mexem_no_prazo(
    relogio: RelogioControlado,
) -> None:  # A-4, cenário 5
    rodada, produto, _ = montar("100.00")
    a, b = ContaFactory.create(), ContaFactory.create()
    comprar(a, produto, "12")
    relogio.congelar(T0)
    iniciar_fechamento(admin(), rodada)
    relogio.congelar(T - 2 * H)
    reduzir_interesse(a, produto, "12")
    assert prazo_do_fechamento(rodada) == T
    relogio.congelar(T - H)
    comprar(b, produto, "12")
    assert prazo_do_fechamento(rodada) == T
    relogio.congelar(T)
    resultado = encerrar_fechamento(rodada)
    assert resultado is not None
    assert resultado.etapa_final == Etapa.FECHAMENTO_ENCERRADO
    assert prazo_do_fechamento(rodada) == T


@pytest.mark.acceptance
def test_depois_do_retorno_as_condicoes_voltam_a_ser_editaveis(
    relogio: RelogioControlado,
) -> None:  # A-5, cenário 73
    rodada, produto, estoque, ciclo, _, _, _ = estado_do_a2(relogio)
    encerrar_fechamento(rodada)
    alterar_minimo(admin(), rodada.fornecedor, "80,00")
    alterar_estoque(admin(), estoque, "30")
    ciclo.refresh_from_db()
    assert ciclo.minimo == D("150.00")
    condicao = CondicaoDoProdutoNoCiclo.objects.get(ciclo=ciclo, produto=produto)
    assert condicao.limite_estoque is None
    assert Fornecedor.objects.get(pk=rodada.fornecedor_id).minimo == D("80.00")


def test_o_estoque_liberado_vai_para_a_fila_no_retorno(relogio: RelogioControlado) -> None:
    # A-6
    rodada, produto, _ = montar("120.00", limite="16")
    a, b, d = (ContaFactory.create() for _ in range(3))
    comprar(a, produto, "15")
    comprar(b, produto, "1")
    espera = pendente(d, produto, 3)
    relogio.congelar(T0)
    iniciar_fechamento(admin(), rodada)
    relogio.congelar(T - H)
    editar_produto(admin(), produto, preco="9.00")
    relogio.congelar(T)
    encerrar_fechamento(rodada)
    assert etapa(rodada) == Etapa.INTERESSE
    espera.refresh_from_db()
    assert (espera.situacao, espera.quantidade_reservada, espera.quantidade_pendente) == (
        SituacaoParcela.ATIVA,
        D("3"),
        D("0"),
    )
    assert EntradaAuditoria.objects.filter(acao="interesse.alocar_pendentes").count() == 1
    total = sum(p.quantidade_reservada for p in parcelas(produto))
    assert total == D("15")


def test_novo_fechamento_depois_do_retorno_gera_novo_ciclo(relogio: RelogioControlado) -> None:
    # A-7
    rodada, _produto, _, primeiro, a, _, _ = estado_do_a2(relogio)
    encerrar_fechamento(rodada)
    alterar_minimo(admin(), rodada.fornecedor, "80,00")
    relogio.congelar(T + H)
    segundo = iniciar_fechamento(admin(), rodada)
    assert segundo.numero == 2
    assert segundo.pk != primeiro.pk
    assert prazo_do_fechamento(rodada) == T + H + timedelta(hours=24)
    assert len(avisos_de(a, "fechamento_iniciado")) == 2


@pytest.mark.parametrize("etapa_inicial", [Etapa.INTERESSE, Etapa.FECHAMENTO, Etapa.PAGAMENTO])
def test_so_o_fechamento_encerrado_volta_para_interesse(etapa_inicial: str) -> None:  # A-8
    rodada, _, _ = montar("100.00")
    Rodada.objects.filter(pk=rodada.pk).update(etapa=etapa_inicial)
    with pytest.raises(TransicaoRecusada) as erro, transaction.atomic():
        voltar_para_interesse(rodada, motivo="minimo_nao_atingido")
    assert erro.value.codigo == "fora_de_fechamento_encerrado"
    assert erro.value.mensagem == (
        "Só uma rodada com o fechamento encerrado pode voltar para interesse."
    )
    assert etapa(rodada) == etapa_inicial
    assert EntradaAuditoria.objects.filter(acao="rodada.voltar_para_interesse").count() == 0


def test_motivo_desconhecido_e_erro() -> None:  # A-9
    rodada, _, _ = montar("100.00")
    Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.FECHAMENTO_ENCERRADO)
    with pytest.raises(ValueError, match="motivo"), transaction.atomic():
        voltar_para_interesse(rodada, motivo="outro")
    assert etapa(rodada) == Etapa.FECHAMENTO_ENCERRADO


@pytest.mark.django_db(transaction=True)
def test_voltar_para_interesse_exige_transacao() -> None:  # A-9
    rodada, _, _ = montar("100.00")
    Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.FECHAMENTO_ENCERRADO)
    with pytest.raises(TransactionManagementError):
        voltar_para_interesse(rodada, motivo="minimo_nao_atingido")
    assert etapa(rodada) == Etapa.FECHAMENTO_ENCERRADO


def test_falha_no_aviso_de_retorno_desfaz_o_encerramento(
    monkeypatch: pytest.MonkeyPatch, relogio: RelogioControlado
) -> None:  # A-11
    rodada, produto, _, _, a, b, _ = estado_do_a2(relogio)

    def estoura(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("falha na emissão")

    monkeypatch.setattr(avisos, "emitir_evento_para_varios", estoura)
    with pytest.raises(RuntimeError):
        encerrar_fechamento(rodada)
    assert etapa(rodada) == Etapa.FECHAMENTO
    assert interesse_do_comprador(b, produto).reservado == D("1")
    assert interesse_do_comprador(a, produto).reservado == D("15")
    assert EntradaAuditoria.objects.filter(acao="rodada.encerrar_fechamento").count() == 0
    assert Notificacao.objects.filter(evento="excedentes_removidos").count() == 0
