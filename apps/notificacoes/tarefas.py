"""Tarefa periódica dos envios (E04-03), no Procrastinate (fila no Postgres)."""

from procrastinate.contrib.django import app

from apps.notificacoes.processamento import processar_envios

NOME_DA_TAREFA = "processar_envios_pendentes"


@app.periodic(cron="* * * * *")
@app.task(name=NOME_DA_TAREFA, queueing_lock=NOME_DA_TAREFA)
def processar_envios_pendentes(timestamp: int) -> None:
    processar_envios()
