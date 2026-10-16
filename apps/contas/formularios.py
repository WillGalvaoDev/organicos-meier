"""Formulários de recuperação de acesso (E02-02)."""

from typing import Any

from allauth.account.forms import ResetPasswordForm, ResetPasswordKeyForm
from django import forms

from apps.contas.acesso import AcessoRecusado, Metodo, verificar_acesso
from apps.contas.emails import EmailInvalido, normalizar_email
from apps.contas.models import Papel
from apps.fornecedores.models import Fornecedor


class FormularioRecuperacao(ResetPasswordForm):
    """O e-mail só sai quando existe conta e `verificar_acesso(..., senha)` não recusa.

    A resposta é igual para qualquer e-mail: contas recusadas simplesmente saem da lista de
    envio, sem mudar o que o formulário devolve.
    """

    def clean_email(self) -> Any:
        email = super().clean_email()
        permitidas = []
        for conta in self.users:  # type: ignore[has-type]
            try:
                verificar_acesso(conta, conta.email_normalizado, Metodo.SENHA)
            except AcessoRecusado:
                continue
            permitidas.append(conta)
        self.users = permitidas
        return email


class FormularioNovaSenha(ResetPasswordKeyForm):
    """Revalida a situação da conta no momento de definir a senha (banimento ou remoção)."""

    def clean(self) -> Any:
        dados = super().clean()
        if self.user is not None:
            try:
                verificar_acesso(self.user, self.user.email_normalizado, Metodo.SENHA)
            except AcessoRecusado:
                raise forms.ValidationError(
                    "Não foi possível redefinir a senha com esse link."
                ) from None
        return dados


class FormularioConvite(forms.Form):
    """Emissão de convite. O servidor valida tudo de novo (papel e fornecedor adulterados)."""

    email = forms.CharField(max_length=254)
    papel = forms.ChoiceField(
        choices=[(Papel.COMPRADOR.value, "Comprador"), (Papel.FORNECEDOR.value, "Fornecedor")]
    )
    fornecedor = forms.ModelChoiceField(
        queryset=Fornecedor.objects.order_by("nome"), required=False, empty_label="—"
    )


class FormularioPedidoDeLink(forms.Form):
    """Pedido de link de acesso. E-mail mal formado é o único erro visível."""

    email = forms.CharField(max_length=254)

    def clean_email(self) -> str:
        email = str(self.cleaned_data["email"])
        try:
            normalizar_email(email)
        except EmailInvalido:
            raise forms.ValidationError("Informe um e-mail válido.") from None
        return email
