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
from apps.nucleo.tempo import agora
from apps.nucleo.valores import CampoDinheiro, CampoQuantidade
from apps.pagamentos.models import PAGAMENTO_REGISTRADO
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

    @property
    def referencia_externa(self) -> str:
        """Identifica o pedido e o ciclo no provedor; é igual em todas as tentativas (E08-03)."""
        return f"om-c{self.abertura.ciclo_id}-p{self.pk}"

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
        PAGAMENTO_REGISTRADO, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
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


class SituacaoDaTentativa(models.TextChoices):
    SOLICITADA = "solicitada", "Solicitada"
    CRIADA = "criada", "Criada"
    NAO_CRIADA = "nao_criada", "Não criada"


class TentativaDePagamento(models.Model):
    """Uma vez que o comprador pede para pagar (E08-03). Guarda a chave de idempotência da
    cobrança no provedor e, depois de criada, os dados para pagar, que só o dono do pedido vê."""

    pedido = models.ForeignKey(Pedido, on_delete=models.PROTECT, related_name="tentativas")
    numero = models.PositiveIntegerField()
    chave_idempotencia = models.CharField(max_length=64, unique=True)
    referencia_externa = models.CharField(max_length=64)
    situacao = models.CharField(max_length=12, choices=SituacaoDaTentativa.choices)
    id_externo = models.CharField(max_length=64, null=True, blank=True, unique=True)
    dados_para_pagar = models.JSONField(default=dict, blank=True)
    codigo_da_falha = models.CharField(max_length=40, blank=True, default="")
    solicitada_em = models.DateTimeField(default=agora)
    criada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["pedido", "numero"], name="tentativa_de_pagamento_numero_unico"
            ),
            models.UniqueConstraint(
                fields=["pedido"],
                condition=Q(situacao="solicitada"),
                name="tentativa_de_pagamento_solicitada_unica",
            ),
            models.CheckConstraint(
                condition=~Q(situacao="criada") | Q(id_externo__isnull=False),
                name="tentativa_de_pagamento_criada_tem_id_externo",
            ),
            models.CheckConstraint(
                condition=~Q(situacao="nao_criada") | ~Q(codigo_da_falha=""),
                name="tentativa_de_pagamento_nao_criada_tem_codigo",
            ),
            models.CheckConstraint(
                condition=Q(situacao__in=SituacaoDaTentativa.values),
                name="tentativa_de_pagamento_situacao_valida",
            ),
        )

    def __str__(self) -> str:
        return f"tentativa {self.pk}"


class DestinoDaDecisao(models.TextChoices):
    QUITA = "quita", "Quita o pedido"
    DEVOLUCAO = "devolucao", "Gera devolução"
    SEM_PEDIDO = "sem_pedido", "Sem pedido"


class MotivoDoDestino(models.TextChoices):
    INICIADO_FORA_DO_PRAZO = "iniciado_fora_do_prazo", "Iniciado fora do prazo"
    APROVADO_APOS_A_MARGEM = "aprovado_apos_a_margem", "Aprovado depois da margem"
    DUPLICIDADE = "duplicidade", "Pagamento em duplicidade"
    PEDIDO_CANCELADO = "pedido_cancelado", "Pedido cancelado"
    VALOR_DIVERGENTE = "valor_divergente", "Valor diferente do pedido"
    REFERENCIA_DESCONHECIDA = "referencia_desconhecida", "Referência desconhecida"


class DestinoDoPagamento(RegistroSoInsercao):
    """A decisão comercial sobre um pagamento aprovado, tomada uma única vez (E08-04)."""

    pagamento = models.OneToOneField(
        PAGAMENTO_REGISTRADO, on_delete=models.PROTECT, related_name="destino"
    )
    pedido = models.ForeignKey(
        Pedido, on_delete=models.PROTECT, null=True, blank=True, related_name="destinos"
    )
    destino = models.CharField(max_length=10, choices=DestinoDaDecisao.choices)
    motivo = models.CharField(
        max_length=30, choices=MotivoDoDestino.choices, blank=True, default=""
    )
    decidido_em = models.DateTimeField(default=agora)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["pedido"],
                condition=Q(destino="quita"),
                name="destino_um_quita_por_pedido",
            ),
            models.CheckConstraint(
                condition=(
                    Q(destino="quita", pedido__isnull=False, motivo="")
                    | Q(
                        destino="devolucao",
                        pedido__isnull=False,
                        motivo__in=[
                            MotivoDoDestino.INICIADO_FORA_DO_PRAZO.value,
                            MotivoDoDestino.APROVADO_APOS_A_MARGEM.value,
                            MotivoDoDestino.DUPLICIDADE.value,
                            MotivoDoDestino.PEDIDO_CANCELADO.value,
                            MotivoDoDestino.VALOR_DIVERGENTE.value,
                        ],
                    )
                    | Q(
                        destino="sem_pedido",
                        pedido__isnull=True,
                        motivo=MotivoDoDestino.REFERENCIA_DESCONHECIDA.value,
                    )
                ),
                name="destino_coerente",
            ),
        )

    def __str__(self) -> str:
        return f"destino {self.pk}"
