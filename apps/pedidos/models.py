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
from apps.fornecedores.models import Fornecedor
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


class ResultadoDaApuracao(models.TextChoices):
    VALIDA = "valida", "Válida"
    RETORNO_PARA_INTERESSE = "retorno_para_interesse", "Retorno para interesse"


class ApuracaoFinal(RegistroDoPedido):
    """A apuração final do ciclo (E11-01): uma por ciclo, gravada depois de cancelar os não
    pagos. A rodada continua em `pagamento` até o administrador aprovar o resultado."""

    ciclo = models.OneToOneField(Ciclo, on_delete=models.PROTECT, related_name="apuracao")
    abertura = models.OneToOneField(
        AberturaDoPagamento, on_delete=models.PROTECT, related_name="apuracao"
    )
    autor = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="+")
    iniciada_em = models.DateTimeField()
    pedidos_pagos = models.PositiveIntegerField()
    pedidos_nao_pagos = models.PositiveIntegerField()
    resultado = models.CharField(max_length=24, choices=ResultadoDaApuracao.choices)
    valor_valido = CampoDinheiro()
    minimo = CampoDinheiro()

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=Q(resultado__in=ResultadoDaApuracao.values),
                name="apuracao_resultado_valido",
            ),
            models.CheckConstraint(
                condition=Q(valor_valido__gte=0), name="apuracao_valor_valido_nao_negativo"
            ),
        )

    def __str__(self) -> str:
        return f"apuração {self.pk}"


class AprovacaoDoResultado(RegistroDoPedido):
    """O administrador aprovou o resultado válido da apuração e a rodada avançou (E11-06)."""

    apuracao = models.OneToOneField(
        ApuracaoFinal, on_delete=models.PROTECT, related_name="aprovacao"
    )
    autor = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="+")
    aprovada_em = models.DateTimeField()

    def __str__(self) -> str:
        return f"aprovação {self.pk}"


class CancelamentoDaRodada(RegistroDoPedido):
    """O administrador cancelou a rodada inteira (E12-01): uma por rodada, só inserção. A mensagem
    é dado do cancelamento (serve ao aviso e às telas), e não motivo: a auditoria não a guarda."""

    rodada = models.OneToOneField(Rodada, on_delete=models.PROTECT, related_name="cancelamento")
    autor = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="+")
    cancelada_em = models.DateTimeField()
    com_reembolso = models.BooleanField()
    mensagem = models.CharField(max_length=1000, blank=True, default="")
    etapa_anterior = models.CharField(max_length=30)

    def __str__(self) -> str:
        return f"cancelamento da rodada {self.rodada_id}"


class CaixaInvalidada(RegistroDoPedido):
    """Uma caixa do produto no ciclo que ficou incompleta por inadimplência (E11-03). Só inserção:
    a caixa inteira é invalidada, e nenhuma é refeita."""

    apuracao = models.ForeignKey(ApuracaoFinal, on_delete=models.PROTECT, related_name="caixas")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="+")
    numero = models.PositiveIntegerField()

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["apuracao", "produto", "numero"], name="caixa_invalidada_unica"
            ),
            models.CheckConstraint(condition=Q(numero__gte=1), name="caixa_invalidada_numero"),
        )

    def __str__(self) -> str:
        return f"caixa {self.numero} invalidada"


class RestauracaoDeCaixa(RegistroDoPedido):
    """A volta de uma parte da parcela de um pagante para a fila de pendentes, por caixa
    invalidada (E11-04). `parcela_no_pedido` é único: é a chave (parcela, caixa invalidada) que
    impede restaurar duas vezes."""

    apuracao = models.ForeignKey(
        ApuracaoFinal, on_delete=models.PROTECT, related_name="restauracoes"
    )
    parcela_no_pedido = models.OneToOneField(
        ParcelaNoPedido, on_delete=models.PROTECT, related_name="restauracao"
    )
    parcela = models.ForeignKey(ParcelaDeInteresse, on_delete=models.PROTECT, related_name="+")
    quantidade = CampoQuantidade()
    criada_em = models.DateTimeField(default=agora)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=Q(quantidade__gt=0), name="restauracao_quantidade_positiva"
            ),
        )

    def __str__(self) -> str:
        return f"restauração {self.pk}"


class SituacaoDePagamento(models.TextChoices):
    AGUARDANDO_PAGAMENTO = "aguardando_pagamento", "Aguardando pagamento"
    PAGO = "pago", "Pago"
    CANCELADO = "cancelado", "Cancelado"


