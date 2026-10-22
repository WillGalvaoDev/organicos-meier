"""Livro-razão (E09-01): contas por destinação, movimentos e transferências.

Tudo aqui só aceita inserção, no banco e na aplicação. O saldo de uma conta não é guardado: é o que
entrou nela menos o que saiu, somado das transferências.
"""

from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import F, Q
from django.db.models.lookups import GreaterThan

from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.nucleo.so_insercao import RegistroSoInsercao
from apps.nucleo.tempo import agora
from apps.nucleo.valores import CampoDinheiro
from apps.rodadas.models import Ciclo, Rodada


class Destinacao(models.TextChoices):
    CUSTODIA = "custodia", "Custódia"
    OBRIGACAO_FORNECEDOR = "obrigacao_fornecedor", "Obrigação com fornecedor"
    FRETE = "frete", "Frete"
    OBRIGACAO_COMPRADOR = "obrigacao_comprador", "Obrigação com comprador"
    RECEITA_SERVICO = "receita_servico", "Receita de serviço"
    RESERVA = "reserva", "Reserva"
    DESPESAS_A_COBRIR = "despesas_a_cobrir", "Despesas a cobrir"


class Componente(models.TextChoices):
    PRODUTOS = "produtos", "Produtos"
    SERVICO = "servico", "Serviço"
    FRETE = "frete", "Frete"


class TipoDeMovimento(models.TextChoices):
    ENTRADA_DE_PAGAMENTO = "entrada_de_pagamento", "Entrada de pagamento"
    ENTRADA_PARA_DEVOLUCAO = "entrada_para_devolucao", "Entrada para devolução"
    APORTE = "aporte", "Aporte"
    TARIFA = "tarifa", "Tarifa"
    APURACAO = "apuracao", "Apuração"
    FINANCIAMENTO_DE_OBRIGACAO = "financiamento_de_obrigacao", "Financiamento de obrigação"
    COBERTURA_DE_DESPESA = "cobertura_de_despesa", "Cobertura de despesa"
    REPASSE = "repasse", "Repasse"
    RETIRADA_DE_RECEITA = "retirada_de_receita", "Retirada de receita"
    PAGAMENTO_DO_FRETE = "pagamento_do_frete", "Pagamento do frete"
    DEVOLUCAO = "devolucao", "Devolução"


class TipoDeAlerta(models.TextChoices):
    INVARIANTE_VIOLADO = "invariante_violado", "Invariante violado"
    RESERVA_INSUFICIENTE = "reserva_insuficiente", "Reserva insuficiente"
    PAGAMENTO_SEM_CONCILIACAO = "pagamento_sem_conciliacao", "Pagamento sem conciliação"
    DIVERGENCIA_NA_CONCILIACAO = "divergencia_na_conciliacao", "Divergência na conciliação"
    APROVADO_APOS_A_MARGEM = "aprovado_apos_a_margem", "Aprovado depois da margem"
    DUPLICIDADE = "duplicidade", "Duplicidade"


class Gravidade(models.TextChoices):
    CRITICO = "critico", "Crítico"
    AVISO = "aviso", "Aviso"


class ContaFinanceira(RegistroSoInsercao):
    """Uma conta do livro-razão: a destinação mais a chave. Nasce no primeiro movimento."""

    destinacao = models.CharField(max_length=30, choices=Destinacao.choices)
    chave = models.CharField(max_length=80)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, null=True, blank=True)
    rodada = models.ForeignKey(Rodada, on_delete=models.PROTECT, null=True, blank=True)
    ciclo = models.ForeignKey(Ciclo, on_delete=models.PROTECT, null=True, blank=True)
    comprador = models.ForeignKey(Conta, on_delete=models.PROTECT, null=True, blank=True)
    componente = models.CharField(max_length=10, choices=Componente.choices, blank=True, default="")
    # O modelo da obrigação com comprador nasce na E09-04; até lá, só o número dela.
    obrigacao = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["destinacao", "chave"], name="conta_financeira_unica"),
        )

    def __str__(self) -> str:
        return f"{self.destinacao}:{self.chave}"


class MovimentoFinanceiro(RegistroSoInsercao):
    """Um movimento: o conjunto de transferências que acontece junto ou não acontece."""

    class AutorTipo(models.TextChoices):
        SISTEMA = "sistema"
        USUARIO = "usuario"

    tipo = models.CharField(max_length=30, choices=TipoDeMovimento.choices)
    autor_tipo = models.CharField(max_length=10, choices=AutorTipo.choices)
    # NULL é exigido pela constraint: o autor "sistema" não tem identificador.
    autor_id = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001
    momento = models.DateTimeField(default=agora)
    justificativa = models.TextField()
    origem_tipo = models.CharField(max_length=100)
    origem_id = models.CharField(max_length=64)
    chave = models.CharField(max_length=120, unique=True)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=(
                    Q(autor_tipo="usuario", autor_id__isnull=False, autor_id__regex=r"\S")
                    | Q(autor_tipo="sistema", autor_id__isnull=True)
                ),
                name="movimento_autor_conforme_tipo",
            ),
            models.CheckConstraint(
                condition=Q(justificativa__regex=r"\S"), name="movimento_justificativa_preenchida"
            ),
        )

    def __str__(self) -> str:
        return f"{self.tipo} {self.chave}"


