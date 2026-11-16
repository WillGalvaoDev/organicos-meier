"""Apoio dos testes da E14: o AE (o AF da E13) e as operações de recebimento e ocorrência."""

import uuid
from typing import Any

from apps.pedidos.models import ItemDoPedido, PedidoFormal
from apps.rodadas.models import CondicaoDoProdutoNoCiclo
from tests.apoio.pedido_formal import arranjo_af

__all__ = ["NOVO", "arranjo_ae", "arranjo_unico", "item_de", "ocorrer", "receber"]

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


def arranjo_unico(
    relogio: Any,
    sim: Any,
    *,
    preco: str = "10.00",
    quantidade: int = 10,
    frete: str = "20.00",
) -> tuple[Any, Any, PedidoFormal]:
    """O AE-48 (preço 10,00, 10 unidades) e o AE-18 (preço 12,50, 8 unidades): um só comprador C
    num fornecedor com mínimo de 100,00, pago e aprovado em `T0 + 48h`. Devolve o arranjo, o pedido
    de C e o pedido formal. O pedido de C: produtos 100,00, serviço 5,00 e o frete dado."""
    from apps.fornecedores.models import Fornecedor
    from apps.pedidos.apuracao import aprovar_resultado, iniciar_apuracao
    from tests.apoio.apuracao import H, pagar
    from tests.apoio.pedido_formal import EMAIL_DO_PEDIDO, PRAZO
    from tests.apoio.pedidos import T0, abrir, montar_arranjo, pedido_de

    relogio.congelar(T0)
    a = montar_arranjo(
        minimo="100.00",
        parcelas_de_p1=(("c", quantidade),),
        parcelas_de_p2=(),
        preco_de_p1=preco,
    )
    abrir(a, frete)
    relogio.congelar(T0 + H)
    Fornecedor.objects.filter(pk=a.fornecedor.pk).update(email_pedido=EMAIL_DO_PEDIDO)
    pedido = pedido_de(a.c)
    pagar(relogio, sim, pedido)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    aprovar_resultado(a.admin, a.rodada)
    CondicaoDoProdutoNoCiclo.objects.get_or_create(
        ciclo=a.ciclo,
        produto=a.p1,
        defaults={"incremento": a.p1.incremento, "multiplo": a.p1.multiplo},
    )
    return a, pedido, PedidoFormal.objects.get(rodada=a.rodada)


def ocorrer(autor: Any, item: Any, quantidade: Any, tipo: Any, acionamento: Any = NOVO) -> Any:
    from apps.pedidos.ocorrencias import registrar_ocorrencia

    return registrar_ocorrencia(
        autor,
        item,
        quantidade,
        tipo,
        acionamento=uuid.uuid4() if acionamento is NOVO else acionamento,
    )
