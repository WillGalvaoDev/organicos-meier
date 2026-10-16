"""Encerramento de sessões de uma conta (E02-03; reaproveitado pela E02-08)."""

from allauth.usersessions.models import UserSession
from django.contrib.sessions.models import Session

from apps.contas.models import Conta


def encerrar_sessoes(conta: Conta) -> int:
    """Apaga todas as sessões da conta. Devolve quantas sessões foram encerradas.

    Varre as sessões do banco (e não só o `usersessions`), para não depender de a conta ter
    feito alguma requisição depois do login.
    """
    encerradas = 0
    alvo = str(conta.pk)
    for sessao in Session.objects.all():
        if sessao.get_decoded().get("_auth_user_id") == alvo:
            sessao.delete()
            encerradas += 1
    UserSession.objects.filter(user=conta).delete()
    return encerradas
