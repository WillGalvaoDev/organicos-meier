"""Apoio dos testes de pedidos (E08): o arranjo comum da abertura do pagamento.

Fornecedor F (mínimo R$ 100,00), rodada com o fechamento encerrado, `P1` a R$ 10,00 sem múltiplo
e `P2` a R$ 5,00 com múltiplo 6. O comprador A tem 6 de `P1` e 4 de `P2`; o comprador B tem 5 de
`P1` e 8 de `P2`, sendo 2 delas numa segunda parcela. A ordem das parcelas de `P2` é A com 4, B
com 6 e B com 2 (duas caixas). `pendente_a_p1` acrescenta pendentes à parcela de A em `P1`. O
relógio deve estar congelado antes de montar o arranjo.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from apps.catalogo.models import Produto, Unidade
from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.pedidos.abertura import ResultadoDaAbertura, abrir_pagamento
from apps.pedidos.models import AberturaDoPagamento, Pedido
from apps.rodadas.models import Ciclo, Etapa, Rodada
from tests.apoio.ciclos import dar_prazo_de_teste
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ParcelaFactory,
    ProdutoFactory,
    RodadaFactory,
)

D = Decimal
T0 = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)


@dataclass
class Arranjo:
    fornecedor: Fornecedor
    rodada: Rodada
    ciclo: Ciclo
    p1: Produto
    p2: Produto
    a: Conta
    b: Conta
    admin: Conta


def administrador() -> Conta:
    return Conta.objects.get(papel=Papel.ADMINISTRADOR)


def montar_arranjo(*, minimo: str = "100.00", pendente_a_p1: int = 0) -> Arranjo:
    fornecedor = FornecedorFactory.create(nome="F", minimo=D(minimo))
    rodada = RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.FECHAMENTO_ENCERRADO)
    ciclo = dar_prazo_de_teste(rodada).ciclo
    p1 = ProdutoFactory.create(
        fornecedor=fornecedor, nome="P1", unidade=Unidade.UNIDADE, preco=D("10.00")
    )
    p2 = ProdutoFactory.create(
        fornecedor=fornecedor,
        nome="P2",
        unidade=Unidade.UNIDADE,
        preco=D("5.00"),
        multiplo=D("6.000"),
    )
    for produto in (p1, p2):
        EstoqueDaRodadaFactory.create(rodada=rodada, produto=produto, limite=None)
    a = ContaFactory.create(nome="Comprador A")
    b = ContaFactory.create(nome="Comprador B")
    for comprador, produto, quantidade in (
        (a, p1, 6),
        (b, p1, 5),
        (a, p2, 4),
        (b, p2, 6),
        (b, p2, 2),
    ):
        pendente = pendente_a_p1 if (comprador, produto) == (a, p1) else 0
        ParcelaFactory.create(
            comprador=comprador,
            produto=produto,
            quantidade_original=D(quantidade + pendente),
            quantidade_reservada=D(quantidade),
            quantidade_pendente=D(pendente),
        )
    return Arranjo(fornecedor, rodada, ciclo, p1, p2, a, b, administrador())


def abrir(arranjo: Arranjo, frete: str = "22.00") -> ResultadoDaAbertura:
    return abrir_pagamento(arranjo.admin, arranjo.rodada, D(frete))


def pedido_de(comprador: Conta) -> Pedido:
    pedidos: list[Pedido] = list(Pedido.objects.filter(comprador=comprador))
    assert len(pedidos) == 1, f"pedidos do comprador: {len(pedidos)}"
    return pedidos[0]


def abertura_unica() -> AberturaDoPagamento:
    aberturas: list[AberturaDoPagamento] = list(AberturaDoPagamento.objects.all())
    assert len(aberturas) == 1, f"aberturas: {len(aberturas)}"
    return aberturas[0]
