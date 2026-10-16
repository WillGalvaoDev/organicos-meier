"""Adaptador do allauth (E02-02): identidade autorizada, banimento e mensagem única de recusa."""

from typing import Any, ClassVar

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from django import forms
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from apps.contas.acesso import AcessoRecusado, Metodo, verificar_acesso
from apps.contas.emails import EmailInvalido, normalizar_email
from apps.contas.models import Conta, Papel

MENSAGEM_GENERICA = "Não foi possível entrar com esses dados."


def conferir_login_por_senha(conta: Conta, email: str) -> None:
    """Regras de entrada por senha. Levanta `AcessoRecusado` (códigos internos).

    A recusa do administrador é temporária: até a E02-03 entregar a passkey obrigatória, nunca
    existe sessão de administrador só com senha. Essa linha sai na E02-03.
    """
    verificar_acesso(conta, email, Metodo.SENHA)
    if conta.papel == Papel.ADMINISTRADOR:
        raise AcessoRecusado("administrador_exige_passkey")
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
            conferir_login_por_senha(usuario, credentials.get("email") or usuario.email_normalizado)
        except AcessoRecusado:
            self.authentication_failed(request, **credentials)
            return None
        return usuario

    def pre_login(self, request: HttpRequest, user: Any, **kwargs: Any) -> HttpResponse | None:
        try:
            conferir_login_por_senha(user, user.email_normalizado)
        except AcessoRecusado:
            return HttpResponseRedirect(reverse("account_login"))
        return None

    def respond_user_inactive(self, request: HttpRequest, user: Any) -> HttpResponse:
        return HttpResponseRedirect(reverse("account_login"))  # sem página de conta inativa
