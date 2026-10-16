from django.dispatch import Signal

# Enviado dentro da transação da abertura, com o argumento `rodada`.
rodada_aberta = Signal()
