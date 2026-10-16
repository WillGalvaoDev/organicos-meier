from django.db import models


class Fornecedor(models.Model):
    """Entidade mínima (E02-01): só o nome. A E03 acrescenta os demais campos e a gestão."""

    nome = models.CharField(max_length=150)

    def __str__(self) -> str:
        return self.nome
