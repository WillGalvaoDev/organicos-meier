"""Backend de e-mail que sempre falha (E02-04, A-19)."""

from typing import Any

from django.core.mail.backends.base import BaseEmailBackend


class BackendQueFalha(BaseEmailBackend):
    def send_messages(self, email_messages: Any) -> int:
        raise ConnectionError("falha simulada no envio")
