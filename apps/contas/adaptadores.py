"""Adaptador do allauth (E02-02): identidade autorizada, banimento e mensagem única de recusa."""

from typing import Any, ClassVar

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.authentication import get_authentication_records
from allauth.account.models import EmailAddress
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.mfa.models import Authenticator
from django import forms
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from apps.contas.acesso import AcessoRecusado, Metodo, verificar_acesso
from apps.contas.administracao import tem_passkey
from apps.contas.emails import EmailInvalido, normalizar_email
from apps.contas.models import Conta

MENSAGEM_GENERICA = "Não foi possível entrar com esses dados."


def metodo_do_login(request: HttpRequest) -> Metodo:
    """Método do login em curso, pelos registros de autenticação da sessão."""
    registros = get_authentication_records(request)
    if registros and registros[-1].get("method") == "mfa" and registros[-1].get("passwordless"):
        return Metodo.PASSKEY
    return Metodo.SENHA


def conferir_login(conta: Conta, email: str, metodo: Metodo) -> None:
    """Regras de entrada. Levanta `AcessoRecusado` (códigos internos, nunca exibidos).

    O administrador entra por senha (seguida da etapa de passkey) ou por passkey direta; as
    sessões dele sem passkey cadastrada ficam restritas pelo middleware
    `ExigePasskeyDoAdministrador`.
    """
    verificar_acesso(conta, email, metodo)
    verificado = EmailAddress.objects.filter(user=conta, verified=True).exists()
    if not verificado:  # exigido por ACCOUNT_EMAIL_VERIFICATION = "mandatory"
        raise AcessoRecusado("email_nao_verificado")


class AdaptadorConta(DefaultAccountAdapter):
    error_messages: ClassVar[dict[str, Any]] = {
        **DefaultAccountAdapter.error_messages,
        "account_inactive": MENSAGEM_GENERICA,
        "email_password_mismatch": MENSAGEM_GENERICA,
        "phone_password_mismatch": MENSAGEM_GENERICA,
        "username_password_mismatch": MENSAGEM_GENERICA,
        "invalid_login": MENSAGEM_GENERICA,
    }

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return False  # cadastro público fora do escopo (§18); a conta nasce por convite

    def clean_email(self, email: str) -> str:
        try:
            return normalizar_email(email)
        except EmailInvalido as erro:
            raise forms.ValidationError(str(erro)) from None

    def authenticate(self, request: HttpRequest, **credentials: Any) -> Any:
        """Autentica e, em seguida, aplica `verificar_acesso`. Recusa vira "credencial inválida"."""
        email = credentials.get("email")
        if email is not None:
            try:
                credentials["email"] = normalizar_email(email)
            except EmailInvalido:
                self.authentication_failed(request, **credentials)
                return None
        usuario = super().authenticate(request, **credentials)
        if usuario is None:
            return None
        try:
            conferir_login(
                usuario, credentials.get("email") or usuario.email_normalizado, Metodo.SENHA
            )
        except AcessoRecusado:
            self.authentication_failed(request, **credentials)
            return None
        return usuario

    def pre_login(self, request: HttpRequest, user: Any, **kwargs: Any) -> HttpResponse | None:
        try:
            conferir_login(user, user.email_normalizado, metodo_do_login(request))
        except AcessoRecusado:
            return HttpResponseRedirect(reverse("account_login"))
        return None

    def get_reauthentication_methods(self, user: Any) -> list[dict[str, Any]]:
        """Com passkey cadastrada, a nova autenticação é só por passkey (nunca por senha)."""
        metodos: list[dict[str, Any]] = super().get_reauthentication_methods(user)
        if user.is_authenticated and tem_passkey(user):
            return [m for m in metodos if m["id"] != "reauthenticate"]
        return metodos

    def respond_user_inactive(self, request: HttpRequest, user: Any) -> HttpResponse:
        return HttpResponseRedirect(reverse("account_login"))  # sem página de conta inativa


class AdaptadorMFA(DefaultMFAAdapter):
    def can_delete_authenticator(self, authenticator: Authenticator) -> bool:
        """A última passkey do administrador não pode ser removida (só o comando de recuperação)."""
        if authenticator.type != Authenticator.Type.WEBAUTHN:
            return True
        outras = Authenticator.objects.filter(
            user_id=authenticator.user_id, type=Authenticator.Type.WEBAUTHN
        ).exclude(pk=authenticator.pk)
        return bool(outras.exists())
