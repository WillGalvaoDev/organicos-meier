"""Cálculo dos valores da cobrança (E08-01).

Função pura, sem banco: produtos, serviço de 5%, parte do frete e total de cada comprador.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from apps.catalogo.quantidades import calcular_subtotal
from apps.nucleo.valores import arredondar_centavos

TAXA_DE_SERVICO = Decimal("0.05")


@dataclass(frozen=True)
class ItemACobrar:
    produto_id: int
    preco_unitario: Decimal
    quantidade: Decimal


@dataclass(frozen=True)
class CompradorACobrar:
    comprador_id: int
    itens: tuple[ItemACobrar, ...]


@dataclass(frozen=True)
class ItemCobrado:
    produto_id: int
    preco_unitario: Decimal
    quantidade: Decimal
    subtotal: Decimal


@dataclass(frozen=True)
class CobrancaDoComprador:
    comprador_id: int
    itens: tuple[ItemCobrado, ...]
    produtos: Decimal
    servico: Decimal
    frete: Decimal
    total: Decimal


_CENTAVO = Decimal("0.01")


def _decimal_com_casas(valor: object, casas: int, nome: str) -> Decimal:
    if isinstance(valor, bool) or not isinstance(valor, Decimal):
        raise ValueError(f"{nome} deve ser Decimal")
    if not valor.is_finite():
        raise ValueError(f"{nome} deve ser finito")
    _, digitos, expoente = valor.as_tuple()
    excedentes = -int(expoente) - casas
    if excedentes > 0 and any(digitos[-excedentes:]):
        raise ValueError(f"{nome} com mais de {casas} casas decimais")
    return valor


def _validar(compradores: Sequence[CompradorACobrar], frete: object) -> Decimal:
    valor_do_frete = _decimal_com_casas(frete, 2, "frete")
    if valor_do_frete < 0:
        raise ValueError("frete negativo")
    if not compradores:
        raise ValueError("nenhum comprador")
    vistos: set[int] = set()
    for comprador in compradores:
        if comprador.comprador_id in vistos:
            raise ValueError(f"comprador repetido: {comprador.comprador_id}")
        vistos.add(comprador.comprador_id)
        if not comprador.itens:
            raise ValueError(f"comprador {comprador.comprador_id} sem item")
        produtos: set[int] = set()
        for item in comprador.itens:
            if item.produto_id in produtos:
                raise ValueError(f"produto repetido: {item.produto_id}")
            produtos.add(item.produto_id)
            if _decimal_com_casas(item.preco_unitario, 2, "preço") < 0:
                raise ValueError("preço negativo")
            if _decimal_com_casas(item.quantidade, 3, "quantidade") <= 0:
                raise ValueError("quantidade deve ser maior que zero")
    return valor_do_frete


def _ratear_frete(produtos: dict[int, Decimal], frete: Decimal) -> dict[int, Decimal]:
    """Maior resto: cada um recebe `F * P / T` truncado a centavos; os centavos que faltam vão,
    um a um, aos de maior resto, e no empate ao de menor `comprador_id`."""
    total = sum(produtos.values(), Decimal(0))
    partes: dict[int, Decimal] = {}
    restos: dict[int, Decimal] = {}
    for comprador_id, p in produtos.items():
        exato = frete * p / total
        partes[comprador_id] = exato.quantize(_CENTAVO, rounding=ROUND_DOWN)
        restos[comprador_id] = exato - partes[comprador_id]
    faltam = int((frete - sum(partes.values(), Decimal(0))) / _CENTAVO)
    ordem = sorted(restos, key=lambda c: (-restos[c], c))
    for comprador_id in ordem[:faltam]:
        partes[comprador_id] += _CENTAVO
    return partes


def calcular_cobranca(
    compradores: Sequence[CompradorACobrar], frete: Decimal
) -> list[CobrancaDoComprador]:
    """Valores congelados de cada comprador: produtos (P), serviço de 5%, parte do frete e total.

    `ValueError`, sem resultado parcial, para entrada inválida. Não lê o banco e não depende da
    ordem da entrada; a saída vem em ordem de `comprador_id`.
    """
    valor_do_frete = _validar(compradores, frete)
    itens_por_comprador: dict[int, tuple[ItemCobrado, ...]] = {}
    produtos: dict[int, Decimal] = {}
    for comprador in sorted(compradores, key=lambda c: c.comprador_id):
        itens = tuple(
            ItemCobrado(
                i.produto_id,
                i.preco_unitario,
                i.quantidade,
                calcular_subtotal(i.preco_unitario, i.quantidade),
            )
            for i in sorted(comprador.itens, key=lambda i: i.produto_id)
        )
        itens_por_comprador[comprador.comprador_id] = itens
        produtos[comprador.comprador_id] = sum((i.subtotal for i in itens), Decimal("0.00"))
    if sum(produtos.values(), Decimal(0)) <= 0:
        raise ValueError("o total dos produtos deve ser maior que zero")
    fretes = _ratear_frete(produtos, valor_do_frete)
    resultado = []
    for comprador_id, p in produtos.items():
        servico = arredondar_centavos(p * TAXA_DE_SERVICO)
        parte = fretes[comprador_id]
        resultado.append(
            CobrancaDoComprador(
                comprador_id,
                itens_por_comprador[comprador_id],
                p,
                servico,
                parte,
                p + servico + parte,
            )
        )
    return resultado
