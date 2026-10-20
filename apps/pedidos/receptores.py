"""Receptores dos pedidos: a decisão do destino de um pagamento aprovado (E08-04) e o cancelamento
dos pedidos não pagos na suspensão e na remoção da conta (E08-06).

Rodam dentro da transação do remetente: uma exceção desfaz a sincronização inteira (E07-03) ou a
moderação inteira (E02-08).
"""

from typing import Any

from apps.pagamentos.models import PagamentoNoProvedor
from apps.pagamentos.provedor import SituacaoNoProvedor
from apps.pedidos.cancelamento import cancelar_pedidos_nao_pagos
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


def cancelar_pedidos_na_suspensao(sender: Any, conta: Any, **kwargs: Any) -> None:
    cancelar_pedidos_nao_pagos(conta, motivo="suspensao")


def cancelar_pedidos_na_remocao(sender: Any, conta: Any, **kwargs: Any) -> None:
    cancelar_pedidos_nao_pagos(conta, motivo="remocao_da_conta")
