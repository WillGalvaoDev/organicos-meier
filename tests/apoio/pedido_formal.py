"""Apoio dos testes do pedido formal (E13): o arranjo AF da E13-01.

AF é o AP-viável com X e Y pagos pelo simulador, apurado e aprovado em `T0 + 48h`, com a rodada em
`aguardando_fornecedor`. O e-mail do pedido do fornecedor F é `pedidos@f.example`.
"""

from datetime import datetime, timedelta
from typing import Any

from apps.fornecedores.models import Fornecedor
from apps.pedidos.models import PedidoFormal
from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

PRAZO = T0 + 48 * H
EMAIL_DO_PEDIDO = "pedidos@f.example"


def arranjo_af(
    relogio: RelogioControlado, sim: Any, *, pagar_y: bool = True, **arranjo: Any
) -> tuple[Any, Any, Any, PedidoFormal]:
    """O AF aprovado. Devolve o arranjo, X, Y e o pedido formal. O relógio fica em `T0 + 48h`."""
    from apps.pedidos.apuracao import aprovar_resultado, iniciar_apuracao

    a, x, y = arranjo_ap(relogio, **arranjo)
    Fornecedor.objects.filter(pk=a.fornecedor.pk).update(email_pedido=EMAIL_DO_PEDIDO)
    pagar(relogio, sim, x)
    if pagar_y:
        pagar(relogio, sim, y)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    aprovar_resultado(a.admin, a.rodada)
    return a, x, y, PedidoFormal.objects.get(rodada=a.rodada)


M = timedelta(minutes=1)
FALHA = "tests.apoio.email_falho.BackendQueFalha"
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def processar(relogio: RelogioControlado, instante: datetime) -> int:
    """Roda a tarefa do envio automático no instante dado."""
    from apps.pedidos.envio_do_pedido_formal import processar_pedidos_formais

    relogio.congelar(instante)
    return processar_pedidos_formais()


def af_sucesso(relogio: RelogioControlado, sim: Any) -> tuple[Any, Any, Any, PedidoFormal]:
    """AF-sucesso: a primeira tentativa automática aceita. O relógio fica em `T0 + 48h`."""
    af = arranjo_af(relogio, sim)
    processar(relogio, PRAZO)
    return af


def af_falhas(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> tuple[Any, Any, Any, PedidoFormal]:
    """AF-falhas: três falhas automáticas, e o serviço de e-mail volta a aceitar. O relógio fica
    em `T0 + 48h + 35 min`."""
    settings.EMAIL_BACKEND = FALHA
    af = arranjo_af(relogio, sim)
    for instante in (PRAZO, PRAZO + 5 * M, PRAZO + 35 * M):
        processar(relogio, instante)
    settings.EMAIL_BACKEND = LOCMEM
    return af


def af_meio(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> tuple[Any, Any, Any, PedidoFormal]:
    """AF-meio: uma falha automática, com a segunda agendada (`em_andamento`)."""
    settings.EMAIL_BACKEND = FALHA
    af = arranjo_af(relogio, sim)
    processar(relogio, PRAZO)
    settings.EMAIL_BACKEND = LOCMEM
    return af
