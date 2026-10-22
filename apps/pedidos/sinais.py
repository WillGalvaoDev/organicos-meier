"""Sinais emitidos pelos pedidos."""

from django.dispatch import Signal

# Enviado por `decidir_destino` (E08-04) logo depois de gravar o destino de um pagamento aprovado,
# na mesma transação e com o pagamento e a situação do pedido já travados. Argumento: `destino`.
# Quem recebe não pode depender de `apps.pedidos`, e uma exceção desfaz a sincronização inteira.
destino_do_pagamento_decidido = Signal()
