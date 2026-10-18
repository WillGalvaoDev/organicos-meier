from django.dispatch import Signal

# Enviado dentro da transação da edição, com `produto`, `anterior` e `novo` (Decimal) e
# `alteracao`, a `EntradaAuditoria` `produto.alterar_preco` gravada na mesma transação (E05-06).
preco_alterado = Signal()
