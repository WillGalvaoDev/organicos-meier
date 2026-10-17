"""Formulário do comunicado (E04-06); as regras ficam em `comunicados.py`."""

from django import forms

from apps.notificacoes.servicos import MAIOR_CORPO, MAIOR_TITULO


class FormularioComunicado(forms.Form):
    titulo = forms.CharField(max_length=MAIOR_TITULO, strip=True)
    mensagem = forms.CharField(max_length=MAIOR_CORPO, strip=True, widget=forms.Textarea)
    token = forms.UUIDField(widget=forms.HiddenInput)
