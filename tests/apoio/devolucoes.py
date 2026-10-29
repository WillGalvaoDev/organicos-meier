"""Apoio dos testes das devoluções (E10): pedidos pagos com itens de valores explícitos."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.contas.models import Conta
from apps.financeiro.reembolsos import reembolso_integral_do_pedido, reembolso_parcial
from apps.pedidos.models import ItemDoPedido, Pedido
from tests.apoio.financeiro import chave_nova, pedido_composto
from tests.apoio.pedidos import administrador, marcar_pago
from tests.fabricas import ContaFactory, ProdutoFactory

D = Decimal


@dataclass(frozen=True)
class Item:
    """Um item do arranjo: subtotal, quantidade e incremento, em texto."""

    subtotal: str
    quantidade: str
    incremento: str


# Os arranjos K, M e N da aceitação da E10-02
K = ("7.99", "0.40", "1.60", [Item("7.99", "1.000", "0.25")])
M = ("0.09", "0.00", "0.00", [Item("0.09", "0.600", "0.1")])
N = ("100.00", "5.00", "20.00", [Item("25.00", "1", "1"), Item("75.00", "3", "1")])


def itens_do_pedido(pedido: Pedido, itens: list[Item]) -> list[ItemDoPedido]:
    """Grava os itens (a composição comercial) do pedido, direto."""
    fornecedor = pedido.abertura.rodada.fornecedor
    criados: list[ItemDoPedido] = []
    for item in itens:
        quantidade = D(item.quantidade)
        produto = ProdutoFactory.create(fornecedor=fornecedor, incremento=D(item.incremento))
        criados.append(
            ItemDoPedido.objects.create(
                pedido=pedido,
                produto=produto,
                nome=produto.nome,
                unidade=produto.unidade,
                incremento=D(item.incremento),
                preco_unitario=(D(item.subtotal) / quantidade).quantize(D("0.01")),
                quantidade=quantidade,
                subtotal=D(item.subtotal),
            )
        )
    return criados


def pedido_pago_com_itens(
    arranjo: tuple[str, str, str, list[Item]], comprador: Conta | None = None
) -> tuple[Pedido, list[ItemDoPedido]]:
    """Um pedido `pago` (direto no banco, sem entradas no livro) com os itens do arranjo."""
    produtos, servico, frete, itens = arranjo
    pedido = pedido_composto(comprador or ContaFactory.create(), produtos, servico, frete)
    marcar_pago(pedido)
    return pedido, itens_do_pedido(pedido, itens)


def parcial(
    item: ItemDoPedido,
    quantidade: str,
    *,
    chave: str | None = None,
    motivo: str = "ocorrencia_de_entrega",
) -> Any:
    """Um `reembolso_parcial` numa transação própria, pelo administrador."""
    with transaction.atomic():
        return reembolso_parcial(
            item, D(quantidade), chave=chave or chave_nova(), motivo=motivo, autor=administrador()
        )


def integral(pedido: Pedido, *, chave: str | None = None) -> Any:
    """Um `reembolso_integral_do_pedido` numa transação própria, pelo administrador."""
    with transaction.atomic():
        return reembolso_integral_do_pedido(
            pedido,
            chave=chave or chave_nova(),
            motivo="cancelamento_da_rodada",
            autor=administrador(),
        )


def componentes(registrado: Any) -> tuple[Decimal, Decimal, Decimal]:
    """Os produtos, o serviço e o frete do reembolso registrado."""
    r = registrado.reembolso
    return r.produtos, r.servico, r.frete
