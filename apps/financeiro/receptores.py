"""Receptores do livro-razão (E09-04), ligados em `apps.py`."""

from typing import Any

from apps.financeiro.entradas import registrar_entrada, registrar_tarifa
from apps.pedidos.models import DestinoDoPagamento


def registrar_no_livro_o_destino_decidido(
    sender: Any, destino: DestinoDoPagamento, **kwargs: Any
) -> None:
    """Roda dentro da transação que decidiu o destino: uma exceção desfaz a sincronização."""
    registrar_entrada(destino)
    registrar_tarifa(destino.pagamento)