class MotivoDoCancelamento(models.TextChoices):
    SUSPENSAO = "suspensao", "Suspensão da conta"
    REMOCAO_DA_CONTA = "remocao_da_conta", "Remoção da conta"
    INADIMPLENCIA = "inadimplencia", "Falta de pagamento"
    CANCELAMENTO_DA_RODADA = "cancelamento_da_rodada", "Cancelamento da rodada"


class SituacaoDoPedido(models.Model):
    pedido = models.OneToOneField(Pedido, on_delete=models.PROTECT, related_name="estado")
    situacao = models.CharField(max_length=20, choices=SituacaoDePagamento.choices)
    quitado_por = models.OneToOneField(
        PAGAMENTO_REGISTRADO, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    quitado_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    motivo_do_cancelamento = models.CharField(
        max_length=30, choices=MotivoDoCancelamento.choices, blank=True, default=""
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


class PedidoFormal(RegistroSoInsercao):
    """O pedido formal ao fornecedor (E13-01): um por ciclo aprovado, gerado na transação da
    aprovação do resultado. O conteúdo do e-mail fica congelado aqui, e todo envio usa este
    mesmo registro. Nenhum campo identifica um comprador."""

    aprovacao = models.OneToOneField(
        AprovacaoDoResultado, on_delete=models.PROTECT, related_name="pedido_formal"
    )
    ciclo = models.OneToOneField(Ciclo, on_delete=models.PROTECT, related_name="pedido_formal")
    rodada = models.ForeignKey(Rodada, on_delete=models.PROTECT, related_name="pedidos_formais")
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.PROTECT, related_name="pedidos_formais"
    )
    emitido_em = models.DateTimeField()
    prazo_entrega_dias = models.PositiveSmallIntegerField()
    previsao_inicial = models.DateField()
    total_produtos = CampoDinheiro()
    assunto = models.CharField(max_length=200)
    corpo = models.TextField()

    def __str__(self) -> str:
        return f"pedido formal {self.pk}"


class LinhaDoPedidoFormal(RegistroSoInsercao):
    """Um produto do pedido formal, com a quantidade final e o valor congelados (E13-01)."""

    pedido_formal = models.ForeignKey(PedidoFormal, on_delete=models.PROTECT, related_name="linhas")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="+")
    nome = models.CharField(max_length=150)
    unidade = models.CharField(max_length=10, choices=Unidade.choices)
    preco_unitario = CampoDinheiro()
    multiplo = CampoQuantidade(null=True, blank=True)
    quantidade = CampoQuantidade()
    caixas = models.PositiveIntegerField(null=True, blank=True)
    valor_total = CampoDinheiro()

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["pedido_formal", "produto"], name="linha_do_pedido_formal_unica"
            ),
            models.CheckConstraint(
                condition=Q(quantidade__gt=0), name="linha_do_pedido_formal_quantidade_positiva"
            ),
            models.CheckConstraint(
                condition=Q(valor_total__gte=0), name="linha_do_pedido_formal_valor_nao_negativo"
            ),
            models.CheckConstraint(
                condition=(
                    Q(multiplo__isnull=True, caixas__isnull=True)
                    | Q(multiplo__isnull=False, caixas__isnull=False)
                ),
                name="linha_do_pedido_formal_caixas_com_multiplo",
            ),
        )

    def __str__(self) -> str:
        return f"linha {self.pk} do pedido formal"


class OrigemDaPrevisao(models.TextChoices):
    PADRAO = "padrao", "Prazo padrão"
    AJUSTE = "ajuste", "Ajuste do administrador"


class PrevisaoDeEntrega(RegistroSoInsercao):
    """A data prevista de entrega de um ciclo (E13-01). Só inserção: a vigente é a de maior
    `pk`. A inicial é `padrao`, sem autor; um ajuste (E13-05) é `ajuste`, com o administrador."""

    rodada = models.ForeignKey(Rodada, on_delete=models.PROTECT, related_name="previsoes")
    ciclo = models.ForeignKey(Ciclo, on_delete=models.PROTECT, related_name="previsoes")
    data = models.DateField()
    origem = models.CharField(max_length=10, choices=OrigemDaPrevisao.choices)
    autor = models.ForeignKey(
        Conta, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    registrada_em = models.DateTimeField(default=agora)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=(
                    Q(origem="padrao", autor__isnull=True) | Q(origem="ajuste", autor__isnull=False)
                ),
                name="previsao_de_entrega_origem_e_autor",
            ),
        )

    def __str__(self) -> str:
        return f"previsão {self.pk}"


