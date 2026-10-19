"""Registro dos pagamentos do provedor (E07-03).

`PagamentoNoProvedor` é o espelho do que o provedor respondeu por último e foi aplicado;
`ConsultaDoPagamento` guarda cada resposta e só aceita inserção. Só `sincronizacao.py` escreve
nestas tabelas (cenário 37): nenhuma rota, comando ou tela registra um pagamento recebido.
Nenhum campo guarda dado do pagador.
"""

from django.db import models

from apps.nucleo.so_insercao import RegistroSoInsercao
from apps.nucleo.tempo import agora
from apps.nucleo.valores import CampoDinheiro
from apps.pagamentos.provedor import SituacaoNoProvedor

SITUACOES = [situacao.value for situacao in SituacaoNoProvedor]
SITUACOES_ESCOLHAS = [(valor, valor) for valor in SITUACOES]


class OrigemDaConsulta(models.TextChoices):
    AVISO = "aviso", "Aviso do provedor"
    TAREFA = "tarefa", "Tarefa de chamadas pendentes"
    DECISAO = "decisao", "Consulta antes de uma decisão"
    BUSCA = "busca", "Busca por referência"


class DivergenciaDaConsulta(models.TextChoices):
    NENHUMA = "", "Nenhuma"
    REFERENCIA = "referencia", "Referência"
    VALOR = "valor", "Valor"
    CRIACAO = "criacao", "Criação no provedor"
    APROVACAO = "aprovacao", "Aprovação no provedor"


class PagamentoNoProvedor(models.Model):
    provedor = models.CharField(max_length=30)
    ambiente = models.CharField(max_length=20)
    id_externo = models.CharField(max_length=64)
    referencia_externa = models.CharField(max_length=64, db_index=True)
    valor = CampoDinheiro()
    situacao = models.CharField(max_length=20, choices=SITUACOES_ESCOLHAS)
    criado_no_provedor_em = models.DateTimeField()
    expira_em = models.DateTimeField()
    aprovado_no_provedor_em = models.DateTimeField(null=True, blank=True)
    primeiro_aviso_em = models.DateTimeField(null=True, blank=True)
    primeira_consulta_em = models.DateTimeField(default=agora)
    ultima_consulta_em = models.DateTimeField(default=agora)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["provedor", "id_externo"], name="pagamento_id_unico"),
            models.CheckConstraint(
                condition=models.Q(valor__gt=0), name="pagamento_valor_positivo"
            ),
            models.CheckConstraint(
                condition=models.Q(situacao__in=SITUACOES),
                name="pagamento_situacao_valida",
            ),
        )

    def __str__(self) -> str:
        return f"{self.provedor}:{self.id_externo}"


class ConsultaDoPagamento(RegistroSoInsercao):
    pagamento = models.ForeignKey(
        PagamentoNoProvedor, on_delete=models.PROTECT, related_name="consultas"
    )
    origem = models.CharField(max_length=10, choices=OrigemDaConsulta.choices)
    situacao = models.CharField(max_length=20, choices=SITUACOES_ESCOLHAS)
    aprovado_em = models.DateTimeField(null=True, blank=True)
    referencia_externa = models.CharField(max_length=64)
    valor = CampoDinheiro()
    consultado_em = models.DateTimeField(default=agora)
    aplicada = models.BooleanField()
    divergencia = models.CharField(
        max_length=10, choices=DivergenciaDaConsulta.choices, blank=True, default=""
    )

    def __str__(self) -> str:
        return f"consulta {self.pk}"


class SituacaoDaChamada(models.TextChoices):
    PENDENTE = "pendente", "Pendente"
    CONCLUIDA = "concluida", "Concluída"
    FALHOU = "falhou", "Falhou"


class ChamadaAoProvedor(models.Model):
    """Uma chamada ao provedor registrada junto da mudança de estado e executada por tarefa
    (E07-04). A chave de idempotência é gravada antes da chamada e reaproveitada em toda nova
    tentativa. Os parâmetros não levam dados pessoais."""

    operacao = models.CharField(max_length=40)
    alvo = models.CharField(max_length=64)
    parametros = models.JSONField(default=dict, blank=True)
    chave_idempotencia = models.CharField(max_length=64, unique=True)
    provedor = models.CharField(max_length=30)
    ambiente = models.CharField(max_length=20)
    situacao = models.CharField(
        max_length=10, choices=SituacaoDaChamada.choices, default=SituacaoDaChamada.PENDENTE
    )
    tentativas = models.PositiveIntegerField(default=0)
    proxima_em = models.DateTimeField(default=agora)
    criada_em = models.DateTimeField(default=agora)
    concluida_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.CharField(max_length=40, blank=True, default="")

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["operacao", "alvo"],
                condition=models.Q(situacao="pendente"),
                name="chamada_pendente_unica",
            ),
            models.CheckConstraint(
                condition=models.Q(situacao__in=SituacaoDaChamada.values),
                name="chamada_situacao_valida",
            ),
        )

    def __str__(self) -> str:
        return f"chamada {self.pk}"


class AvisoRecebido(RegistroSoInsercao):
    """Um aviso do provedor aceito: só o identificador do evento, o tipo e o pagamento citado.
    Nada do corpo vira estado (E07-05); a situação do pagamento vem da consulta."""

    provedor = models.CharField(max_length=30)
    id_evento = models.CharField(max_length=64)
    tipo = models.CharField(max_length=40)
    id_externo = models.CharField(max_length=64)
    recebido_em = models.DateTimeField(default=agora)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["provedor", "id_evento"], name="aviso_evento_unico"),
        )

    def __str__(self) -> str:
        return f"{self.provedor}:{self.id_evento}"
