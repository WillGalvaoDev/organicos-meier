"""Canais de saída (E04-03)."""

from django.core.mail import EmailMessage


def enviar_email(destino: str, assunto: str, corpo: str) -> None:
    """Entrega a mensagem ao `EMAIL_BACKEND` configurado. Não captura exceções.

    "Enviado" significa aceito pelo serviço de e-mail, e não entregue (L-13). É a mesma função
    que o pedido formal ao fornecedor usará (E13).
    """
    EmailMessage(assunto, corpo, to=[destino]).send(fail_silently=False)
