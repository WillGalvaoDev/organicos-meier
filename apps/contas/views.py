from allauth.mfa.adapter import get_adapter as get_adapter_mfa
from allauth.mfa.models import Authenticator
from allauth.mfa.webauthn.views import remove_webauthn
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.contas.administracao import somente_administrador


@login_required
def inicio(request: HttpRequest) -> HttpResponse:
    """Página inicial autenticada: nome e papel, até as telas de cada papel existirem."""
    return render(request, "inicio.html", {"conta": request.user})


@somente_administrador
def painel_administracao(request: HttpRequest) -> HttpResponse:
    """Início da área administrativa, sem conteúdo de negócio (E02-03)."""
    return render(request, "administracao/painel.html", {"conta": request.user})


def remover_passkey(request: HttpRequest, pk: int) -> HttpResponse:
    """Remoção de passkey do allauth, recusada quando seria a última (o allauth só consulta
    `can_delete_authenticator` no TOTP, então a regra é aplicada aqui)."""
    if request.method == "POST" and request.user.is_authenticated:
        autenticador = Authenticator.objects.filter(
            pk=pk, user=request.user, type=Authenticator.Type.WEBAUTHN
        ).first()
        if autenticador is not None and not get_adapter_mfa().can_delete_authenticator(
            autenticador
        ):
            messages.error(request, "A última passkey não pode ser removida.")
            return redirect("mfa_list_webauthn")
    resposta: HttpResponse = remove_webauthn(request, pk=pk)
    return resposta