class TransferenciaFinanceira(RegistroSoInsercao):
    """Uma partida: `valor` sai de `de` e entra em `para`. Conta nula é o exterior: o dinheiro
    entrando na conta do provedor (`de` nula) ou saindo dela (`para` nula)."""

    movimento = models.ForeignKey(
        MovimentoFinanceiro, on_delete=models.PROTECT, related_name="transferencias"
    )
    de = models.ForeignKey(
        ContaFinanceira, on_delete=models.PROTECT, null=True, blank=True, related_name="saidas"
    )
    para = models.ForeignKey(
        ContaFinanceira, on_delete=models.PROTECT, null=True, blank=True, related_name="entradas"
    )
    valor = CampoDinheiro()

    class Meta:
        constraints = (
            models.CheckConstraint(condition=Q(valor__gt=0), name="transferencia_valor_positivo"),
            models.CheckConstraint(
                condition=Q(de__isnull=False) | Q(para__isnull=False),
                name="transferencia_tem_uma_conta",
            ),
            models.CheckConstraint(
                condition=Q(de__isnull=True) | Q(para__isnull=True) | ~Q(de=F("para")),
                name="transferencia_contas_distintas",
            ),
        )

    def __str__(self) -> str:
        return f"transferência {self.pk}"


class TipoDeDespesa(models.TextChoices):
    TARIFA = "tarifa", "Tarifa do provedor"
    DEFICIT_DE_FRETE = "deficit_frete", "Déficit de frete"


class ObrigacaoComComprador(RegistroSoInsercao):
    """Uma devolução devida a um comprador. O registro nunca muda: o financiado, o designado e o
    liquidado saem do livro-razão, e não de campos alteráveis."""

    rodada = models.ForeignKey(Rodada, on_delete=models.PROTECT, null=True, blank=True)
    ciclo = models.ForeignKey(Ciclo, on_delete=models.PROTECT, null=True, blank=True)
    pedido = models.ForeignKey(
        "pedidos.Pedido", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    comprador = models.ForeignKey(Conta, on_delete=models.PROTECT, null=True, blank=True)
    origem_tipo = models.CharField(max_length=100)
    origem_id = models.CharField(max_length=64)
    motivo = models.CharField(max_length=40)
    produtos = CampoDinheiro(default=0)
    servico = CampoDinheiro(default=0)
    frete = CampoDinheiro(default=0)
    # o que não se separa em componentes, como o pagamento devolvido inteiro
    integral = CampoDinheiro(default=0)
    # nasceu quando o ciclo já tinha sido apurado no livro (E09-06): muda as fontes e o relatório
    depois_da_apuracao = models.BooleanField(default=False)
    criada_em = models.DateTimeField(default=agora)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["origem_tipo", "origem_id"], name="obrigacao_origem_unica"
            ),
            models.CheckConstraint(
                condition=Q(origem_tipo__regex=r"\S") & Q(origem_id__regex=r"\S"),
                name="obrigacao_origem_preenchida",
            ),
            models.CheckConstraint(
                condition=(
                    Q(produtos__gte=0) & Q(servico__gte=0) & Q(frete__gte=0) & Q(integral__gte=0)
                ),
                name="obrigacao_componentes_nao_negativos",
            ),
            models.CheckConstraint(
                condition=Q(
                    GreaterThan(F("produtos") + F("servico") + F("frete") + F("integral"), 0)
                ),
                name="obrigacao_devido_positivo",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        rodada__isnull=True,
                        ciclo__isnull=True,
                        pedido__isnull=True,
                        comprador__isnull=True,
                    )
                    | Q(
                        rodada__isnull=False,
                        ciclo__isnull=False,
                        pedido__isnull=False,
                        comprador__isnull=False,
                    )
                ),
                name="obrigacao_pedido_todo_ou_nada",
            ),
        )

    @property
    def devido(self) -> Decimal:
        return Decimal(self.produtos + self.servico + self.frete + self.integral)

    def __str__(self) -> str:
        return f"obrigação {self.pk}"


