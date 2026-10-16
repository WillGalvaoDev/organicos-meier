"""Rodadas de compra coletiva (E03-02). Uma rodada ativa por fornecedor."""

from django.db import models

from apps.catalogo.models import Produto
from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.nucleo.tempo import agora
from apps.nucleo.valores import CampoQuantidade


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


class EstoqueDaRodada(models.Model):
    """Produto incluído na rodada, com o limite de estoque (nulo = sem limite)."""

    rodada = models.ForeignKey(Rodada, on_delete=models.PROTECT, related_name="estoques")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="+")
    limite = CampoQuantidade(null=True, blank=True)
    incluido_em = models.DateTimeField(default=agora)

    class Meta:
        db_table = "rodadas_estoque"
        constraints = (
            models.UniqueConstraint(fields=["rodada", "produto"], name="estoque_produto_unico"),
            models.CheckConstraint(
                condition=models.Q(limite__isnull=True) | models.Q(limite__gte=0),
                name="estoque_limite_nao_negativo",
            ),
        )

    def __str__(self) -> str:
        return f"estoque {self.pk}"
