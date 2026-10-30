"""Lado do provedor no simulador de pagamentos (E07-01): cobranças e avisos simulados."""

from django.db import models

from apps.nucleo.tempo import agora
from apps.nucleo.valores import CampoDinheiro


class CobrancaSimulada(models.Model):
    """O pagamento pendente que o provedor cria junto com a cobrança (como no Pix)."""

    chave_idempotencia = models.CharField(max_length=64, unique=True)
    referencia_externa = models.CharField(max_length=64, db_index=True)
    valor = CampoDinheiro()
    descricao = models.CharField(max_length=120)
    meio = models.CharField(max_length=20)
    situacao = models.CharField(max_length=20)
    criado_em = models.DateTimeField(default=agora)
    aprovado_em = models.DateTimeField(null=True, blank=True)
    expira_em = models.DateTimeField()
    # Calculados na aprovação (E09-02); nulos antes dela.
    tarifa = CampoDinheiro(null=True, blank=True)
    liberado_em = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.id_externo

    @property
    def id_externo(self) -> str:
        return f"sim-{self.pk}"


class AvisoSimulado(models.Model):
    """Um evento que o provedor enviaria; os testes decidem quando e quantas vezes entregá-lo."""

    tipo = models.CharField(max_length=20, default="pagamento")
    id_externo = models.CharField(max_length=40)
    criado_em = models.DateTimeField(default=agora)
    entregas = models.PositiveIntegerField(default=0)
    descartado = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.id_evento

    @property
    def id_evento(self) -> str:
        return f"sim-ev-{self.pk}"


class MovimentoSimulado(models.Model):
    """Um movimento da conta do provedor simulado (E09-02): pagamento, tarifa, depósito, saída ou
    ajuste. O valor tem sinal; `liberado_em` é quando o dinheiro passa a estar disponível."""

    tipo = models.CharField(max_length=20)
    descricao = models.CharField(max_length=50)
    valor = CampoDinheiro()
    id_externo = models.CharField(max_length=40, blank=True, default="")
    ocorrido_em = models.DateTimeField(default=agora)
    liberado_em = models.DateTimeField()
    id_estorno = models.CharField(max_length=64, blank=True, default="")

    def __str__(self) -> str:
        return self.id_movimento

    @property
    def id_movimento(self) -> str:
        return f"mov-{self.pk}"


class EstornoSimulado(models.Model):
    """Um estorno do pagamento (E10-03). `visivel` falso é o estorno que o provedor recusou na
    resposta mas continua processando: a consulta não o mostra."""

    cobranca = models.ForeignKey(
        CobrancaSimulada, on_delete=models.CASCADE, related_name="estornos"
    )
    chave_idempotencia = models.CharField(max_length=64, unique=True)
    valor = CampoDinheiro()
    situacao = models.CharField(max_length=20)
    codigo = models.CharField(max_length=40, blank=True, default="")
    criado_em = models.DateTimeField(default=agora)
    concluido_em = models.DateTimeField(null=True, blank=True)
    visivel = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.id_estorno

    @property
    def id_estorno(self) -> str:
        return f"sim-est-{self.pk}"
