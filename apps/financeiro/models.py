"""Livro-razão (E09-01): contas por destinação, movimentos e transferências.

Tudo aqui só aceita inserção, no banco e na aplicação. O saldo de uma conta não é guardado: é o que
entrou nela menos o que saiu, somado das transferências.
"""

from django.db import models
from django.db.models import F, Q

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
