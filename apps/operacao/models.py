"""O registro da execução das tarefas periódicas (E15-01).

Estado operacional, não dado financeiro nem de auditoria: o registro é mutável. Guarda só o nome
da tarefa, instantes, uma contagem e o nome da classe do último erro (nunca a mensagem).
"""

from django.db import models

from apps.nucleo.so_insercao import RegistroSoInsercao


class ExecucaoDaTarefa(models.Model):
    nome = models.CharField(max_length=60, unique=True)
    monitorada_desde = models.DateTimeField()
    ultima_conclusao_em = models.DateTimeField(null=True, blank=True)
    ultima_falha_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.CharField(max_length=100, blank=True, default="")
    falhas_seguidas = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return self.nome


class BackupExterno(RegistroSoInsercao):
    """Um backup externo concluído (E16-04): só existe para um objeto conferido no bucket.

    Só inserção, como a auditoria. Guarda a chave do objeto no bucket de backups, o tamanho e o
    SHA-256 do arquivo cifrado; nunca dados de conexão nem caminho local.
    """

    iniciado_em = models.DateTimeField()
    concluido_em = models.DateTimeField()
    ambiente = models.CharField(max_length=20)
    chave = models.CharField(max_length=255, unique=True)
    tamanho_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=models.Q(tamanho_bytes__gt=0), name="backup_externo_tamanho_positivo"
            ),
            models.CheckConstraint(
                condition=models.Q(sha256__regex=r"^[0-9a-f]{64}$"),
                name="backup_externo_sha256_hexadecimal",
            ),
        )

    def __str__(self) -> str:
        return self.chave
