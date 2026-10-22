"""Tarefa periódica do livro-razão (E09-04), no Procrastinate (fila no Postgres)."""

from procrastinate.contrib.django import app

from apps.financeiro.entradas import registrar_tarifas_pendentes_agora

TAREFA_DAS_TARIFAS = "registrar_tarifas_pendentes"


@app.periodic(cron="*/10 * * * *")
@app.task(name=TAREFA_DAS_TARIFAS, queueing_lock=TAREFA_DAS_TARIFAS)
def registrar_tarifas_pendentes(timestamp: int) -> None:
    registrar_tarifas_pendentes_agora()
