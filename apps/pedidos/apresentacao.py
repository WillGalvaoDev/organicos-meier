"""Textos e estados que as telas do comprador mostram sobre um pedido (E08-03)."""

from dataclasses import dataclass
from datetime import datetime

from apps.nucleo.tempo import agora, no_fuso_da_operacao
from apps.pedidos.models import (
    Pedido,
    SituacaoDaTentativa,
    SituacaoDePagamento,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import tentativa_aberta
from apps.pedidos.prazos import aceita_tentativas, prazo_de_pagamento


def prazo_do_pedido(pedido: Pedido) -> datetime:
    return prazo_de_pagamento(pedido.abertura)


def data_e_hora(instante: datetime) -> str:
    local = no_fuso_da_operacao(instante)
    return f"{local:%d/%m/%Y} às {local:%H:%M}"


def texto_da_situacao(pedido: Pedido, instante: datetime) -> str:
    situacao = pedido.estado.situacao
    if situacao == SituacaoDePagamento.PAGO:
        return "Pago"
    if situacao == SituacaoDePagamento.CANCELADO:
        return "Cancelado"
    if not aceita_tentativas(pedido.abertura, instante):
        return "Prazo encerrado"
    return f"Aguardando pagamento até {data_e_hora(prazo_do_pedido(pedido))}"


@dataclass(frozen=True)
class Pagamento:
    """O que o detalhe mostra do pagamento: o código Pix, a espera ou a falha por prazo."""

    codigo_pix: str | None
    gerando: bool
    falhou_por_prazo: bool
    pode_pagar: bool


def situacao_do_pagamento(pedido: Pedido, comprador_ativo: bool) -> Pagamento:
    tentativas: list[TentativaDePagamento] = list(pedido.tentativas.order_by("numero"))
    aguardando = pedido.estado.situacao == SituacaoDePagamento.AGUARDANDO_PAGAMENTO
    aberta = tentativa_aberta(tentativas) if aguardando else None
    codigo = None
    if aberta is not None and aberta.situacao == SituacaoDaTentativa.CRIADA:
        codigo = str(aberta.dados_para_pagar.get("pix_copia_e_cola", "")) or None
    ultima = tentativas[-1] if tentativas else None
    falhou_por_prazo = bool(
        aguardando
        and aberta is None
        and ultima is not None
        and ultima.situacao == SituacaoDaTentativa.NAO_CRIADA
        and ultima.codigo_da_falha == "prazo_encerrado"
    )
    dentro_do_prazo = aceita_tentativas(pedido.abertura, agora())
    return Pagamento(
        codigo_pix=codigo,
        gerando=dentro_do_prazo
        and aberta is not None
        and aberta.situacao == SituacaoDaTentativa.SOLICITADA,
        falhou_por_prazo=falhou_por_prazo,
        pode_pagar=aguardando and dentro_do_prazo and aberta is None and comprador_ativo,
    )
