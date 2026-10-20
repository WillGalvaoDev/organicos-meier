"""Tentativas de pagamento e cobrança Pix (E08-03).

Cada vez que o comprador pede para pagar, o sistema grava uma tentativa com a chave de
idempotência e agenda a criação da cobrança no provedor, na mesma transação (E07-04). Há no
máximo uma tentativa aberta por pedido, e nada é criado a partir de `T0 + 24h`, mesmo que a
tarefa de bloqueio esteja atrasada.

Ordem das travas: `PagamentoNoProvedor` → `SituacaoDoPedido` → `TentativaDePagamento`. Este
módulo trava a situação e as tentativas, e nunca um pagamento.
"""

import logging
from datetime import datetime

from django.db import connection, transaction
from django.db.transaction import TransactionManagementError
from procrastinate.exceptions import AlreadyEnqueued

from apps.contas.models import Conta, Papel, Situacao
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao, prazo_encerrado, somar_horas
from apps.pagamentos.chamadas import agendar_chamada
from apps.pagamentos.models import ChamadaAoProvedor, PagamentoNoProvedor
from apps.pagamentos.provedor import SituacaoNoProvedor
from apps.pedidos.models import (
    Pedido,
    SituacaoDaTentativa,
    SituacaoDePagamento,
    SituacaoDoPedido,
    TentativaDePagamento,
)

logger = logging.getLogger(__name__)

HORAS_DO_PRAZO_DE_PAGAMENTO = 24

MENSAGENS = {
    "nao_e_seu": "Este pedido não é seu.",
    "prazo_encerrado": (
        "O prazo para pagar este pedido terminou em {prazo:%d/%m/%Y} às {prazo:%H:%M} "
        "(horário de Brasília)."
    ),
    "pedido_pago": "Este pedido já está pago.",
    "pedido_cancelado": "Este pedido foi cancelado e não pode mais ser pago.",
    "conta_inativa": "Sua conta não pode fazer pagamentos no momento.",
}


class PagamentoRecusado(Exception):
    """O comprador não pode pagar este pedido agora. `codigo` diz o motivo."""

    def __init__(self, codigo: str, prazo: datetime | None = None) -> None:
        self.codigo = codigo
        super().__init__(MENSAGENS[codigo].format(prazo=prazo))


def tentativa_aberta(tentativas: list[TentativaDePagamento]) -> TentativaDePagamento | None:
    """A tentativa aberta mais recente, se houver (as tentativas vêm por `numero`)."""
    return next((t for t in reversed(tentativas) if _aberta(t)), None)


def _aberta(tentativa: TentativaDePagamento) -> bool:
    """Solicitada, ou criada com o pagamento ainda pendente (sem registro, conta como aberta)."""
    if tentativa.situacao == SituacaoDaTentativa.SOLICITADA:
        return True
    if tentativa.situacao != SituacaoDaTentativa.CRIADA:
        return False
    situacao = (
        PagamentoNoProvedor.objects.filter(id_externo=tentativa.id_externo)
        .values_list("situacao", flat=True)
        .first()
    )
    return situacao in (None, SituacaoNoProvedor.PENDENTE.value)


def _disparar_processamento() -> None:
    """Depois do commit, enfileira a tarefa das chamadas para o comprador não esperar o minuto.
    Se ela já está na fila, a recusa é ignorada; a execução periódica cobre qualquer falha."""
    from apps.pagamentos.tarefas import processar_chamadas_ao_provedor

    try:
        with transaction.atomic():
            processar_chamadas_ao_provedor.defer(  # type: ignore[call-arg]
                timestamp=int(agora().timestamp())
            )
    except AlreadyEnqueued:
        pass
    except Exception as erro:
        logger.warning("Disparo imediato das chamadas falhou: %s", type(erro).__name__)


def pedir_pagamento(comprador: Conta, pedido: Pedido) -> TentativaDePagamento:
    """O comprador pede para pagar o pedido: devolve a tentativa aberta ou cria uma nova."""
    with transaction.atomic():
        situacao = (
            SituacaoDoPedido.objects.select_for_update()
            .select_related("pedido__abertura")
            .get(pedido_id=pedido.pk)
        )
        tentativas = list(
            TentativaDePagamento.objects.select_for_update()
            .filter(pedido_id=pedido.pk)
            .order_by("numero")
        )
        instante = agora()  # lido depois das travas
        travado = situacao.pedido
        prazo = somar_horas(travado.abertura.t0, HORAS_DO_PRAZO_DE_PAGAMENTO)
        atual = Conta.objects.get(pk=comprador.pk)
        if travado.comprador_id != comprador.pk:
            raise PagamentoRecusado("nao_e_seu")
        if prazo_encerrado(instante, prazo):
            raise PagamentoRecusado("prazo_encerrado", no_fuso_da_operacao(prazo))
        if situacao.situacao == SituacaoDePagamento.PAGO:
            raise PagamentoRecusado("pedido_pago")
        if situacao.situacao == SituacaoDePagamento.CANCELADO:
            raise PagamentoRecusado("pedido_cancelado")
        if atual.papel != Papel.COMPRADOR or atual.situacao != Situacao.ATIVA:
            raise PagamentoRecusado("conta_inativa")
        aberta = tentativa_aberta(tentativas)
        if aberta is not None:
            return aberta
        numero = (tentativas[-1].numero if tentativas else 0) + 1
        tentativa = TentativaDePagamento.objects.create(
            pedido=travado,
            numero=numero,
            chave_idempotencia=f"om-p{travado.pk}-t{numero}",
            referencia_externa=travado.referencia_externa,
            situacao=SituacaoDaTentativa.SOLICITADA,
            solicitada_em=instante,
        )
        agendar_chamada(
            "criar_cobranca",
            f"t{tentativa.pk}",
            parametros={"tentativa": tentativa.pk},
            chave_idempotencia=tentativa.chave_idempotencia,
        )
        transaction.on_commit(_disparar_processamento)
        registrar_auditoria(
            atual,
            "pedido.pedir_pagamento",
            travado,
            {"pedido": travado.pk, "numero": numero},
        )
        return tentativa


def agendar_cancelamento(tentativa: TentativaDePagamento, motivo: str) -> ChamadaAoProvedor | None:
    """Agenda o cancelamento da cobrança da tentativa no provedor, uma vez por motivo.

    Só agenda se a tentativa está `criada` e o pagamento dela ainda não é terminal. O alvo é
    `t<tentativa>:<motivo>`, diferente do da criação e de cada motivo, para que quem trava o
    pedido nunca espere uma chamada em andamento (E07-R01). Exige transação.
    """
    if not connection.in_atomic_block:
        raise TransactionManagementError("agendar_cancelamento exige uma transação aberta.")
    atual = TentativaDePagamento.objects.get(pk=tentativa.pk)
    if atual.situacao != SituacaoDaTentativa.CRIADA or atual.id_externo is None:
        return None
    if not _aberta(atual):
        return None
    return agendar_chamada(
        "cancelar_cobranca",
        f"t{atual.pk}:{motivo}",
        parametros={"id_externo": atual.id_externo},
    )
