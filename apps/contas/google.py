"""Apoio ao login e cadastro com Google (E02-07)."""

from typing import Any

from allauth.socialaccount.internal.flows.signup import clear_pending_signup
from django.contrib import messages
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

from apps.contas.emails import EmailInvalido, normalizar_email

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


_CHAVES_DE_VERIFICACAO = ("email_verified", "verified_email")


def email_verificado_do_google(extra_data: dict[str, Any] | None) -> str | None:
    """E-mail normalizado do Google, ou `None` se ausente, inválido ou não verificado.

    O provedor entrega a verificação em dois formatos: `email_verified` (ID token) e
    `verified_email` (`/oauth2/v2/userinfo`). O e-mail só conta como verificado quando pelo menos
    uma das chaves vale exatamente `True` (booleano) e nenhuma presente tem outro valor. É o único
    ponto do projeto que interpreta a verificação (adaptador e conclusão do cadastro).
    """
    if not isinstance(extra_data, dict):
        return None
    marcas = [extra_data[chave] for chave in _CHAVES_DE_VERIFICACAO if chave in extra_data]
    if not marcas or any(marca is not True for marca in marcas):
        return None
    email = extra_data.get("email")
    if not isinstance(email, str):
        return None
    try:
        return normalizar_email(email)
    except EmailInvalido:
        return None
