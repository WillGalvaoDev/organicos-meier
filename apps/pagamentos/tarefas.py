"""Tarefa periódica das chamadas ao provedor (E07-04), no Procrastinate (fila no Postgres)."""

from procrastinate.contrib.django import app

from apps.pagamentos.chamadas import processar_chamadas

NOME_DA_TAREFA = "processar_chamadas_ao_provedor"


@app.periodic(cron="* * * * *")
@app.task(name=NOME_DA_TAREFA, queueing_lock=NOME_DA_TAREFA)
def processar_chamadas_ao_provedor(timestamp: int) -> None:
    processar_chamadas()
