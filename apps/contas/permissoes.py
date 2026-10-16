"""Políticas de acesso por papel (E02-10).

Toda view do projeto declara uma política (`politica_de_acesso`), conferida por um teste que varre
as rotas. As recusas ocorrem no servidor, antes da view, para qualquer método e com ou sem
`HX-Request`: anônimo vai para o login, papel ou situação errados recebem 403 sem dados da rota.
"""

import functools
from collections.abc import Callable, Iterator
from enum import StrEnum
from typing import Any, ClassVar

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.urls import URLPattern, URLResolver, get_resolver

from apps.contas.models import Papel

View = Callable[..., HttpResponseBase]


class Politica(StrEnum):
    PUBLICA = "publica"
    AUTENTICADA = "autenticada"
    COMPRADOR = "comprador"  # ativa ou suspensa (consulta)
    COMPRADOR_ATIVO = "comprador_ativo"  # só quem pode adicionar interesses
    FORNECEDOR = "fornecedor"  # exige o fornecedor vinculado
    ADMINISTRADOR = "administrador"  # regra de `somente_administrador` (E02-03)


# Views de bibliotecas (allauth, Google), declaradas por nome de rota. Sem curingas: cada rota
# nova de terceiros precisa de uma entrada explícita.
POLITICAS_DE_TERCEIROS: dict[str, Politica] = {
    # allauth: contas
    "account_login": Politica.PUBLICA,  # tela de entrada
    "account_logout": Politica.PUBLICA,  # sair é inofensivo para quem não está logado
    "account_reauthenticate": Politica.AUTENTICADA,
    "account_reset_password": Politica.PUBLICA,  # recuperação de acesso
    "account_reset_password_done": Politica.PUBLICA,
    "account_reset_password_from_key": Politica.PUBLICA,  # o link do e-mail é a credencial
    "account_reset_password_from_key_done": Politica.PUBLICA,
    # allauth: MFA (passkeys), restrito ao administrador por `ProtegeRotasDeMfa`
    "mfa_index": Politica.AUTENTICADA,
    "mfa_authenticate": Politica.PUBLICA,  # etapa de login; protegida pelo estágio do allauth
    "mfa_reauthenticate": Politica.AUTENTICADA,
    "mfa_reauthenticate_webauthn": Politica.AUTENTICADA,
    "mfa_list_webauthn": Politica.AUTENTICADA,
    "mfa_add_webauthn": Politica.AUTENTICADA,
    "mfa_edit_webauthn": Politica.AUTENTICADA,
    "mfa_remove_webauthn": Politica.AUTENTICADA,  # a rota do allauth fica atrás da nossa
    "mfa_login_webauthn": Politica.PUBLICA,  # login por passkey direta
    # allauth: login social (Google), início e retorno do OAuth
    "google_login": Politica.PUBLICA,
    "google_callback": Politica.PUBLICA,
}


def _checar(request: HttpRequest, politica: Politica) -> HttpResponse | None:
    """Devolve o redirecionamento de login, levanta 403, ou devolve `None` se passou."""
    if politica is Politica.PUBLICA:
        return None
    usuario = request.user
    if not usuario.is_authenticated:
        return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
    if politica is Politica.AUTENTICADA:
        return None
    papel = getattr(usuario, "papel", None)
    if politica is Politica.COMPRADOR:
        permitido = papel == Papel.COMPRADOR
    elif politica is Politica.COMPRADOR_ATIVO:
        permitido = papel == Papel.COMPRADOR and bool(usuario.pode_adicionar_interesse)
    elif politica is Politica.FORNECEDOR:
        # Defesa em profundidade: a restrição do banco já impede fornecedor sem vínculo.
        permitido = papel == Papel.FORNECEDOR and usuario.fornecedor_id is not None
        if permitido:
            request.fornecedor_vinculado = usuario.fornecedor  # type: ignore[attr-defined]
    else:
        permitido = False
    if not permitido:
        raise PermissionDenied
    return None


def _decorador(politica: Politica) -> Callable[[View], View]:
    def decorador(view: View) -> View:
        @functools.wraps(view)
        def envolvida(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
            recusa = _checar(request, politica)
            return recusa if recusa is not None else view(request, *args, **kwargs)

        envolvida.politica_de_acesso = politica  # type: ignore[attr-defined]
        return envolvida

    return decorador


publica = _decorador(Politica.PUBLICA)
exige_login = _decorador(Politica.AUTENTICADA)
exige_comprador = _decorador(Politica.COMPRADOR)
exige_comprador_ativo = _decorador(Politica.COMPRADOR_ATIVO)
exige_fornecedor = _decorador(Politica.FORNECEDOR)


class _MixinDePolitica:
    """Base dos mixins: confere a política antes da view e a grava na view de `as_view()`."""

    politica: ClassVar[Politica]

    @classmethod
    def as_view(cls, **initkwargs: Any) -> View:
        view: View = super().as_view(**initkwargs)  # type: ignore[misc]
        view.politica_de_acesso = cls.politica  # type: ignore[attr-defined]
        return view

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        recusa = _checar(request, self.politica)
        if recusa is not None:
            return recusa
        return super().dispatch(request, *args, **kwargs)  # type: ignore[misc, no-any-return]


class PublicaMixin(_MixinDePolitica):
    politica = Politica.PUBLICA


class ExigeLoginMixin(_MixinDePolitica):
    politica = Politica.AUTENTICADA


class ExigeCompradorMixin(_MixinDePolitica):
    politica = Politica.COMPRADOR


class ExigeCompradorAtivoMixin(_MixinDePolitica):
    politica = Politica.COMPRADOR_ATIVO


class ExigeFornecedorMixin(_MixinDePolitica):
    politica = Politica.FORNECEDOR


def politica_da_view(callback: Any) -> Politica | None:
    """Política declarada pela view (decorador ou `as_view()`), ou `None` se não houver."""
    while isinstance(callback, functools.partial):
        callback = callback.func
    politica = getattr(callback, "politica_de_acesso", None)
    return Politica(politica) if politica is not None else None


def _rotas(padroes: list[Any], prefixo: str = "") -> Iterator[tuple[str, str | None, Any]]:
    for padrao in padroes:
        if isinstance(padrao, URLResolver):
            yield from _rotas(padrao.url_patterns, prefixo + str(padrao.pattern))
        elif isinstance(padrao, URLPattern):
            yield prefixo + str(padrao.pattern), padrao.name, padrao.callback


def rotas_sem_politica(urlconf: str | None = None) -> list[str]:
    """Rotas sem política declarada (nem na view, nem em `POLITICAS_DE_TERCEIROS`)."""
    faltando: list[str] = []
    for caminho, nome, callback in _rotas(get_resolver(urlconf).url_patterns):
        if politica_da_view(callback) is None and nome not in POLITICAS_DE_TERCEIROS:
            faltando.append(f"{caminho} ({nome})")
    return faltando


def entradas_de_terceiros_inexistentes(urlconf: str | None = None) -> list[str]:
    """Entradas de `POLITICAS_DE_TERCEIROS` cujo nome não corresponde a nenhuma rota."""
    nomes = {nome for _, nome, _ in _rotas(get_resolver(urlconf).url_patterns)}
    return sorted(nome for nome in POLITICAS_DE_TERCEIROS if nome not in nomes)
