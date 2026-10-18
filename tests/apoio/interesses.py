"""Apoio dos testes de interesse (E05): cenário de rodada com produto e utilitários de leitura."""

from decimal import Decimal
from typing import Any

from apps.catalogo.models import Produto, Unidade
from apps.contas.models import Conta
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.models import EstoqueDaRodada, Etapa, Rodada
from tests.fabricas import EstoqueDaRodadaFactory, ParcelaFactory, ProdutoFactory, RodadaFactory

D = Decimal


def cenario(
    limite: str | None = "10", etapa: str = Etapa.INTERESSE, **produto: Any
) -> tuple[Rodada, Produto, EstoqueDaRodada]:
    """Rodada do fornecedor com um produto em unidade (incremento 1) e o estoque dele."""
    rodada = RodadaFactory.create(etapa=etapa)
    campos = {"unidade": Unidade.UNIDADE, **produto}
    item = ProdutoFactory.create(fornecedor=rodada.fornecedor, **campos)
    estoque = EstoqueDaRodadaFactory.create(
        rodada=rodada, produto=item, limite=None if limite is None else D(limite)
    )
    return rodada, item, estoque


def parcelas(produto: Produto, comprador: Conta | None = None) -> list[ParcelaDeInteresse]:
    consulta = ParcelaDeInteresse.objects.filter(produto=produto).order_by("sequencia")
    return list(consulta.filter(comprador=comprador) if comprador else consulta)


def auditorias(acao: str) -> list[EntradaAuditoria]:
    return list(EntradaAuditoria.objects.filter(acao=acao).order_by("id"))


def reservada(comprador: Conta, produto: Produto, quantidade: int | str) -> ParcelaDeInteresse:
    """Parcela ativa toda reservada, criada por fábrica (sem passar pelos serviços)."""
    valor = D(quantidade)
    return ParcelaFactory.create(
        comprador=comprador,
        produto=produto,
        quantidade_original=valor,
        quantidade_reservada=valor,
    )


def pendente(comprador: Conta, produto: Produto, quantidade: int | str) -> ParcelaDeInteresse:
    """Parcela `pendente`, sem reserva, criada por fábrica."""
    valor = D(quantidade)
    return ParcelaFactory.create(
        comprador=comprador,
        produto=produto,
        quantidade_original=valor,
        quantidade_reservada=D(0),
        quantidade_pendente=valor,
        situacao=SituacaoParcela.PENDENTE,
    )
