from django.dispatch import Signal

# Enviado dentro da transação da sincronização, uma vez por mudança de situação aplicada, com
# `pagamento`, `anterior` (`SituacaoNoProvedor` ou `None` na criação) e `atual` (E07-03).
situacao_do_pagamento_mudou = Signal()
