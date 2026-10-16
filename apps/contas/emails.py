"""Normalização única de e-mail (E02-01).

Todo ponto que grava, compara ou consulta e-mail passa por `normalizar_email`.
"""

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

_VALIDADOR = EmailValidator()


class EmailInvalido(Exception):
    """Texto que não é um e-mail válido. A mensagem não repete o endereço."""


def normalizar_email(texto: str) -> str:
    """Tira espaços das pontas e converte para minúsculas, sem tocar em aliases (`+`, `.`)."""
    if not isinstance(texto, str):
        raise EmailInvalido("o e-mail deve ser um texto")
    normalizado = texto.strip().lower()
    if not normalizado:
        raise EmailInvalido("o e-mail está vazio")
    try:
        _VALIDADOR(normalizado)
    except ValidationError:
        raise EmailInvalido("o e-mail informado não é válido") from None
    return normalizado


def email_banido(texto: str) -> bool:
    """Verdadeiro se o e-mail (normalizado) está banido. Texto inválido devolve falso."""
    from apps.contas.models import EmailBanido

    try:
        normalizado = normalizar_email(texto)
    except EmailInvalido:
        return False
    return EmailBanido.objects.filter(email_normalizado=normalizado).exists()
