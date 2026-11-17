"""A tarefa periódica da verificação operacional (E15-02), no Procrastinate (fila no Postgres)."""

from procrastinate.contrib.django import app

from apps.nucleo.tempo import agora
from apps.operacao.backup import fazer_backup_externo
from apps.operacao.execucao import execucao_monitorada
from apps.operacao.verificacao import verificar_operacao_agora

NOME_DA_TAREFA = "verificar_operacao"


@app.periodic(cron="*/5 * * * *")
@app.task(name=NOME_DA_TAREFA, queueing_lock=NOME_DA_TAREFA)
def verificar_operacao(timestamp: int) -> None:
    with execucao_monitorada(NOME_DA_TAREFA):
        verificar_operacao_agora()


NOME_DO_BACKUP = "backup_diario"


@app.periodic(cron="0 6 * * *")  # 03:00 em Brasília
@app.task(name=NOME_DO_BACKUP, queueing_lock=NOME_DO_BACKUP)
def backup_diario(timestamp: int) -> None:
    """O backup externo cifrado no R2 (E16-04). A falha é repassada: a E15-01 registra e o Sentry
    recebe o erro e o check-in `error`."""
    with execucao_monitorada(NOME_DO_BACKUP):
        fazer_backup_externo(agora())
