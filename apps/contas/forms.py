"""Formulário de cadastro por convite (E02-05)."""

from typing import Any

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.contas.models import Conta, Convite


class FormularioCadastroPorConvite(forms.Form):
    """Nome, senha e confirmação. E-mail, papel e fornecedor vêm sempre do convite."""

    nome = forms.CharField(max_length=150, strip=True)
    senha = forms.CharField(widget=forms.PasswordInput)
    confirmacao = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args: Any, convite: Convite, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.convite = convite

    def clean(self) -> dict[str, Any]:
        dados: dict[str, Any] = super().clean() or {}
        senha = dados.get("senha")
        if senha and dados.get("confirmacao") != senha:
            self.add_error("confirmacao", "A confirmação não confere com a senha.")
        elif senha:
            provisoria = Conta(
                email_normalizado=self.convite.email_normalizado, nome=dados.get("nome", "")
            )
            try:
                validate_password(senha, user=provisoria)
            except ValidationError as erro:
                self.add_error("senha", erro)
        return dados


class FormularioConclusaoGoogle(forms.Form):
    """Conclusão do cadastro com Google: só o nome, já preenchido com o do Google."""

    nome = forms.CharField(max_length=150, strip=True)
