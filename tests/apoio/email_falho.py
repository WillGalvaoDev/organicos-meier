"""Backends de e-mail que falham, para os testes (E02-04 A-19, E04-03).

`BackendComFalhas` e `BackendQueFalhaPara` guardam a configuração na classe, porque o Django cria
um backend novo a cada envio. Os dois aceitam as demais mensagens como o `locmem` (`mail.outbox`).
"""

from typing import Any

from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.locmem import EmailBackend as BackendLocmem


class BackendQueFalha(BaseEmailBackend):
    def send_messages(self, email_messages: Any) -> int:
        raise ConnectionError("falha simulada no envio")


class BackendComFalhas(BackendLocmem):
    """Falha as N primeiras chamadas e depois aceita."""

    falhas_restantes = 0
    chamadas = 0

    @classmethod
    def configurar(cls, *, falhas: int) -> None:
        cls.falhas_restantes = falhas
        cls.chamadas = 0

    def send_messages(self, messages: Any) -> int:
        type(self).chamadas += 1
        if type(self).falhas_restantes > 0:
            type(self).falhas_restantes -= 1
            raise ConnectionError("falha simulada no envio")
        return super().send_messages(messages)


class BackendQueFalhaPara(BackendLocmem):
    """Falha só para os destinos configurados."""

    destinos_que_falham: set[str] = set()  # noqa: RUF012
    chamadas = 0

    @classmethod
    def configurar(cls, *, destinos: set[str]) -> None:
        cls.destinos_que_falham = set(destinos)
        cls.chamadas = 0

    def send_messages(self, messages: Any) -> int:
        type(self).chamadas += 1
        if any(destino in type(self).destinos_que_falham for m in messages for destino in m.to):
            raise ConnectionError("falha simulada no envio")
        return super().send_messages(messages)
