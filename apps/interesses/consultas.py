"""Leituras das parcelas de um produto (E03-04).

Com `travar=True` (dentro de `transaction.atomic()`), as linhas lidas são travadas com
`FOR UPDATE`, em ordem de `sequencia`: é a forma de a E03-05 e a E03-06 decidirem sobre o
estoque e o incremento sem corrida com as operações de interesse.
"""

from decimal import Decimal

from django.db.models import QuerySet, Sum

from apps.catalogo.models import Produto
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela

_ZERO = Decimal("0.000")
_RESERVAM = (SituacaoParcela.ATIVA, SituacaoParcela.EM_PEDIDO)


def _parcelas(produto: Produto, travar: bool) -> QuerySet[ParcelaDeInteresse]:
    parcelas = ParcelaDeInteresse.objects.filter(produto_id=produto.pk).order_by("sequencia")
    return parcelas.select_for_update() if travar else parcelas


def total_reservado(produto: Produto, *, travar: bool = False) -> Decimal:
    """Soma da reserva das parcelas `ativa` ou `em_pedido` do produto (a que o estoque cobre)."""
    parcelas = _parcelas(produto, travar).filter(situacao__in=_RESERVAM)
    if travar:
        total = sum(parcelas.values_list("quantidade_reservada", flat=True), _ZERO)
    else:
        total = parcelas.order_by().aggregate(total=Sum("quantidade_reservada"))["total"] or _ZERO
    return total.quantize(_ZERO)


def quantidades_em_uso(produto: Produto, *, travar: bool = False) -> list[Decimal]:
    """Reservas e pendências maiores que zero das parcelas do produto que não foram removidas."""
    parcelas = _parcelas(produto, travar).exclude(situacao=SituacaoParcela.REMOVIDA)
    em_uso: list[Decimal] = []
    for reservada, pendente in parcelas.values_list("quantidade_reservada", "quantidade_pendente"):
        em_uso.extend(quantidade for quantidade in (reservada, pendente) if quantidade > 0)
    return em_uso
