from django.dispatch import Signal

# Enviado dentro da transação da abertura, com o argumento `rodada`.
rodada_aberta = Signal()

# Enviado dentro da transação de uma inclusão ou alteração de estoque, com `estoque`,
# `anterior` e `novo` (limite; `None` = sem limite). Na inclusão, `anterior` é `Decimal("0")`.
estoque_alterado = Signal()
