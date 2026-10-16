"""Formulário de cadastro por convite (E02-05)."""

from typing import Any

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from apps.contas.models import Conta, Convite
from apps.contas.perfil import (
    AvatarInvalido,
    TelefoneInvalido,
    normalizar_telefone,
    processar_avatar,
)


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


class FormularioPerfil(forms.Form):
    """Perfil da própria conta. E-mail, papel, fornecedor e situação não são campos."""

    nome = forms.CharField(max_length=150, strip=True)
    telefone = forms.CharField(required=False, max_length=40)
    avatar = forms.FileField(required=False)
    remover_avatar = forms.BooleanField(required=False)
    whatsapp = forms.BooleanField(required=False)

    def __init__(self, *args: Any, conta: Conta, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.conta = conta
        self.telefone_normalizado: str | None = None
        self.avatar_processado: ContentFile[bytes] | None = None

    def clean_telefone(self) -> str:
        try:
            self.telefone_normalizado = normalizar_telefone(self.cleaned_data["telefone"])
        except TelefoneInvalido:
            raise ValidationError("Informe um telefone brasileiro válido, com DDD.") from None
        return str(self.cleaned_data["telefone"])

    def clean_avatar(self) -> Any:
        arquivo = self.cleaned_data.get("avatar")
        if arquivo:
            try:
                self.avatar_processado = processar_avatar(arquivo)
            except AvatarInvalido:
                raise ValidationError(
                    "Envie uma imagem JPEG, PNG ou WebP de até 2 MB e 4096 x 4096 pixels."
                ) from None
        return arquivo

    def clean(self) -> dict[str, Any]:
        dados: dict[str, Any] = super().clean() or {}
        if "telefone" in dados:
            sem_telefone = self.telefone_normalizado is None
            if dados.get("whatsapp") and sem_telefone and self.conta.whatsapp_consentido_em is None:
                self.add_error(
                    "whatsapp", "Informe um telefone para aceitar mensagens por WhatsApp."
                )
        return dados
