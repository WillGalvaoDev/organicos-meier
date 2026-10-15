"""Modelos usados só nos testes. O app é registrado apenas em config/settings/test.py."""

from django.db import models

from apps.nucleo.valores import CampoDinheiro, CampoQuantidade


class ModeloValores(models.Model):
    preco = CampoDinheiro()
    peso = CampoQuantidade()

    def __str__(self) -> str:
        return f"{self.preco} / {self.peso}"
