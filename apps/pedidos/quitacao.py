"""Quitação e destino dos pagamentos aprovados (E08-04).

Quando o provedor aprova um pagamento, a sincronização (E07-03) avisa por sinal e esta decisão
acontece uma única vez por pagamento: ou ele quita o pedido, ou gera devolução integral, com o
motivo registrado. Só os horários do provedor decidem (P-6); a ordem de chegada dos avisos não
muda o resultado.

Ordem das travas: `PagamentoDoProvedor` → `SituacaoDoPedido` → `TentativaDePagamento`. Quem chama
já travou o pagamento; este módulo trava a situação do pedido.
"""

import logging
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from django.db import connection
from django.db.transaction import TransactionManagementError

from apps.catalogo.templatetags.catalogo import reais
from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.nucleo.tempo import agora, ate_o_limite
from apps.pagamentos.provedor import SituacaoNoProvedor
from apps.pedidos.models import (
    DestinoDaDecisao,
    DestinoDoPagamento,
    MotivoDoDestino,
    Pedido,
    SituacaoDePagamento,
    SituacaoDoPedido,
)
from apps.pedidos.prazos import aceita_tentativas, fim_da_margem, prazo_de_pagamento
from apps.pedidos.sinais import destino_do_pagamento_decidido

logger = logging.getLogger(__name__)

MAIOR_TITULO = 150
MOTIVOS_DE_DEVOLUCAO = (
    MotivoDoDestino.INICIADO_FORA_DO_PRAZO,
    MotivoDoDestino.APROVADO_APOS_A_MARGEM,
    MotivoDoDestino.DUPLICIDADE,
    MotivoDoDestino.PEDIDO_CANCELADO,
    MotivoDoDestino.VALOR_DIVERGENTE,
)

_REFERENCIA = re.compile(r"om-c(\d+)-p(\d+)")


class PagamentoDoProvedor(Protocol):
    """O que a decisão lê de um pagamento do provedor. Este módulo só lê o pagamento; quem o
    escreve é a sincronização (E07-03)."""

    pk: int
    id_externo: str
    referencia_externa: str
    valor: Decimal
    situacao: str
    criado_no_provedor_em: datetime
    aprovado_no_provedor_em: datetime | None


def ler_referencia(texto: str) -> tuple[int, int] | None:
    """Separa o ciclo e o pedido de `om-c<ciclo>-p<pedido>`; `None` se o formato não confere."""
    achado = _REFERENCIA.fullmatch(texto)
    if achado is None:
        return None
    return int(achado.group(1)), int(achado.group(2))


def _gravar_destino(
    pagamento: PagamentoDoProvedor, pedido: Pedido | None, destino: str, motivo: str
) -> DestinoDoPagamento:
    gravado = DestinoDoPagamento.objects.create(
        pagamento_id=pagamento.pk,
        pedido=pedido,
        destino=destino,
        motivo=motivo,
        decidido_em=agora(),
    )
    # quem recebe (o livro-razão, E09-04) roda na mesma transação: uma exceção desfaz tudo
    destino_do_pagamento_decidido.send(sender=DestinoDoPagamento, destino=gravado)
    return gravado


def _sem_pedido(pagamento: PagamentoDoProvedor) -> DestinoDoPagamento:
    destino = _gravar_destino(
        pagamento, None, DestinoDaDecisao.SEM_PEDIDO, MotivoDoDestino.REFERENCIA_DESCONHECIDA
    )
    logger.error(
        "Pagamento %s aprovado com referência desconhecida: %s",
        pagamento.id_externo,
        MotivoDoDestino.REFERENCIA_DESCONHECIDA,
    )
    registrar_auditoria(
        SISTEMA,
        "pagamento.destino",
        destino,
        {
            "id_externo": pagamento.id_externo,
            "pedido": None,
            "destino": destino.destino,
            "motivo": destino.motivo,
        },
    )
    return destino


def _motivo_da_devolucao(
    pagamento: PagamentoDoProvedor, aprovado: datetime, pedido: Pedido, situacao: SituacaoDoPedido
) -> str | None:
    """O motivo pelo qual o pagamento não quita o pedido, ou `None` se ele quita."""
    abertura = pedido.abertura
    limite = fim_da_margem(abertura)
    if pagamento.valor != pedido.total:
        return MotivoDoDestino.VALOR_DIVERGENTE
    if not aceita_tentativas(abertura, pagamento.criado_no_provedor_em):
        return MotivoDoDestino.INICIADO_FORA_DO_PRAZO
    if not ate_o_limite(aprovado, limite):
        return MotivoDoDestino.APROVADO_APOS_A_MARGEM
    if situacao.situacao == SituacaoDePagamento.PAGO:
        return MotivoDoDestino.DUPLICIDADE
    cancelado_em = situacao.cancelado_em
    if situacao.situacao == SituacaoDePagamento.CANCELADO and (
        cancelado_em is None or aprovado >= cancelado_em
    ):
        return MotivoDoDestino.PEDIDO_CANCELADO
    return None


