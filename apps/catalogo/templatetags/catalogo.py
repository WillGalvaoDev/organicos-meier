from decimal import Decimal
from typing import Any

from django import template

from apps.catalogo.quantidades import formatar_quantidade

register = template.Library()


@register.filter
def quantidade_br(valor: Any) -> str:
    """Quantidade sem zeros à direita e com vírgula; vazio quando não há valor."""
    if valor is None or valor == "":
        return ""
    return formatar_quantidade(valor if isinstance(valor, Decimal) else Decimal(str(valor)))
