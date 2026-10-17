"""Adaptador do allauth (E02-02): identidade autorizada, banimento e mensagem única de recusa."""

import uuid
from typing import Any, ClassVar

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.authentication import get_authentication_records
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.mfa.models import Authenticator
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from django import forms
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from apps.contas import google as apoio_google
from apps.contas.acesso import AcessoRecusado, Metodo, verificar_acesso
from apps.contas.administracao import tem_passkey
from apps.contas.convites import ConviteInvalido, validar_convite
from apps.contas.emails import EmailInvalido, email_banido, normalizar_email
from apps.contas.google import CHAVE_CONVITE_PENDENTE, recusar_login_google
from apps.contas.models import Conta
from apps.notificacoes.acesso import enviar_email_de_acesso
from apps.notificacoes.models import CONTA_ALLAUTH

MENSAGEM_GENERICA = "Não foi possível entrar com esses dados."


def metodo_do_login(request: HttpRequest) -> Metodo:
    """Método do login em curso, pelos registros de autenticação da sessão."""
    registros = get_authentication_records(request)
    if registros and registros[-1].get("method") == "mfa" and registros[-1].get("passwordless"):
        return Metodo.PASSKEY
    if registros and registros[-1].get("method") == "link":
        return Metodo.LINK
    if registros and registros[-1].get("method") == "socialaccount":
        return Metodo.GOOGLE
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

    def send_mail(
        self, template_prefix: str, email: str | list[str], context: dict[str, Any]
    ) -> None:
        """Os e-mails do allauth (recuperação de senha) saem pelo registro de envios (E04-05).

        A mensagem é montada na requisição (o corpo leva o token e não é guardado); o envio e o
        registro só acontecem depois da confirmação da transação em curso (E04-R02).
        """
        mensagem = self.render_mail(template_prefix, email, context)
        destino = mensagem.to[0]
        conta = Conta.objects.filter(email_normalizado=destino).first()
        referencia = uuid.uuid4()

        def enviar() -> None:
            enviar_email_de_acesso(
                CONTA_ALLAUTH,
                destino=destino,
                assunto=mensagem.subject,
                corpo=mensagem.body,
                conta=conta,
                referencia=referencia,
                modelo=template_prefix,
            )

        transaction.on_commit(enviar)

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

    def set_password(self, user: Any, password: str) -> None:
        """Grava só a senha. O padrão do allauth chama `user.save()` e reescreveria todas as
        colunas (inclusive `situacao`) com os valores lidos no início da requisição."""
        user.set_password(password)
        user.save(update_fields=["password"])

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


class AdaptadorContaSocial(DefaultSocialAccountAdapter):
    """Associa o Google à conta pelo e-mail normalizado; só cria conta com convite válido.

    Decisão no retorno do Google (spec E02-07), nesta ordem: conta social já vinculada (o e-mail
    do Google precisa continuar igual ao da conta), conta com o mesmo e-mail normalizado (vincula
    e entra) ou convite pendente na sessão para o mesmo e-mail (segue para a conclusão do cadastro).
    Qualquer outra situação é recusa única, sem criar nada.
    """

    @staticmethod
    def _email_verificado(sociallogin: SocialLogin) -> str | None:
        return apoio_google.email_verificado_do_google(sociallogin.account.extra_data)

    @staticmethod
    def _convite_pendente_valido(request: HttpRequest, email: str) -> bool:
        token = request.session.get(CHAVE_CONVITE_PENDENTE)
        if not token:
            return False
        try:
            convite = validar_convite(token)
        except ConviteInvalido:
            return False
        return bool(convite.email_normalizado == email)

    @staticmethod
    def _recusar(request: HttpRequest) -> None:
        raise ImmediateHttpResponse(recusar_login_google(request))

    def pre_social_login(self, request: HttpRequest, sociallogin: SocialLogin) -> None:
        email = self._email_verificado(sociallogin)
        if email is None:
            self._recusar(request)
            return
        if sociallogin.is_existing:  # conta social já vinculada
            conta = sociallogin.user
            if conta.email_normalizado != email:
                self._recusar(request)
            self._exigir_acesso(request, conta, email)
            request.session.pop(CHAVE_CONVITE_PENDENTE, None)
            return
        # Leitura, `verificar_acesso` e vínculo na mesma transação, com a conta travada: o
        # `connect` do allauth grava a conta inteira e, sem a trava, desfaria uma suspensão ou
        # remoção feita entre a leitura e o vínculo. Uma recusa aqui desfaz a transação.
        try:
            with transaction.atomic():
                conta = Conta.objects.select_for_update().filter(email_normalizado=email).first()
                if conta is not None:  # mesmo e-mail normalizado: vincula, nunca cria outra conta
                    verificar_acesso(conta, email, Metodo.GOOGLE)
                    sociallogin.connect(request, conta)
        except AcessoRecusado:
            self._recusar(request)
        if conta is not None:
            request.session.pop(CHAVE_CONVITE_PENDENTE, None)
            return
        if email_banido(email) or not self._convite_pendente_valido(request, email):
            self._recusar(request)

    def _exigir_acesso(self, request: HttpRequest, conta: Conta, email: str) -> None:
        try:
            verificar_acesso(conta, email, Metodo.GOOGLE)
        except AcessoRecusado:
            self._recusar(request)

    def is_open_for_signup(self, request: HttpRequest, sociallogin: SocialLogin) -> bool:
        email = self._email_verificado(sociallogin)
        return email is not None and self._convite_pendente_valido(request, email)

    def is_auto_signup_allowed(self, request: HttpRequest, sociallogin: SocialLogin) -> bool:
        return False  # a conta nasce no formulário de conclusão, que consome o convite

    def on_authentication_error(
        self,
        request: HttpRequest,
        provider: Any,
        error: Any = None,
        exception: Any = None,
        extra_context: Any = None,
    ) -> None:
        self._recusar(request)