def _quitar(
    pagamento: PagamentoDoProvedor, aprovado: datetime, pedido: Pedido, situacao: SituacaoDoPedido
) -> DestinoDoPagamento:
    prazo = prazo_de_pagamento(pedido.abertura)
    cancelamento_sem_efeito = situacao.motivo_do_cancelamento or None
    destino = _gravar_destino(pagamento, pedido, DestinoDaDecisao.QUITA, "")
    situacao.situacao = SituacaoDePagamento.PAGO
    situacao.quitado_por_id = pagamento.pk
    situacao.quitado_em = aprovado
    situacao.cancelado_em = None
    situacao.motivo_do_cancelamento = ""
    situacao.save(
        update_fields=[
            "situacao",
            "quitado_por",
            "quitado_em",
            "cancelado_em",
            "motivo_do_cancelamento",
        ]
    )
    registrar_auditoria(
        SISTEMA,
        "pedido.quitar",
        pedido,
        {
            "pedido": pedido.pk,
            "id_externo": pagamento.id_externo,
            "aprovado_em": aprovado.astimezone(UTC).isoformat(),
            "na_margem": aprovado >= prazo,
            "cancelamento_sem_efeito": cancelamento_sem_efeito,
        },
    )
    fornecedor = pedido.abertura.rodada.fornecedor.nome
    emitir_evento(
        Evento.PAGAMENTO_CONFIRMADO,
        pedido.comprador,
        titulo=f"Pagamento confirmado: {fornecedor}"[:MAIOR_TITULO],
        corpo=(
            f"Recebemos o pagamento do seu pedido {pedido.pk} da rodada de {fornecedor}, "
            f"no valor de {reais(pedido.total)}. O pedido está pago."
        ),
        link=f"/pedidos/{pedido.pk}/",
        chave=f"pagamento_confirmado:{pedido.pk}:{pedido.comprador_id}",
    )
    return destino


def decidir_destino(pagamento: PagamentoDoProvedor) -> DestinoDoPagamento | None:
    """Decide, uma única vez, o destino de um pagamento aprovado: quitar o pedido ou devolver.

    Exige transação e o pagamento já travado (é o caso do receptor, dentro de
    `sincronizar_pagamento`). Devolve `None` se o pagamento não está aprovado ou não tem horário de
    aprovação (anomalia registrada no log); o destino existente, se já houver.
    """
    if not connection.in_atomic_block:
        raise TransactionManagementError("decidir_destino exige uma transação aberta.")
    if pagamento.situacao != SituacaoNoProvedor.APROVADO:
        return None
    existente: DestinoDoPagamento | None = DestinoDoPagamento.objects.filter(
        pagamento_id=pagamento.pk
    ).first()
    if existente is not None:
        return existente
    aprovado = pagamento.aprovado_no_provedor_em
    if aprovado is None:
        logger.error("Pagamento %s aprovado sem horário de aprovação", pagamento.id_externo)
        return None
    referencia = ler_referencia(pagamento.referencia_externa)
    pedido = None
    if referencia is not None:
        ciclo_id, pedido_id = referencia
        pedido = (
            Pedido.objects.select_related("abertura__rodada__fornecedor", "comprador")
            .filter(pk=pedido_id, abertura__ciclo_id=ciclo_id)
            .first()
        )
    if pedido is None:
        return _sem_pedido(pagamento)
    situacao = SituacaoDoPedido.objects.select_for_update().get(pedido=pedido)
    motivo = _motivo_da_devolucao(pagamento, aprovado, pedido, situacao)
    if motivo is None:
        return _quitar(pagamento, aprovado, pedido, situacao)
    destino = _gravar_destino(pagamento, pedido, DestinoDaDecisao.DEVOLUCAO, motivo)
    registrar_auditoria(
        SISTEMA,
        "pagamento.destino",
        destino,
        {
            "id_externo": pagamento.id_externo,
            "pedido": pedido.pk,
            "destino": destino.destino,
            "motivo": destino.motivo,
        },
    )
    logger.warning("Pagamento %s vai para devolução: %s", pagamento.id_externo, motivo)
    return destino
