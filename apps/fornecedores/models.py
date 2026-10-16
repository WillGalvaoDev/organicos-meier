from decimal import Decimal

from django.db import models

from apps.nucleo.tempo import agora
from apps.nucleo.valores import CampoDinheiro


class Fornecedor(models.Model):
    """Fornecedor (E02-01 criou o nome; E03-01 acrescenta os dados funcionais)."""

    nome = models.CharField(max_length=150)
    email_pedido = models.CharField(max_length=254)
    minimo = CampoDinheiro()
    prazo_entrega_dias = models.PositiveSmallIntegerField()
    informacoes_frete = models.TextField(max_length=1000, blank=True, default="")
    criado_em = models.DateTimeField(default=agora)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=models.Q(minimo__gte=Decimal("0.01")), name="fornecedor_minimo_positivo"
            ),
            models.CheckConstraint(
                condition=models.Q(prazo_entrega_dias__gte=1, prazo_entrega_dias__lte=365),
                name="fornecedor_prazo_valido",
            ),
        )

    def __str__(self) -> str:
        return self.nome
