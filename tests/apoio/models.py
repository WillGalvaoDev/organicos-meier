"""Modelos usados só nos testes. O app é registrado apenas em config/settings/test.py."""

from django.db import models

from apps.nucleo.so_insercao import RegistroSoInsercao
from apps.nucleo.valores import CampoDinheiro, CampoQuantidade


class ModeloValores(models.Model):
    preco = CampoDinheiro()
    peso = CampoQuantidade()

    def __str__(self) -> str:
        return f"{self.preco} / {self.peso}"


class ModeloInstante(models.Model):
    momento = models.DateTimeField()

    def __str__(self) -> str:
        return self.momento.isoformat()


class ModeloSoInsercao(RegistroSoInsercao):
    nome = models.CharField(max_length=50)

    def __str__(self) -> str:
        return self.nome


class ModeloContador(models.Model):
    valor = models.IntegerField(default=0)

    def __str__(self) -> str:
        return str(self.valor)


class CobrancaDeTeste(models.Model):
    """Resultado da operação de teste `criar_cobranca_de_teste` (E07-04)."""

    id_externo = models.CharField(max_length=64)

    def __str__(self) -> str:
        return self.id_externo


class FalhaDeTeste(models.Model):
    """Código recebido pelo gancho `falhou` da operação de teste (E07-04)."""

    codigo = models.CharField(max_length=40)

    def __str__(self) -> str:
        return self.codigo
