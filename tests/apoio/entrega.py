"""Apoio dos testes da E14: o AE (o AF da E13) e as operações de recebimento e ocorrência."""

import uuid
from typing import Any

from apps.pedidos.models import ItemDoPedido
from tests.apoio.pedido_formal import arranjo_af

__all__ = ["arranjo_af", "item_de", "receber"]


def item_de(pedido: Any, produto: Any) -> ItemDoPedido:
    """O item do pedido para o produto (X-P1, Y-P2 ...)."""
    return ItemDoPedido.objects.get(pedido=pedido, produto=produto)


def receber(autor: Any, rodada: Any, produto: Any, quantidade: Any, acionamento: Any = None) -> Any:
    from apps.pedidos.recebimento import registrar_recebimento

    return registrar_recebimento(
        autor,
        rodada,
        produto,
        quantidade,
        acionamento=acionamento if acionamento is not None else uuid.uuid4(),
    )
