"""Acesso à área administrativa e nova autenticação por passkey (E02-03).

A prova de passkey vem dos registros de autenticação que o allauth guarda na sessão
(`allauth.account.authentication.get_authentication_records`, API pública): uma entrada com
`method == "mfa"` e `type == "webauthn"`, criada no login por passkey, na etapa de passkey depois
da senha ou numa nova autenticação. Registros de senha nunca contam.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any
from urllib.parse import urlencode

from allauth.account.authentication import get_authentication_records
from allauth.mfa.models import Authenticator
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from apps.contas.models import Conta, Papel
from apps.nucleo.tempo import agora

View = Callable[..., HttpResponse]


def tem_passkey(conta: Conta) -> bool:
    return bool(Authenticator.objects.filter(user=conta, type=Authenticator.Type.WEBAUTHN).exists())


def _registros_de_passkey(request: HttpRequest) -> list[dict[str, Any]]:
    return [
        registro
        for registro in get_authentication_records(request)
        if registro.get("method") == "mfa" and registro.get("type") == "webauthn"
    ]


def tem_prova_de_passkey(request: HttpRequest) -> bool:
    return bool(_registros_de_passkey(request))


def passkey_recente(request: HttpRequest) -> bool:
    """A última autenticação por passkey ocorreu há menos de `ACCOUNT_REAUTHENTICATION_TIMEOUT` s.

    O limite é exclusivo, como o do allauth (`agora - momento < prazo`): exatamente no prazo, já
    é preciso autenticar de novo. O instante vem de `agora()` (controlável nos testes).
    """
    registros = _registros_de_passkey(request)
    if not registros:
        return False
    ultimo = max(float(registro["at"]) for registro in registros)
    return agora().timestamp() - ultimo < settings.ACCOUNT_REAUTHENTICATION_TIMEOUT


def redirecionar_para_reautenticacao(request: HttpRequest) -> HttpResponseRedirect:
    """Nova autenticação por passkey (não por senha), voltando depois para a ação original."""
    destino = urlencode({"next": request.get_full_path()})
    return HttpResponseRedirect(f"{reverse('mfa_reauthenticate_webauthn')}?{destino}")


def _barrar(request: HttpRequest, *, recente: bool) -> HttpResponse | None:
    """Devolve a resposta de recusa, ou `None` quando o acesso é permitido."""
    usuario = request.user
    if not usuario.is_authenticated:
        return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
    if getattr(usuario, "papel", None) != Papel.ADMINISTRADOR:
        raise PermissionDenied
    if not tem_prova_de_passkey(request):
        return redirecionar_para_reautenticacao(request)
    if recente and not passkey_recente(request):
        return redirecionar_para_reautenticacao(request)
    return None


def somente_administrador(view: View) -> View:
    """Libera só administrador autenticado, com prova de passkey na sessão."""

    @wraps(view)
    def envolvida(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        recusa = _barrar(request, recente=False)
        return recusa if recusa is not None else view(request, *args, **kwargs)

    return envolvida


def exige_reautenticacao_por_passkey(view: View) -> View:
    """`somente_administrador` + passkey usada há no máximo `ACCOUNT_REAUTHENTICATION_TIMEOUT` s."""

    @wraps(view)
    def envolvida(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        recusa = _barrar(request, recente=True)
        return recusa if recusa is not None else view(request, *args, **kwargs)

    return envolvida


class SomenteAdministradorMixin:
    """Mixin para views baseadas em classe, com a mesma regra de `somente_administrador`."""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        recusa = _barrar(request, recente=False)
        if recusa is not None:
            return recusa
        return super().dispatch(request, *args, **kwargs)  # type: ignore[misc, no-any-return]
