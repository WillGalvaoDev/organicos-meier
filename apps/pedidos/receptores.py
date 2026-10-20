"""Receptores dos pedidos (E08-04): a decisão do destino de um pagamento aprovado.

Rodam dentro da transação do remetente: uma exceção desfaz a sincronização inteira (E07-03), e a
próxima consulta tenta de novo.
"""

from typing import Any

from apps.pagamentos.models import PagamentoNoProvedor
from apps.pagamentos.provedor import SituacaoNoProvedor
from apps.pedidos.quitacao import decidir_destino


def decidir_destino_do_pagamento_aprovado(
    sender: Any,
    pagamento: PagamentoNoProvedor,
    anterior: SituacaoNoProvedor | None,
    atual: SituacaoNoProvedor,
    **kwargs: Any,
) -> None:
    if atual == SituacaoNoProvedor.APROVADO:
        decidir_destino(pagamento)
