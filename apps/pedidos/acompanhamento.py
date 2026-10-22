"""Situação dos pedidos e devoluções devidas, para o administrador (E08-05)."""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q

from apps.pagamentos.models import ChamadaAoProvedor, SituacaoDaChamada
from apps.pedidos.models import (
    AberturaDoPagamento,
    DestinoDaDecisao,
    DestinoDoPagamento,
    MotivoDoCancelamento,
    MotivoDoDestino,
    Pedido,
    SituacaoDePagamento,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import tentativa_aberta
from apps.pedidos.prazos import prazo_de_pagamento

MOTIVOS_POR_EXTENSO = {
    MotivoDoDestino.APROVADO_APOS_A_MARGEM: "aprovado depois da margem",
    MotivoDoDestino.INICIADO_FORA_DO_PRAZO: "iniciado fora do prazo",
    MotivoDoDestino.DUPLICIDADE: "pagamento em duplicidade",
    MotivoDoDestino.PEDIDO_CANCELADO: "pedido cancelado",
    MotivoDoDestino.VALOR_DIVERGENTE: "valor diferente do pedido",
    MotivoDoDestino.REFERENCIA_DESCONHECIDA: "referência desconhecida",
}
CANCELAMENTOS_POR_EXTENSO = {
    MotivoDoCancelamento.SUSPENSAO: "Cancelado (suspensão)",
    MotivoDoCancelamento.REMOCAO_DA_CONTA: "Cancelado (remoção da conta)",
}


@dataclass(frozen=True)
class LinhaDoPedido:
    comprador: str
    total: Decimal
    situacao: str


@dataclass(frozen=True)
class DevolucaoDevida:
    id_externo: str
    valor: Decimal
    motivo: str


def _sem_resposta_do_provedor(tentativas: list[TentativaDePagamento]) -> bool:
    """A última chamada de criação, cancelamento ou consulta do pedido está pendente com erro."""
    filtro = Q(operacao="criar_cobranca", alvo__in=[f"t{t.pk}" for t in tentativas]) | Q(
        operacao="consultar_pagamento", alvo__in=[t.id_externo for t in tentativas if t.id_externo]
    )
    for tentativa in tentativas:
        filtro |= Q(operacao="cancelar_cobranca", alvo__startswith=f"t{tentativa.pk}:")
    ultima = ChamadaAoProvedor.objects.filter(filtro).order_by("-pk").first()
    if ultima is None:
        return False
    return bool(ultima.situacao == SituacaoDaChamada.PENDENTE and ultima.ultimo_erro)


def _situacao(pedido: Pedido) -> str:
    estado = pedido.estado
    if estado.situacao == SituacaoDePagamento.PAGO:
        quitado = estado.quitado_em
        no_prazo = quitado is not None and quitado < prazo_de_pagamento(pedido.abertura)
        return "Pago no prazo" if no_prazo else "Pago na margem"
    if estado.situacao == SituacaoDePagamento.CANCELADO:
        return CANCELAMENTOS_POR_EXTENSO[MotivoDoCancelamento(estado.motivo_do_cancelamento)]
    tentativas = list(pedido.tentativas.order_by("numero"))
    if _sem_resposta_do_provedor(tentativas):
        return "Sem resposta do provedor"
    if tentativa_aberta(tentativas) is not None:
        return "Pagamento pendente"
    return "Não pago"


def situacao_dos_pedidos(abertura: AberturaDoPagamento) -> list[LinhaDoPedido]:
    pedidos = (
        abertura.pedidos.select_related("comprador", "estado", "abertura")
        .order_by("comprador__nome", "pk")
        .all()
    )
    return [LinhaDoPedido(p.comprador.nome, p.total, _situacao(p)) for p in pedidos]


def devolucoes_devidas(abertura: AberturaDoPagamento) -> list[DevolucaoDevida]:
    """Os destinos `devolucao` e `sem_pedido` dos pagamentos com a referência dos pedidos."""
    referencias = [p.referencia_externa for p in abertura.pedidos.select_related("abertura")]
    destinos = (
        DestinoDoPagamento.objects.filter(
            destino__in=(DestinoDaDecisao.DEVOLUCAO, DestinoDaDecisao.SEM_PEDIDO),
            pagamento__referencia_externa__in=referencias,
        )
        .select_related("pagamento")
        .order_by("pk")
    )
    return [
        DevolucaoDevida(
            d.pagamento.id_externo,
            d.pagamento.valor,
            MOTIVOS_POR_EXTENSO[MotivoDoDestino(d.motivo)],
        )
        for d in destinos
    ]
