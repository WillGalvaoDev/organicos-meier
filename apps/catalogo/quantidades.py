"""Validação de incremento, múltiplo e quantidade, e subtotal (E03-03).

Aritmética decimal exata sobre `apps.nucleo.valores`: nada de `float`. `validar_quantidade` é o
ponto único de validação de quantidade contra o incremento do produto.
"""

from decimal import Decimal
from typing import Any

from apps.catalogo.models import Produto
from apps.nucleo.valores import ValorInvalido, arredondar_centavos, eh_multiplo, quantidade


class QuantidadeRecusada(Exception):
    """Base das recusas de incremento, múltiplo e quantidade."""


class IncrementoInvalido(QuantidadeRecusada):
    pass


class MultiploInvalido(QuantidadeRecusada):
    pass


class QuantidadeInvalida(QuantidadeRecusada):
    pass


_MSG_INCREMENTO = "O incremento deve ser maior que zero, com até três casas decimais."
_MSG_MULTIPLO = "O múltiplo deve ser maior que zero e divisível exatamente pelo incremento."
_MSG_QUANTIDADE = "A quantidade deve ser maior que zero e múltipla do incremento do produto."


def validar_incremento(entrada: Any) -> Decimal:
    try:
        valor = quantidade(entrada)
    except ValorInvalido:
        raise IncrementoInvalido(_MSG_INCREMENTO) from None
    if valor <= 0:
        raise IncrementoInvalido(_MSG_INCREMENTO)
    return valor


def validar_multiplo(entrada: Any, incremento: Decimal) -> Decimal | None:
    """Vazio (`None` ou texto vazio) significa sem múltiplo."""
    if entrada is None or (isinstance(entrada, str) and not entrada.strip()):
        return None
    try:
        valor = quantidade(entrada)
        if valor <= 0 or not eh_multiplo(valor, incremento):
            raise MultiploInvalido(_MSG_MULTIPLO)
    except ValorInvalido:
        raise MultiploInvalido(_MSG_MULTIPLO) from None
    return valor


def validar_quantidade(produto: Produto, entrada: Any) -> Decimal:
    try:
        valor = quantidade(entrada)
        if valor <= 0 or not eh_multiplo(valor, produto.incremento):
            raise QuantidadeInvalida(_MSG_QUANTIDADE)
    except ValorInvalido:
        raise QuantidadeInvalida(_MSG_QUANTIDADE) from None
    return valor


def calcular_subtotal(preco: Decimal, quantidade: Decimal) -> Decimal:
    """Preço vezes quantidade, arredondado uma única vez para centavos (ROUND_HALF_UP)."""
    for parte in (preco, quantidade):
        if not isinstance(parte, Decimal):
            raise ValorInvalido(f"tipo não aceito: {type(parte).__name__}")
    return arredondar_centavos(preco * quantidade)


def formatar_quantidade(valor: Decimal) -> str:
    """Exibição com vírgula e sem zeros à direita: 0,25, 1, 1,5."""
    return format(valor.normalize(), "f").replace(".", ",")
