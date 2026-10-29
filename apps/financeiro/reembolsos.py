"""Cálculo do reembolso (E10-02): parcial por item, serviço e frete proporcionais, integral."""

from decimal import Decimal
from typing import NamedTuple

from apps.contas.models import Conta
from apps.financeiro.models import ObrigacaoComComprador, Reembolso
from apps.nucleo.auditoria import _Sistema
from apps.pedidos.models import ItemDoPedido, Pedido


class ReembolsoRecusado(Exception):
    """O reembolso não pode ser calculado; a mensagem diz o motivo."""


class ReembolsoConflitante(Exception):
    """A chave já existe com outro conteúdo."""


class ReembolsoRegistrado(NamedTuple):
    reembolso: Reembolso
    obrigacao: ObrigacaoComComprador | None
    sem_cobertura: Decimal


def reembolso_parcial(
    item: ItemDoPedido, quantidade: Decimal, *, chave: str, motivo: str, autor: Conta | _Sistema
) -> ReembolsoRegistrado:
    raise NotImplementedError


def reembolso_integral_do_pedido(
    pedido: Pedido, *, chave: str, motivo: str, autor: Conta | _Sistema
) -> ReembolsoRegistrado | None:
    raise NotImplementedError


def acumulado_do_item(item: ItemDoPedido) -> tuple[Decimal, Decimal]:
    raise NotImplementedError


def acumulado_do_pedido(pedido: Pedido) -> tuple[Decimal, Decimal, Decimal]:
    raise NotImplementedError
