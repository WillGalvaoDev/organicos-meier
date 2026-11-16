"""Apoio dos testes da E14: o AE (o AF da E13) e as operações de recebimento e ocorrência."""

import uuid
from typing import Any

from apps.pedidos.models import ItemDoPedido, PedidoFormal
from apps.rodadas.models import CondicaoDoProdutoNoCiclo
from tests.apoio.pedido_formal import arranjo_af

__all__ = ["NOVO", "arranjo_ae", "item_de", "receber"]

NOVO: Any = object()  # "gere um acionamento novo"


def arranjo_ae(relogio: Any, sim: Any, **opcoes: Any) -> tuple[Any, Any, Any, PedidoFormal]:
    """O AE: o AF da E13 com as condições do ciclo que o fechamento congela (incremento e
    múltiplo de cada produto), que a preparação de teste do fechamento não cria."""
    a, x, y, pedido_formal = arranjo_af(relogio, sim, **opcoes)
    for produto in (a.p1, a.p2):
        CondicaoDoProdutoNoCiclo.objects.get_or_create(
            ciclo=a.ciclo,
            produto=produto,
            defaults={"incremento": produto.incremento, "multiplo": produto.multiplo},
        )
    return a, x, y, pedido_formal


def item_de(pedido: Any, produto: Any) -> ItemDoPedido:
    """O item do pedido para o produto (X-P1, Y-P2 ...)."""
    return ItemDoPedido.objects.get(pedido=pedido, produto=produto)


def receber(autor: Any, rodada: Any, produto: Any, quantidade: Any, acionamento: Any = NOVO) -> Any:
    from apps.pedidos.recebimento import registrar_recebimento

    return registrar_recebimento(
        autor,
        rodada,
        produto,
        quantidade,
        acionamento=uuid.uuid4() if acionamento is NOVO else acionamento,
    )
