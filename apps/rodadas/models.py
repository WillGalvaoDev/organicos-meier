"""Rodadas de compra coletiva (E03-02). Uma rodada ativa por fornecedor."""

from django.db import models

from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.nucleo.tempo import agora


class Etapa(models.TextChoices):
    INTERESSE = "interesse", "Interesse"
    FECHAMENTO = "fechamento", "Fechamento"
    FECHAMENTO_ENCERRADO = "fechamento_encerrado", "Fechamento com prazo encerrado"
    PAGAMENTO = "pagamento", "Pagamento"
    AGUARDANDO_FORNECEDOR = "aguardando_fornecedor", "Aguardando fornecedor"
    DISPONIVEL_PARA_RETIRADA = "disponivel_para_retirada", "Disponível para retirada"
    CANCELADA = "cancelada", "Cancelada"


ETAPAS_ATIVAS = (
    Etapa.INTERESSE,
    Etapa.FECHAMENTO,
    Etapa.FECHAMENTO_ENCERRADO,
    Etapa.PAGAMENTO,
    Etapa.AGUARDANDO_FORNECEDOR,
)


class Rodada(models.Model):
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, related_name="rodadas")
    etapa = models.CharField(max_length=30, choices=Etapa.choices, default=Etapa.INTERESSE)
    aberta_em = models.DateTimeField(default=agora)
    aberta_por = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["fornecedor"],
                condition=models.Q(etapa__in=ETAPAS_ATIVAS),
                name="rodada_ativa_unica_por_fornecedor",
            ),
        )

    def __str__(self) -> str:
        return f"rodada {self.pk}"
