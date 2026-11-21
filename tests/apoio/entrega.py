"""Apoio dos testes da E14: o AE (o AF da E13) e as operações de recebimento e ocorrência."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from apps.pedidos.models import ItemDoPedido, PedidoFormal
from apps.rodadas.models import CondicaoDoProdutoNoCiclo
from tests.apoio.pedido_formal import arranjo_af

__all__ = [
    "ENDERECO",
    "NOVO",
    "ae_liberada",
    "ae_recebido",
    "arranjo_ae",
    "arranjo_unico",
    "descartar",
    "item_de",
    "liberar",
    "ocorrer",
    "receber",
    "receber_tudo",
    "registrar_endereco",
    "retirar",
]

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
    quantidade: int | str = 10,
    frete: str = "20.00",
    minimo: str = "100.00",
    unidade: str = "unidade",
    incremento: str = "1.000",
) -> tuple[Any, Any, PedidoFormal]:
    """O AE-48 (preço 10,00, 10 unidades) e o AE-18 (preço 12,50, 8 unidades): um só comprador C
    num fornecedor com mínimo de 100,00, pago e aprovado em `T0 + 48h`. Devolve o arranjo, o pedido
    de C e o pedido formal. O pedido de C: produtos 100,00, serviço 5,00 e o frete dado. `minimo`,
    `unidade` e `incremento` mudam o fornecedor e o produto, para itens fracionados."""
    from apps.fornecedores.models import Fornecedor
    from apps.pedidos.apuracao import aprovar_resultado, iniciar_apuracao
    from tests.apoio.apuracao import H, pagar
    from tests.apoio.pedido_formal import EMAIL_DO_PEDIDO, PRAZO
    from tests.apoio.pedidos import T0, abrir, montar_arranjo, pedido_de

    relogio.congelar(T0)
    a = montar_arranjo(
        minimo=minimo,
        parcelas_de_p1=(("c", quantidade),),
        parcelas_de_p2=(),
        preco_de_p1=preco,
        unidade_de_p1=unidade,
        incremento_de_p1=incremento,
    )
    abrir(a, frete)
    relogio.congelar(T0 + H)
    Fornecedor.objects.filter(pk=a.fornecedor.pk).update(email_pedido=EMAIL_DO_PEDIDO)
    assert a.c is not None
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


ENDERECO = "Rua das Hortas, 100 — Méier, Rio de Janeiro/RJ"


def registrar_endereco(admin: Any, texto: str = ENDERECO) -> Any:
    from apps.pedidos.endereco_de_retirada import definir_endereco_de_retirada

    return definir_endereco_de_retirada(admin, texto)


def ae_recebido(
    relogio: Any, sim: Any, *, endereco: bool = True, **opcoes: Any
) -> tuple[Any, Any, Any, PedidoFormal]:
    """O AE-recebido: o AE com P1 11 e P2 12 recebidos e o endereço de retirada registrado."""
    a, x, y, pedido_formal = arranjo_ae(relogio, sim, **opcoes)
    receber(a.admin, a.rodada, a.p1, Decimal("11"))
    receber(a.admin, a.rodada, a.p2, Decimal("12"))
    if endereco:
        registrar_endereco(a.admin)
    return a, x, y, pedido_formal


def liberar(relogio: Any, a: Any, quando: datetime | None = None) -> Any:
    """Libera a retirada em `L = T0 + 72h` (ou em `quando`)."""
    from apps.pedidos.liberacao_da_retirada import liberar_retirada
    from tests.apoio.apuracao import H
    from tests.apoio.pedidos import T0

    relogio.congelar(quando or T0 + 72 * H)
    return liberar_retirada(a.admin, a.rodada)


def receber_tudo(a: Any, pedido_formal: PedidoFormal) -> None:
    """Recebe a quantidade inteira de cada linha do pedido formal."""
    for linha in pedido_formal.linhas.order_by("pk"):
        receber(a.admin, a.rodada, linha.produto, linha.quantidade)


def ae_liberada(relogio: Any, sim: Any, **opcoes: Any) -> tuple[Any, Any, Any, PedidoFormal]:
    """O AE-liberada: o AE-recebido liberado em `L = T0 + 72h`. O relógio fica em `L`."""
    a, x, y, pedido_formal = ae_recebido(relogio, sim, **opcoes)
    liberar(relogio, a)
    return a, x, y, pedido_formal


def retirar(autor: Any, item: Any, quantidade: Any, acionamento: Any = NOVO) -> Any:
    from apps.pedidos.retirada import registrar_retirada

    return registrar_retirada(
        autor,
        item,
        quantidade,
        acionamento=uuid.uuid4() if acionamento is NOVO else acionamento,
    )


def descartar(autor: Any, item: Any, quantidade: Any, acionamento: Any = NOVO) -> Any:
    from apps.pedidos.retirada import registrar_descarte

    return registrar_descarte(
        autor,
        item,
        quantidade,
        acionamento=uuid.uuid4() if acionamento is NOVO else acionamento,
    )
