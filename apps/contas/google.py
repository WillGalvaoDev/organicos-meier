"""Apoio ao login e cadastro com Google (E02-07)."""

from allauth.socialaccount.internal.flows.signup import clear_pending_signup
from django.contrib import messages
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

MENSAGEM_RECUSA = "Não foi possível entrar com essa conta Google."
CHAVE_CONVITE_PENDENTE = "convite_pendente"


def encerrar_cadastro_pendente(request: HttpRequest) -> None:
    """Tira da sessão o convite pendente e o login social em andamento."""
    request.session.pop(CHAVE_CONVITE_PENDENTE, None)
    clear_pending_signup(request)


def recusar_login_google(request: HttpRequest) -> HttpResponseRedirect:
    """Recusa única: nada é criado, a sessão perde o convite pendente e volta ao login."""
    encerrar_cadastro_pendente(request)
    messages.error(request, MENSAGEM_RECUSA)
    return HttpResponseRedirect(reverse("account_login"))
