"""Apoio dos testes da apuração final (E11): o arranjo AP da especificação.

O arranjo AP é o `montar_arranjo` da E08 com o pagamento aberto em `T0` e frete de 22,00. O pedido X
é de A (94,35) e o pedido Y é de B (106,15). "Pagar pelo simulador" é o comprador pedir o pagamento
antes de `T0 + 24h`, a tarefa criar a cobrança, o simulador aprová-la no instante dado e o aviso
ser entregue.
"""

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal
from typing import Any

from apps.pagamentos.chamadas import processar_chamadas
from apps.pedidos.models import Pedido
from apps.rodadas.models import EstoqueDaRodada
from tests.apoio.pedidos import (
    PARCELAS_DE_P1,
    PARCELAS_DE_P2,
    T0,
    Arranjo,
    abrir,
    montar_arranjo,
    pedido_de,
    tentativa_criada,
)
from tests.conftest import RelogioControlado

D = Decimal
H = timedelta(hours=1)
MS = timedelta(milliseconds=1)
VIAVEL = "50.00"
INSUFICIENTE = "100.00"


def arranjo_ap(
    relogio: RelogioControlado,
    *,
    minimo: str = VIAVEL,
    frete: str = "22.00",
    pendente_a_p1: int = 0,
    parcelas_de_p1: Sequence[tuple[str, int]] = PARCELAS_DE_P1,
    parcelas_de_p2: Sequence[tuple[str, int]] = PARCELAS_DE_P2,
    limites: tuple[int, int] | None = None,
) -> tuple[Arranjo, Pedido, Pedido]:
    """AP com o pagamento aberto em `T0`; o relógio fica em `T0 + 1h`. Devolve o arranjo, o
    pedido X (de A) e o pedido Y (de B)."""
    relogio.congelar(T0)
    arranjo = montar_arranjo(
        minimo=minimo,
        pendente_a_p1=pendente_a_p1,
        parcelas_de_p1=parcelas_de_p1,
        parcelas_de_p2=parcelas_de_p2,
    )
    if limites is not None:  # o limite de P1 e o de P2 no estoque da rodada
        for produto, limite in zip((arranjo.p1, arranjo.p2), limites, strict=True):
            EstoqueDaRodada.objects.filter(rodada=arranjo.rodada, produto=produto).update(
                limite=D(limite)
            )
    abrir(arranjo, frete)
    relogio.congelar(T0 + H)
    return arranjo, pedido_de(arranjo.a), pedido_de(arranjo.b)


def cobranca(relogio: RelogioControlado, pedido: Pedido) -> str:
    """O comprador pede o pagamento em `T0 + 1h` e a cobrança é criada (pendente no simulador)."""
    relogio.congelar(T0 + H)
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    return id_externo


def pagar(
    relogio: RelogioControlado,
    sim: Any,
    pedido: Pedido,
    *,
    quando: Any = None,
    entregar: bool = True,
) -> str:
    """Cria a cobrança do pedido, o simulador a aprova em `quando` (por padrão, `T0 + 2h`) e, com
    `entregar`, o aviso é entregue e processado nesse instante. Devolve o `id_externo`."""
    instante = quando or T0 + 2 * H
    id_externo = cobranca(relogio, pedido)
    relogio.congelar(instante)
    sim.aprovar(id_externo, em=instante)
    if entregar:
        sim.entregar_avisos()
        processar_chamadas()
    return id_externo
