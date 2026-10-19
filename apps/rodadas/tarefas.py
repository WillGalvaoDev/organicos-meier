"""Tarefa periódica do encerramento dos fechamentos vencidos (E06-05), no Procrastinate."""

from procrastinate.contrib.django import app

from apps.rodadas.fechamento import encerrar_fechamentos_vencidos

NOME_DA_TAREFA = "encerrar_fechamentos_vencidos"


@app.periodic(cron="* * * * *")
@app.task(name=NOME_DA_TAREFA, queueing_lock=NOME_DA_TAREFA)
def encerrar_fechamentos_vencidos_agora(timestamp: int) -> None:
    encerrar_fechamentos_vencidos()
