"""Valores monetários e quantidades decimais (E01-02).

Aritmética decimal exata, sem ponto flutuante. Toda recusa levanta `ValorInvalido`.
"""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

_CENTAVO = Decimal("0.01")
_TEXTO_DECIMAL = re.compile(r"[+-]?\d+(\.\d+)?")


class ValorInvalido(Exception):
    """Entrada numérica recusada. A mensagem identifica o motivo, sem dados pessoais."""


def _converter(entrada: object, casas: int) -> Decimal:
    if isinstance(entrada, bool | float | int):
        raise ValorInvalido(f"tipo não aceito: {type(entrada).__name__}")
    if isinstance(entrada, str):
        if not _TEXTO_DECIMAL.fullmatch(entrada):
            raise ValorInvalido("texto não é um decimal com ponto separador")
        valor = Decimal(entrada)
    elif isinstance(entrada, Decimal):
        valor = entrada
    else:
        raise ValorInvalido(f"tipo não aceito: {type(entrada).__name__}")
    if not valor.is_finite():
        raise ValorInvalido("valor não finito")
    expoente = valor.normalize().as_tuple().exponent
    if isinstance(expoente, int) and expoente < -casas:
        raise ValorInvalido(f"mais de {casas} casas decimais")
    try:
        return valor.quantize(Decimal(1).scaleb(-casas))
    except InvalidOperation:
        raise ValorInvalido("valor fora da faixa suportada") from None


def dinheiro(entrada: str | Decimal) -> Decimal:
    """Converte texto decimal (ponto) ou `Decimal` em dinheiro com duas casas."""
    return _converter(entrada, 2)


def quantidade(entrada: str | Decimal) -> Decimal:
    """Converte texto decimal (ponto) ou `Decimal` em quantidade com até três casas."""
    return _converter(entrada, 3)


def arredondar_centavos(valor: Decimal) -> Decimal:
    """Arredonda a centavos com ROUND_HALF_UP. Aceita só `Decimal`."""
    if not isinstance(valor, Decimal):
        raise ValorInvalido(f"tipo não aceito: {type(valor).__name__}")
    if not valor.is_finite():
        raise ValorInvalido("valor não finito")
    try:
        return valor.quantize(_CENTAVO, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValorInvalido("valor fora da faixa suportada") from None


def eh_multiplo(valor: Decimal, passo: Decimal) -> bool:
    """Verdadeiro quando `valor` é múltiplo inteiro de `passo`, em aritmética exata."""
    for parte in (valor, passo):
        if not isinstance(parte, Decimal):
            raise ValorInvalido(f"tipo não aceito: {type(parte).__name__}")
        if not parte.is_finite():
            raise ValorInvalido("valor não finito")
    if passo <= 0:
        raise ValorInvalido("passo deve ser maior que zero")
    # Precisão ampla: o resto é exato para qualquer faixa usada pelo negócio.
    with localcontext() as contexto:
        contexto.prec = 100
        try:
            return valor % passo == 0
        except InvalidOperation:
            raise ValorInvalido("valor fora da faixa suportada") from None


class _CampoDecimalExato(models.DecimalField):  # type: ignore[type-arg]
    """DecimalField de precisão fixa que recusa `float` na validação."""

    _max_digits = 0
    _decimal_places = 0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["max_digits"] = self._max_digits
        kwargs["decimal_places"] = self._decimal_places
        super().__init__(*args, **kwargs)

    def deconstruct(self) -> Any:
        nome, caminho, args, kwargs = super().deconstruct()
        kwargs.pop("max_digits", None)
        kwargs.pop("decimal_places", None)
        return nome, caminho, args, kwargs

    def to_python(self, value: Any) -> Any:
        if isinstance(value, float):
            raise ValidationError(
                "Ponto flutuante não é aceito; use texto ou Decimal.", code="float"
            )
        return super().to_python(value)


class CampoDinheiro(_CampoDecimalExato):
    """Dinheiro: NUMERIC(12,2)."""

    _max_digits = 12
    _decimal_places = 2


class CampoQuantidade(_CampoDecimalExato):
    """Quantidade: NUMERIC(12,3)."""

    _max_digits = 12
    _decimal_places = 3
