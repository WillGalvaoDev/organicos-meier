"""Produtos de um fornecedor (E03-03). Imutabilidade no banco: ver `imutavel.py`."""

from decimal import Decimal

from django.db import models
from django.db.models import F, Value
from django.db.models.functions import Mod, NullIf
from django.db.models.lookups import Exact

from apps.fornecedores.models import Fornecedor
from apps.nucleo.tempo import agora
from apps.nucleo.valores import CampoDinheiro, CampoQuantidade

_QTD = CampoQuantidade()
_ZERO = Value(0, output_field=_QTD)


class Unidade(models.TextChoices):
    UNIDADE = "unidade", "unidade"
    PACOTE = "pacote", "pacote"
    CAIXA = "caixa", "caixa"
    KG = "kg", "kg"
    LITRO = "litro", "L"


class Produto(models.Model):
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, related_name="produtos")
    nome = models.CharField(max_length=150)
    descricao = models.TextField(max_length=2000, blank=True, default="")
    unidade = models.CharField(max_length=10, choices=Unidade.choices)
    incremento = CampoQuantidade()
    preco = CampoDinheiro()
    multiplo = CampoQuantidade(null=True, blank=True)
    disponivel = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=agora)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=models.Q(incremento__gt=0), name="produto_incremento_positivo"
            ),
            models.CheckConstraint(
                condition=models.Q(preco__gte=Decimal("0.01")), name="produto_preco_minimo"
            ),
            # NULLIF evita divisão por zero se o incremento inválido chegar junto com um múltiplo;
            # a recusa do incremento fica por conta da restrição acima.
            models.CheckConstraint(
                condition=models.Q(multiplo__isnull=True)
                | (
                    models.Q(multiplo__gt=0)
                    & models.Q(
                        Exact(
                            Mod(F("multiplo"), NullIf(F("incremento"), _ZERO), output_field=_QTD),
                            _ZERO,
                        )
                    )
                ),
                name="produto_multiplo_divisivel",
            ),
        )

    def __str__(self) -> str:
        return self.nome