class SituacaoDoEnvio(models.TextChoices):
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    CONCLUIDO_COM_SUCESSO = "concluido_com_sucesso", "Concluído com sucesso"
    CONCLUIDO_COM_FALHAS = "concluido_com_falhas", "Concluído com falhas"
    INTERROMPIDO = "interrompido", "Interrompido"


class EnvioDoPedidoFormal(models.Model):
    """O estado do ciclo de envio automático do pedido formal (E13-01 cria, E13-02 usa). É o
    único registro do pedido formal que muda."""

    pedido_formal = models.OneToOneField(
        PedidoFormal, on_delete=models.PROTECT, related_name="envio"
    )
    situacao = models.CharField(
        max_length=24, choices=SituacaoDoEnvio.choices, default=SituacaoDoEnvio.EM_ANDAMENTO
    )
    automaticas = models.PositiveSmallIntegerField(default=0)
    proxima_tentativa_em = models.DateTimeField(null=True, blank=True)
    concluido_em = models.DateTimeField(null=True, blank=True)
    motivo_da_interrupcao = models.CharField(max_length=30, blank=True, default="")

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=Q(automaticas__gte=0, automaticas__lte=3),
                name="envio_do_pedido_formal_automaticas_de_0_a_3",
            ),
            models.CheckConstraint(
                condition=(
                    Q(situacao="em_andamento", proxima_tentativa_em__isnull=False)
                    | (~Q(situacao="em_andamento") & Q(proxima_tentativa_em__isnull=True))
                ),
                name="envio_do_pedido_formal_proxima_so_em_andamento",
            ),
            models.CheckConstraint(
                condition=Q(situacao__in=SituacaoDoEnvio.values),
                name="envio_do_pedido_formal_situacao_valida",
            ),
        )

    def __str__(self) -> str:
        return f"envio do pedido formal {self.pedido_formal_id}"


class TipoDaTentativaDeEnvio(models.TextChoices):
    AUTOMATICA = "automatica", "Automática"
    MANUAL = "manual", "Manual"


class ResultadoDoEnvio(models.TextChoices):
    SUCESSO = "sucesso", "Aceito pelo serviço de e-mail"
    FALHA = "falha", "Falha"


class TentativaDeEnvioDoPedidoFormal(RegistroSoInsercao):
    """Uma tentativa de enviar o pedido formal por e-mail (E13-02), automática ou manual. Só
    inserção. "Sucesso" é aceitação pelo serviço de e-mail, e não entrega (L-13)."""

    pedido_formal = models.ForeignKey(
        PedidoFormal, on_delete=models.PROTECT, related_name="tentativas"
    )
    numero = models.PositiveIntegerField()
    tipo = models.CharField(max_length=10, choices=TipoDaTentativaDeEnvio.choices)
    ordem_automatica = models.PositiveSmallIntegerField(null=True, blank=True)
    iniciada_em = models.DateTimeField()
    concluida_em = models.DateTimeField()
    resultado = models.CharField(max_length=10, choices=ResultadoDoEnvio.choices)
    resposta = models.CharField(max_length=100)
    destino = models.CharField(max_length=254)
    autor = models.ForeignKey(
        Conta, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    token = models.UUIDField(null=True, blank=True, unique=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["pedido_formal", "numero"], name="tentativa_de_envio_numero_unico"
            ),
            models.UniqueConstraint(
                fields=["pedido_formal", "ordem_automatica"],
                name="tentativa_de_envio_ordem_automatica_unica",
            ),
            models.CheckConstraint(
                condition=Q(ordem_automatica__isnull=True)
                | Q(ordem_automatica__gte=1, ordem_automatica__lte=3),
                name="tentativa_de_envio_ordem_de_1_a_3",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        tipo="automatica",
                        ordem_automatica__isnull=False,
                        autor__isnull=True,
                        token__isnull=True,
                    )
                    | Q(
                        tipo="manual",
                        ordem_automatica__isnull=True,
                        autor__isnull=False,
                        token__isnull=False,
                    )
                ),
                name="tentativa_de_envio_tipo_coerente",
            ),
            models.CheckConstraint(
                condition=Q(resultado__in=ResultadoDoEnvio.values),
                name="tentativa_de_envio_resultado_valido",
            ),
        )

    def __str__(self) -> str:
        return f"tentativa de envio {self.pk}"
