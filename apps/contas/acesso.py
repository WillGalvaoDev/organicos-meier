"""Ponto único de decisão de acesso (E02-02).

Todo método de entrada (senha, link, Google, passkey) chama `verificar_acesso`; nenhum repete
a lógica. O código da recusa vai para testes e logs, nunca para a tela e nunca com dados pessoais.
"""

from enum import StrEnum

from apps.contas.emails import email_banido
from apps.contas.models import Conta, Papel, Situacao


class Metodo(StrEnum):
    SENHA = "senha"
    LINK = "link"
    GOOGLE = "google"
    PASSKEY = "passkey"


class AcessoRecusado(Exception):
    """Login não permitido. `codigo` é interno (testes e logs), sem dados pessoais."""

    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo


def verificar_acesso(conta: Conta | None, email: str, metodo: Metodo) -> None:
    """Levanta `AcessoRecusado` quando o login não é permitido. Suspensa não é recusa (§2)."""
    if email_banido(email):
        raise AcessoRecusado("banido")
    if conta is None:
        raise AcessoRecusado("sem_conta")
    if conta.situacao == Situacao.REMOVIDA:
        raise AcessoRecusado("removida")
    if conta.papel == Papel.ADMINISTRADOR and metodo in (Metodo.LINK, Metodo.GOOGLE):
        raise AcessoRecusado("metodo_nao_permitido_admin")
