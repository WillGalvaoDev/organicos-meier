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
