"""Parcela de interesse (E03-04). Andaime: campos, sem restrições nem sequência do banco."""

from typing import Any

from django.db import models
from django.db.models import F

from apps.catalogo.models import Produto
from apps.contas.models import Conta
from apps.nucleo.tempo import agora
from apps.nucleo.valores import CampoQuantidade


class SituacaoParcela(models.TextChoices):
    ATIVA = "ativa", "Ativa"
    EM_PEDIDO = "em_pedido", "Em pedido"
    PENDENTE = "pendente", "Pendente"
    REMOVIDA = "removida", "Removida"


class ParcelaDeInteresse(models.Model):
    # O valor real vem do banco: a trigger de inserção sempre grava `nextval` da sequência
    # `interesses_parcela_sequencia`; o `0` é só o marcador do DEFAULT (ver `gatilhos.py`).
    sequencia = models.BigIntegerField(unique=True, editable=False, db_default=0)
    comprador = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="+")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="parcelas")
    quantidade_original = CampoQuantidade()
    quantidade_reservada = CampoQuantidade()
    quantidade_pendente = CampoQuantidade()
    situacao = models.CharField(max_length=10, choices=SituacaoParcela.choices)
    criada_em = models.DateTimeField(default=agora)

    class Meta:
        db_table = "interesses_parcela"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(quantidade_original__gt=0),
                name="parcela_original_positiva",
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade_reservada__gte=0, quantidade_pendente__gte=0),
                name="parcela_quantidades_nao_negativas",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    quantidade_original__gte=F("quantidade_reservada") + F("quantidade_pendente")
                ),
                name="parcela_reservada_mais_pendente_ate_original",
            ),
            models.CheckConstraint(
                condition=~models.Q(situacao="removida")
                | models.Q(quantidade_reservada=0, quantidade_pendente=0),
                name="parcela_removida_sem_quantidades",
            ),
            models.CheckConstraint(
                condition=~models.Q(situacao="pendente") | models.Q(quantidade_reservada=0),
                name="parcela_pendente_sem_reserva",
            ),
            models.CheckConstraint(
                condition=models.Q(situacao__in=SituacaoParcela.values),
                name="parcela_situacao_valida",
            ),
        )

    def __str__(self) -> str:
        return f"parcela {self.pk}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        adicionando = self._state.adding
        super().save(*args, **kwargs)
        if adicionando:
            # A sequência é do banco (trigger de inserção): relê, pois um valor informado pela
            # aplicação é ignorado e o objeto em memória não pode ficar com ele.
            self.refresh_from_db(fields=["sequencia"])
