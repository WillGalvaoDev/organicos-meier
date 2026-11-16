"""A tarefa periódica da verificação operacional (E15-02), no Procrastinate (fila no Postgres)."""

from procrastinate.contrib.django import app

from apps.operacao.execucao import execucao_monitorada
from apps.operacao.verificacao import verificar_operacao_agora

NOME_DA_TAREFA = "verificar_operacao"


@app.periodic(cron="*/5 * * * *")
@app.task(name=NOME_DA_TAREFA, queueing_lock=NOME_DA_TAREFA)
def verificar_operacao(timestamp: int) -> None:
    with execucao_monitorada(NOME_DA_TAREFA):
        verificar_operacao_agora()
