"""O catálogo das tarefas periódicas monitoradas (E15-01).

Uma tarefa periódica criada em etapa futura entra aqui na mesma fatia que a cria.
"""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class TarefaMonitorada:
    nome: str
    descricao: str
    intervalo: timedelta
    tolerancia: timedelta


# nome, descrição, intervalo e tolerância (em minutos)
_CATALOGO = (
    ("processar_envios_pendentes", "Envio de notificações", 1, 5),
    ("processar_chamadas_ao_provedor", "Chamadas ao provedor de pagamentos", 1, 5),
    ("encerrar_fechamentos_vencidos", "Encerramento dos fechamentos vencidos", 1, 5),
    (
        "bloquear_tentativas_vencidas",
        "Bloqueio das cobranças depois do prazo de pagamento",
        1,
        5,
    ),
    ("enviar_pedidos_formais", "Envio automático dos pedidos formais", 1, 5),
    ("registrar_tarifas_pendentes", "Registro das tarifas do provedor", 10, 30),
    ("verificar_invariante", "Verificação do invariante financeiro", 10, 30),
    ("reconsultar_pagamentos_da_margem", "Reconsulta dos pagamentos na margem", 10, 30),
    ("autorizar_devolucoes_do_cancelamento", "Devoluções dos cancelamentos", 10, 30),
    ("conciliar_dias_pendentes", "Conciliação diária", 60, 180),
    ("verificar_operacao", "Verificação operacional", 5, 15),
)

TAREFAS_MONITORADAS: list[TarefaMonitorada] = [
    TarefaMonitorada(nome, descricao, timedelta(minutes=intervalo), timedelta(minutes=tolerancia))
    for nome, descricao, intervalo, tolerancia in _CATALOGO
]

POR_NOME: dict[str, TarefaMonitorada] = {t.nome: t for t in TAREFAS_MONITORADAS}
