"""Tarefas do prazo de pagamento e da margem (E08-05), no Procrastinate (fila no Postgres).

O bloqueio vale em duas camadas: a recusa no servidor (E08-03) vale sozinha, mesmo com a tarefa
parada, e a tarefa só cancela no provedor as cobranças pendentes. Na margem, a reconsulta busca
pela referência os pagamentos já iniciados, que nunca são ignorados (§8.3).
"""

import logging

from django.db import transaction
from procrastinate.contrib.django import app

from apps.nucleo.tempo import agora
from apps.pagamentos.chamadas import agendar_chamada
from apps.pagamentos.consulta import (
    ConsultaAoProvedorFalhou,
    aprovados_da_referencia,
    consultar_antes_de_decidir,
    pendentes_das_referencias,
    travar_pagamento,
)
from apps.pagamentos.models import ChamadaAoProvedor
from apps.pedidos.models import (
    AberturaDoPagamento,
    DestinoDoPagamento,
    Pedido,
    SituacaoDaTentativa,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import agendar_cancelamento
from apps.pedidos.prazos import aceita_tentativas, em_margem
from apps.pedidos.quitacao import decidir_destino
from apps.rodadas.models import Etapa

logger = logging.getLogger(__name__)

TAREFA_DE_BLOQUEIO = "bloquear_tentativas_vencidas"
TAREFA_DA_MARGEM = "reconsultar_pagamentos_da_margem"


def _bloquear(abertura: AberturaDoPagamento) -> int:
    """Agenda o cancelamento de cada tentativa criada ainda sem chamada de cancelamento por prazo.
    Uma chamada que falhou definitivamente conta como existente: não é reagendada (E15 alerta)."""
    agendadas = 0
    tentativas = TentativaDePagamento.objects.filter(
        pedido__abertura=abertura, situacao=SituacaoDaTentativa.CRIADA
    ).order_by("pk")
    for tentativa in tentativas:
        ja_agendada = ChamadaAoProvedor.objects.filter(
            operacao="cancelar_cobranca", alvo=f"t{tentativa.pk}:prazo"
        ).exists()
        if ja_agendada:
            continue
        if agendar_cancelamento(tentativa, "prazo") is not None:
            agendadas += 1
    return agendadas + _bloquear_cobrancas_sem_tentativa(abertura)


def _bloquear_cobrancas_sem_tentativa(abertura: AberturaDoPagamento) -> int:
    """Agenda o cancelamento das cobranças pendentes da abertura que nenhuma tentativa conhece
    (a resposta da criação se perdeu), uma vez só: quem já tem alguma chamada de cancelamento,
    em qualquer situação, não é reagendada (E08-R03). O alvo `p<pagamento>:prazo` é só deste
    bloqueio, que não trava pedido nem pagamento."""
    referencias = [p.referencia_externa for p in Pedido.objects.filter(abertura=abertura)]
    agendadas = 0
    for pagamento in pendentes_das_referencias(referencias):
        if TentativaDePagamento.objects.filter(id_externo=pagamento.id_externo).exists():
            continue
        if ChamadaAoProvedor.objects.filter(
            operacao="cancelar_cobranca", parametros__id_externo=pagamento.id_externo
        ).exists():
            continue
        agendar_chamada(
            "cancelar_cobranca",
            f"p{pagamento.pk}:prazo",
            parametros={"id_externo": pagamento.id_externo},
        )
        agendadas += 1
    return agendadas


def bloquear_tentativas_vencidas_agora() -> int:
    """Cancela, no provedor, as cobranças pendentes das aberturas com o prazo vencido.

    Devolve quantos cancelamentos agendou. Uma falha numa abertura vai para o log (id e tipo da
    exceção) e não impede as outras.
    """
    instante = agora()
    agendadas = 0
    aberturas = AberturaDoPagamento.objects.filter(rodada__etapa=Etapa.PAGAMENTO).order_by("pk")
    for abertura in aberturas:
        if aceita_tentativas(abertura, instante):
            continue
        try:
            with transaction.atomic():
                agendadas += _bloquear(abertura)
        except Exception as erro:
            logger.error(
                "falha ao bloquear as tentativas: abertura=%s erro=%s",
                abertura.pk,
                type(erro).__name__,
            )
    return agendadas


def _decidir_o_que_ficou_pendente(pedido: Pedido) -> None:
    """Decide o destino dos pagamentos aprovados da referência do pedido que ainda não têm um."""
    for pagamento in aprovados_da_referencia(pedido.referencia_externa):
        if DestinoDoPagamento.objects.filter(pagamento_id=pagamento.pk).exists():
            continue
        with transaction.atomic():
            decidir_destino(travar_pagamento(pagamento.pk))


def reconsultar_pagamentos_da_margem_agora() -> int:
    """Reconsulta no provedor todos os pedidos das aberturas em margem, pagos ou não.

    Cada pedido usa `consultar_antes_de_decidir`, fora de qualquer transação; se o provedor não
    responde, o motivo vai para o log e segue o próximo. Depois decide o destino dos pagamentos
    aprovados que ainda não têm. Devolve quantos pedidos foram reconsultados com sucesso.
    """
    instante = agora()
    candidatos = (
        Pedido.objects.filter(abertura__rodada__etapa=Etapa.PAGAMENTO)
        .select_related("abertura")
        .order_by("pk")
    )
    pedidos = [p for p in candidatos if em_margem(p.abertura, instante)]
    reconsultados = 0
    for pedido in pedidos:
        try:
            consultar_antes_de_decidir(pedido.referencia_externa)
        except ConsultaAoProvedorFalhou as erro:
            logger.warning("Reconsulta da margem: pedido=%s motivo=%s", pedido.pk, erro.motivo)
            continue
        reconsultados += 1
    for pedido in pedidos:
        try:
            _decidir_o_que_ficou_pendente(pedido)
        except Exception as erro:
            logger.error(
                "falha ao decidir o destino na margem: pedido=%s erro=%s",
                pedido.pk,
                type(erro).__name__,
            )
    return reconsultados


@app.periodic(cron="* * * * *")
@app.task(name=TAREFA_DE_BLOQUEIO, queueing_lock=TAREFA_DE_BLOQUEIO)
def bloquear_tentativas_vencidas(timestamp: int) -> None:
    bloquear_tentativas_vencidas_agora()


@app.periodic(cron="*/10 * * * *")
@app.task(name=TAREFA_DA_MARGEM, queueing_lock=TAREFA_DA_MARGEM)
def reconsultar_pagamentos_da_margem(timestamp: int) -> None:
    reconsultar_pagamentos_da_margem_agora()
