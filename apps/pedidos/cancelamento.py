"""Pedidos de comprador suspenso ou removido (E08-06).

O pedido não pago é cancelado de imediato, na transação da moderação, e as cobranças pendentes
são canceladas no provedor por `ChamadaAoProvedor`, com um alvo próprio por motivo (a moderação
nunca espera uma chamada em andamento, E07-R01). Os pedidos pagos são preservados (§2). Um
pagamento que o provedor aprovou antes do cancelamento quita o pedido mesmo assim; um aprovado
depois gera devolução (E08-04).

Ordem das travas: a moderação trava a conta, os fornecedores, a rodada, os produtos e as
parcelas (E05-07); depois este módulo trava as `SituacaoDoPedido`. Nunca trava um pagamento do
provedor, então segue a ordem da E08-03: pagamento, situação do pedido, tentativa.
"""

from django.db import connection
from django.db.transaction import TransactionManagementError

from apps.contas.models import Conta, Papel
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.nucleo.tempo import agora
from apps.pedidos.models import (
    Pedido,
    SituacaoDaTentativa,
    SituacaoDePagamento,
    SituacaoDoPedido,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import agendar_cancelamento

MOTIVOS_DE_CANCELAMENTO = ("suspensao", "remocao_da_conta")


def cancelar_pedidos_nao_pagos(conta: Conta, *, motivo: str) -> int:
    """Cancela os pedidos `aguardando_pagamento` da conta, em qualquer abertura.

    Exige transação e `motivo` igual a `suspensao` ou `remocao_da_conta` (`ValueError`). Conta que
    não é de comprador: devolve 0. Devolve quantos pedidos cancelou.
    """
    if not connection.in_atomic_block:
        raise TransactionManagementError("cancelar_pedidos_nao_pagos exige uma transação aberta.")
    if motivo not in MOTIVOS_DE_CANCELAMENTO:
        raise ValueError(f"motivo desconhecido: {motivo!r}")
    if conta.papel != Papel.COMPRADOR:
        return 0
    candidatos = list(
        SituacaoDoPedido.objects.filter(
            pedido__comprador_id=conta.pk, situacao=SituacaoDePagamento.AGUARDANDO_PAGAMENTO
        )
        .order_by("pedido_id")
        .values_list("pedido_id", flat=True)
    )
    cancelados = 0
    for pedido_id in candidatos:
        situacao = SituacaoDoPedido.objects.select_for_update().get(pedido_id=pedido_id)
        if situacao.situacao != SituacaoDePagamento.AGUARDANDO_PAGAMENTO:
            continue  # mudou entre a leitura e a trava
        instante = agora()  # lido depois da trava
        situacao.situacao = SituacaoDePagamento.CANCELADO
        situacao.cancelado_em = instante
        situacao.motivo_do_cancelamento = motivo
        situacao.save(update_fields=["situacao", "cancelado_em", "motivo_do_cancelamento"])
        for tentativa in TentativaDePagamento.objects.filter(
            pedido_id=pedido_id, situacao=SituacaoDaTentativa.CRIADA
        ).order_by("numero"):
            agendar_cancelamento(tentativa, motivo)
        registrar_auditoria(
            SISTEMA,
            "pedido.cancelar",
            Pedido.objects.get(pk=pedido_id),
            {
                "pedido": pedido_id,
                "motivo": motivo,
                "cancelado_em": instante.isoformat(),
            },
        )
        cancelados += 1
    return cancelados
