"""Pedidos congelados na abertura do pagamento (E08-02).

A composição do pedido (abertura, pedidos, itens e parcelas) só aceita inserção, no banco e na
aplicação. A situação de cada pedido fica em `SituacaoDoPedido`, a única tabela alterável, e muda
só pelos serviços.
"""

import logging
from typing import Any

from django.db import models
from django.db.models import F, Q

from apps.catalogo.models import Produto, Unidade
from apps.contas.models import Conta
from apps.interesses.models import ParcelaDeInteresse
from apps.nucleo.so_insercao import RegistroSoInsercao, SoInsercaoQuerySet
from apps.nucleo.valores import CampoDinheiro, CampoQuantidade
from apps.pagamentos.models import PagamentoNoProvedor
from apps.rodadas.models import Ciclo, Rodada

logger = logging.getLogger(__name__)


def _registrar_tentativa(modelo: str, pk: object) -> None:
    logger.warning("Tentativa de alterar pedido congelado: %s %s", modelo, pk)


class _QuerySetDoPedido(SoInsercaoQuerySet):
    """Recusa a operação em lote e registra uma tentativa por registro atingido."""

    def _registrar(self) -> None:
        for pk in list(self.values_list("pk", flat=True)):
            _registrar_tentativa(self.model.__name__, pk)

    def update(self, **kwargs: Any) -> int:
        self._registrar()
        return super().update(**kwargs)

    def delete(self) -> tuple[int, dict[str, int]]:
        self._registrar()
        return super().delete()

    def bulk_update(self, objs: Any, *args: Any, **kwargs: Any) -> int:
        for objeto in objs:
            _registrar_tentativa(type(objeto).__name__, objeto.pk)
        return super().bulk_update(objs, *args, **kwargs)


class RegistroDoPedido(RegistroSoInsercao):
    """Composição do pedido: só inserção, e cada tentativa de alterar é registrada no log."""

    objects = _QuerySetDoPedido.as_manager()  # type: ignore[misc]

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            _registrar_tentativa(type(self).__name__, self.pk)
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        _registrar_tentativa(type(self).__name__, self.pk)
        return super().delete(*args, **kwargs)


class AberturaDoPagamento(RegistroDoPedido):
    ciclo = models.OneToOneField(Ciclo, on_delete=models.PROTECT, related_name="abertura")
    rodada = models.ForeignKey(Rodada, on_delete=models.PROTECT, related_name="aberturas")
    t0 = models.DateTimeField()
    frete = CampoDinheiro()
    total_produtos = CampoDinheiro()
    autor = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = (
            models.CheckConstraint(condition=Q(frete__gte=0), name="abertura_frete_nao_negativo"),
            models.CheckConstraint(
                condition=Q(total_produtos__gt=0), name="abertura_total_produtos_positivo"
            ),
        )

    def __str__(self) -> str:
        return f"abertura {self.pk}"


class Pedido(RegistroDoPedido):
    abertura = models.ForeignKey(
        AberturaDoPagamento, on_delete=models.PROTECT, related_name="pedidos"
    )
    comprador = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="pedidos")
    produtos = CampoDinheiro()
    servico = CampoDinheiro()
    frete = CampoDinheiro()
    total = CampoDinheiro()

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["abertura", "comprador"], name="pedido_unico"),
            models.CheckConstraint(
                condition=Q(total=F("produtos") + F("servico") + F("frete")),
                name="pedido_total_e_a_soma",
            ),
            models.CheckConstraint(condition=Q(produtos__gt=0), name="pedido_produtos_positivo"),
            models.CheckConstraint(condition=Q(servico__gte=0), name="pedido_servico_nao_negativo"),
            models.CheckConstraint(condition=Q(frete__gte=0), name="pedido_frete_nao_negativo"),
        )

    def __str__(self) -> str:
        return f"pedido {self.pk}"


class ItemDoPedido(RegistroDoPedido):
    pedido = models.ForeignKey(Pedido, on_delete=models.PROTECT, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="+")
    nome = models.CharField(max_length=150)
    unidade = models.CharField(max_length=10, choices=Unidade.choices)
    incremento = CampoQuantidade()
    multiplo = CampoQuantidade(null=True, blank=True)
    preco_unitario = CampoDinheiro()
    quantidade = CampoQuantidade()
    subtotal = CampoDinheiro()

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["pedido", "produto"], name="item_unico"),
            models.CheckConstraint(condition=Q(quantidade__gt=0), name="item_quantidade_positiva"),
            models.CheckConstraint(condition=Q(subtotal__gte=0), name="item_subtotal_nao_negativo"),
        )

    def __str__(self) -> str:
        return f"item {self.pk}"


class ParcelaNoPedido(RegistroDoPedido):
    item = models.ForeignKey(ItemDoPedido, on_delete=models.PROTECT, related_name="parcelas")
    parcela = models.ForeignKey(ParcelaDeInteresse, on_delete=models.PROTECT, related_name="+")
    caixa = models.PositiveIntegerField(null=True, blank=True)
    quantidade = CampoQuantidade()

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["item", "parcela", "caixa"],
                name="parcela_no_pedido_unica",
                nulls_distinct=False,
            ),
            models.CheckConstraint(
                condition=Q(caixa__isnull=True) | Q(caixa__gte=1), name="parcela_caixa_positiva"
            ),
            models.CheckConstraint(
                condition=Q(quantidade__gt=0), name="parcela_no_pedido_quantidade_positiva"
            ),
        )

    def __str__(self) -> str:
        return f"parcela no pedido {self.pk}"


class SituacaoDePagamento(models.TextChoices):
    AGUARDANDO_PAGAMENTO = "aguardando_pagamento", "Aguardando pagamento"
    PAGO = "pago", "Pago"
    CANCELADO = "cancelado", "Cancelado"


class MotivoDoCancelamento(models.TextChoices):
    SUSPENSAO = "suspensao", "Suspensão da conta"
    REMOCAO_DA_CONTA = "remocao_da_conta", "Remoção da conta"


class SituacaoDoPedido(models.Model):
    pedido = models.OneToOneField(Pedido, on_delete=models.PROTECT, related_name="estado")
    situacao = models.CharField(max_length=20, choices=SituacaoDePagamento.choices)
    quitado_por = models.OneToOneField(
        PagamentoNoProvedor, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    quitado_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    motivo_do_cancelamento = models.CharField(
        max_length=20, choices=MotivoDoCancelamento.choices, blank=True, default=""
    )

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=(
                    Q(
                        situacao="aguardando_pagamento",
                        quitado_por__isnull=True,
                        quitado_em__isnull=True,
                        cancelado_em__isnull=True,
                        motivo_do_cancelamento="",
                    )
                    | Q(
                        situacao="pago",
                        quitado_por__isnull=False,
                        quitado_em__isnull=False,
                        cancelado_em__isnull=True,
                        motivo_do_cancelamento="",
                    )
                    | Q(
                        situacao="cancelado",
                        quitado_por__isnull=True,
                        quitado_em__isnull=True,
                        cancelado_em__isnull=False,
                        motivo_do_cancelamento__in=MotivoDoCancelamento.values,
                    )
                ),
                name="situacao_do_pedido_coerente",
            ),
        )

    def __str__(self) -> str:
        return f"situação do pedido {self.pedido_id}"