class Despesa(RegistroSoInsercao):
    """Uma despesa a cobrir: a tarifa de um pagamento ou o déficit de frete de um ciclo. O coberto
    é a soma dos movimentos de cobertura; o pendente é o valor menos o coberto."""

    tipo = models.CharField(max_length=20, choices=TipoDeDespesa.choices)
    valor = CampoDinheiro()
    rodada = models.ForeignKey(Rodada, on_delete=models.PROTECT, null=True, blank=True)
    ciclo = models.ForeignKey(Ciclo, on_delete=models.PROTECT, null=True, blank=True)
    pagamento = models.ForeignKey(
        "pagamentos.PagamentoNoProvedor", on_delete=models.PROTECT, null=True, blank=True
    )
    criada_em = models.DateTimeField(default=agora)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["pagamento"],
                condition=Q(tipo="tarifa"),
                name="despesa_uma_tarifa_por_pagamento",
            ),
            models.CheckConstraint(condition=Q(valor__gt=0), name="despesa_valor_positivo"),
            models.CheckConstraint(
                condition=(
                    Q(tipo="tarifa", pagamento__isnull=False)
                    | Q(tipo="deficit_frete", rodada__isnull=False, ciclo__isnull=False)
                ),
                name="despesa_coerente_com_o_tipo",
            ),
        )

    def __str__(self) -> str:
        return f"{self.tipo} {self.valor}"


class DesignacaoDaReserva(RegistroSoInsercao):
    """Dinheiro da reserva separado para uma obrigação com comprador (P-3). Não move nada: o saldo
    da reserva continua o mesmo e o comprometido aumenta. Desfazer e consumir são outros
    registros."""

    obrigacao = models.ForeignKey(
        ObrigacaoComComprador, on_delete=models.PROTECT, related_name="designacoes"
    )
    valor = CampoDinheiro()
    autor_id = models.CharField(max_length=64)
    justificativa = models.TextField()
    criada_em = models.DateTimeField(default=agora)

    class Meta:
        constraints = (
            models.CheckConstraint(condition=Q(valor__gt=0), name="designacao_valor_positivo"),
            models.CheckConstraint(
                condition=Q(justificativa__regex=r"\S"), name="designacao_justificativa_preenchida"
            ),
        )

    def __str__(self) -> str:
        return f"designação {self.pk}"


class DesignacaoDesfeita(RegistroSoInsercao):
    """O desfazer de uma designação, com a justificativa. Uma designação só se desfaz uma vez."""

    designacao = models.OneToOneField(
        DesignacaoDaReserva, on_delete=models.PROTECT, related_name="desfeita"
    )
    autor_id = models.CharField(max_length=64)
    justificativa = models.TextField()
    desfeita_em = models.DateTimeField(default=agora)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=Q(justificativa__regex=r"\S"), name="desfeita_justificativa_preenchida"
            ),
        )

    def __str__(self) -> str:
        return f"designação {self.designacao_id} desfeita"


class ApuracaoNoLivro(RegistroSoInsercao):
    """A apuração de um ciclo no livro-razão (E09-06): uma por ciclo. Guarda o frete efetivo (o
    `F` da abertura) e o arrecadado (o que os pedidos válidos pagaram de frete)."""

    ciclo = models.OneToOneField(Ciclo, on_delete=models.PROTECT, related_name="apuracao_no_livro")
    movimento = models.ForeignKey(
        MovimentoFinanceiro, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    frete_efetivo = CampoDinheiro()
    frete_arrecadado = CampoDinheiro()
    criada_em = models.DateTimeField(default=agora)

    def __str__(self) -> str:
        return f"apuração do ciclo {self.ciclo_id}"


class PedidoApurado(RegistroSoInsercao):
    """Um pedido válido da apuração: o conjunto dela fica registrado, para repetir sem efeito."""

    apuracao = models.ForeignKey(
        ApuracaoNoLivro, on_delete=models.PROTECT, related_name="pedidos_validos"
    )
    pedido = models.ForeignKey("pedidos.Pedido", on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["apuracao", "pedido"], name="pedido_apurado_unico"),
        )


class AlertaFinanceiro(models.Model):
    """Um alerta ao administrador: aberto uma vez por situação `(tipo, chave)` e resolvido depois.
    O histórico fica; a resolução só preenche `resolvido_em` e o motivo."""

    tipo = models.CharField(max_length=30, choices=TipoDeAlerta.choices)
    chave = models.CharField(max_length=64)
    gravidade = models.CharField(max_length=10, choices=Gravidade.choices)
    dados = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    aberto_em = models.DateTimeField(default=agora)
    resolvido_em = models.DateTimeField(null=True, blank=True)
    motivo_da_resolucao = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["tipo", "chave"],
                condition=Q(resolvido_em__isnull=True),
                name="alerta_um_aberto_por_par",
            ),
        )

    def __str__(self) -> str:
        return f"{self.tipo}:{self.chave}"
