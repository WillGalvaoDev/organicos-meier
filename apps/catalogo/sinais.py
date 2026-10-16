from django.dispatch import Signal

# Enviado dentro da transação da edição, com `produto`, `anterior` e `novo` (Decimal).
preco_alterado = Signal()
