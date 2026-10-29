"""Tarefa periódica do livro-razão (E09-04), no Procrastinate (fila no Postgres)."""

from procrastinate.contrib.django import app

from apps.financeiro.conciliacao import conciliar_dias_pendentes_agora
from apps.financeiro.entradas import registrar_tarifas_pendentes_agora
from apps.financeiro.invariante import verificar_invariante_agora

TAREFA_DAS_TARIFAS = "registrar_tarifas_pendentes"
TAREFA_DO_INVARIANTE = "verificar_invariante"
TAREFA_DA_CONCILIACAO = "conciliar_dias_pendentes"


@app.periodic(cron="*/10 * * * *")
@app.task(name=TAREFA_DAS_TARIFAS, queueing_lock=TAREFA_DAS_TARIFAS)
def registrar_tarifas_pendentes(timestamp: int) -> None:
    registrar_tarifas_pendentes_agora()


@app.periodic(cron="*/10 * * * *")
@app.task(name=TAREFA_DO_INVARIANTE, queueing_lock=TAREFA_DO_INVARIANTE)
def verificar_invariante(timestamp: int) -> None:
    verificar_invariante_agora()


@app.periodic(cron="0 * * * *")
@app.task(name=TAREFA_DA_CONCILIACAO, queueing_lock=TAREFA_DA_CONCILIACAO)
def conciliar_dias_pendentes(timestamp: int) -> None:
    conciliar_dias_pendentes_agora()
