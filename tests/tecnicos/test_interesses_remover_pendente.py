"""E05-03: remoção de pendentes pelo comprador (acceptance A-1 a A-8)."""

from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied

from apps.catalogo.quantidades import QuantidadeInvalida
from apps.interesses.consultas import total_reservado
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.interesses.servicos import RemocaoAcimaDoPendente, remover_pendente
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.models import Etapa
from tests.apoio.interesses import auditorias, cenario, parcelas, pendente, reservada
from tests.fabricas import ContaFactory, ParcelaFactory

pytestmark = pytest.mark.django_db

D = Decimal
ACAO = "interesse.remover_pendente"


def estado(parcela: ParcelaDeInteresse) -> tuple[str, Decimal, Decimal]:
    parcela.refresh_from_db()
    return (parcela.situacao, parcela.quantidade_reservada, parcela.quantidade_pendente)


@pytest.mark.acceptance
def test_remocao_parcial_e_total_da_pendencia() -> None:  # A-1, cenário 97
    _, produto, _ = cenario("30")
    a, b = ContaFactory.create(), ContaFactory.create()
    parcela = ParcelaFactory.create(
        comprador=a,
        produto=produto,
        quantidade_original=D("10"),
        quantidade_reservada=D("6"),
        quantidade_pendente=D("4"),
    )
    outra = reservada(b, produto, 5)
    sequencias = (parcela.sequencia, outra.sequencia)
    resumo = remover_pendente(a, produto, "2")
    assert (resumo.reservado, resumo.pendente) == (D("6"), D("2"))
    assert estado(parcela) == (SituacaoParcela.ATIVA, D("6"), D("2"))
    resumo = remover_pendente(a, produto, "2")
    assert (resumo.reservado, resumo.pendente) == (D("6"), D("0"))
    assert estado(parcela) == (SituacaoParcela.ATIVA, D("6"), D("0"))
    assert estado(outra) == (SituacaoParcela.ATIVA, D("5"), D("0"))
    assert (parcela.sequencia, outra.sequencia) == sequencias
    assert parcela.quantidade_original == D("10")
    assert len(auditorias(ACAO)) == 2


def test_remocao_comeca_pela_parcela_mais_recente() -> None:  # A-2
    _, produto, _ = cenario("10")
    a = ContaFactory.create()
    antiga = pendente(a, produto, 2)
    recente = pendente(a, produto, 3)
    remover_pendente(a, produto, "4")
    assert estado(recente) == (SituacaoParcela.REMOVIDA, D("0"), D("0"))
    assert estado(antiga) == (SituacaoParcela.PENDENTE, D("0"), D("1"))
    (entrada,) = auditorias(ACAO)
    assert entrada.alteracoes["parcelas"] == [recente.pk, antiga.pk]
    assert entrada.alteracoes["quantidade"] == "4.000"
    assert entrada.alteracoes["produto"] == produto.pk


def test_parcela_so_pendente_vira_removida() -> None:  # A-3
    _, produto, _ = cenario("10")
    a = ContaFactory.create()
    parcela = pendente(a, produto, 4)
    remover_pendente(a, produto, "4")
    assert estado(parcela) == (SituacaoParcela.REMOVIDA, D("0"), D("0"))


@pytest.mark.acceptance
@pytest.mark.parametrize("entrada", ["5", "1.5", "0", "-1", "abc", 1.0])
def test_remocao_invalida_nao_grava(entrada: Any) -> None:  # A-4, cenário 98
    _, produto, _ = cenario("10")
    a = ContaFactory.create()
    parcela = pendente(a, produto, 4)
    if entrada == "5":
        with pytest.raises(RemocaoAcimaDoPendente) as erro:
            remover_pendente(a, produto, entrada)
        assert erro.value.mensagem == "A remoção passa da quantidade pendente (4)."
    else:
        with pytest.raises(QuantidadeInvalida):
            remover_pendente(a, produto, entrada)
    assert estado(parcela) == (SituacaoParcela.PENDENTE, D("0"), D("4"))
    assert auditorias(ACAO) == []


@pytest.mark.parametrize(
    "etapa",
    [Etapa.PAGAMENTO, Etapa.FECHAMENTO_ENCERRADO, Etapa.CANCELADA, Etapa.AGUARDANDO_FORNECEDOR],
)
def test_remocao_vale_em_qualquer_etapa(etapa: str) -> None:  # A-5
    _, produto, _ = cenario("10", etapa=etapa)
    a = ContaFactory.create()
    parcela = pendente(a, produto, 4)
    resumo = remover_pendente(a, produto, "1")
    assert resumo.pendente == D("3")
    assert estado(parcela) == (SituacaoParcela.PENDENTE, D("0"), D("3"))


@pytest.mark.acceptance
def test_parcela_em_pedido_nao_entra_na_remocao() -> None:  # A-6, cenário 99
    _, produto, _ = cenario("10")
    a = ContaFactory.create()
    parcela = ParcelaFactory.create(
        comprador=a,
        produto=produto,
        quantidade_original=D("6"),
        quantidade_reservada=D("4"),
        quantidade_pendente=D("2"),
        situacao=SituacaoParcela.EM_PEDIDO,
    )
    with pytest.raises(RemocaoAcimaDoPendente) as erro:
        remover_pendente(a, produto, "2")
    assert erro.value.pendente == 0
    assert estado(parcela) == (SituacaoParcela.EM_PEDIDO, D("4"), D("2"))
    assert auditorias(ACAO) == []


def test_so_comprador_ativo_remove_pendente() -> None:  # A-7
    _, produto, _ = cenario("10")
    suspenso = ContaFactory.create(suspensa=True)
    parcela = pendente(suspenso, produto, 3)
    fornecedor = ContaFactory.create(fornecedor=True)
    for conta in (suspenso, fornecedor):
        with pytest.raises(PermissionDenied):
            remover_pendente(conta, produto, "1")
    assert estado(parcela) == (SituacaoParcela.PENDENTE, D("0"), D("3"))
    assert EntradaAuditoria.objects.filter(acao=ACAO).count() == 0


def test_remover_pendente_nao_libera_nem_reserva_estoque() -> None:  # A-8
    _, produto, _ = cenario("10")
    reservada(ContaFactory.create(), produto, 2)
    a = ContaFactory.create()
    pendente(a, produto, 4)
    remover_pendente(a, produto, "4")
    assert total_reservado(produto) == D("2")
    assert auditorias("interesse.alocar_pendentes") == []
    assert [p.situacao for p in parcelas(produto, a)] == [SituacaoParcela.REMOVIDA]
