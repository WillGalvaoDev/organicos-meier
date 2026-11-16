"""O registro da execução das tarefas periódicas (E15-01).

Estado operacional, não dado financeiro nem de auditoria: o registro é mutável. Guarda só o nome
da tarefa, instantes, uma contagem e o nome da classe do último erro (nunca a mensagem).
"""

from django.db import models


class ExecucaoDaTarefa(models.Model):
    nome = models.CharField(max_length=60, unique=True)
    monitorada_desde = models.DateTimeField()
    ultima_conclusao_em = models.DateTimeField(null=True, blank=True)
    ultima_falha_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.CharField(max_length=100, blank=True, default="")
    falhas_seguidas = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return self.nome
