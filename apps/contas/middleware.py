"""Middlewares de proteção do administrador e das rotas de MFA (E02-03)."""

import re
from collections.abc import Callable

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import SESSION_KEY, logout
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse

from apps.contas.administracao import (
    passkey_recente,
    redirecionar_para_reautenticacao,
    tem_passkey,
)
from apps.contas.emails import email_banido
from apps.contas.models import Conta, Papel, Situacao

PREFIXO_MFA = "/seguranca/"
_GERENCIA_PASSKEYS = re.compile(r"^/seguranca/webauthn/(add/|keys/\d+/(remove|edit)/)$")


def _administrador_autenticado(request: HttpRequest) -> bool:
    usuario = request.user
    return bool(usuario.is_authenticated and getattr(usuario, "papel", None) == Papel.ADMINISTRADOR)


class ExigePasskeyDoAdministrador:
    """Administrador sem passkey só alcança o cadastro da primeira (e `POST /sair/`)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if (
            _administrador_autenticado(request)
            and not self._livre(request.path)
            and not tem_passkey(request.user)  # type: ignore[arg-type]
        ):
            return HttpResponseRedirect(reverse("mfa_add_webauthn"))
        return self.get_response(request)

    @staticmethod
    def _livre(caminho: str) -> bool:
        return caminho.startswith((PREFIXO_MFA, "/sair/", settings.STATIC_URL))


class ProtegeRotasDeMfa:
    """MFA existe só para o administrador; gestão de passkeys exige passkey recente."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path.startswith(PREFIXO_MFA) and request.user.is_authenticated:
            if not _administrador_autenticado(request):
                return HttpResponseForbidden()
            # Com a primeira passkey a regra de recência não se aplica: ainda não há passkey
            # para provar, e o allauth já exige login recente por qualquer método.
            if (
                _GERENCIA_PASSKEYS.match(request.path)
                and tem_passkey(request.user)
                and not passkey_recente(request)
            ):
                return redirecionar_para_reautenticacao(request)
        return self.get_response(request)


class RecusaContaSemAcesso:
    """Recusa requisição de sessão cuja conta foi removida ou cujo e-mail foi banido.

    Relê a situação do banco a cada requisição, olhando a sessão diretamente (o Django já trata a
    sessão de conta removida como anônima, mas aqui a requisição é recusada e a sessão encerrada).
    Cobre sessões criadas durante uma corrida com a remoção (infraestrutura 4.11). A view nunca
    executa: GET redireciona para o login; os demais métodos recebem 403.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        identificador = request.session.get(SESSION_KEY)
        if identificador is not None:
            conta = (
                Conta.objects.filter(pk=identificador)
                .values("situacao", "email_normalizado")
                .first()
            )
            if conta is not None and (
                conta["situacao"] == Situacao.REMOVIDA or email_banido(conta["email_normalizado"])
            ):
                logout(request)
                if request.method == "GET":
                    messages.info(request, "Sua sessão foi encerrada.")
                    return HttpResponseRedirect(reverse("account_login"))
                return HttpResponseForbidden()
        return self.get_response(request)
