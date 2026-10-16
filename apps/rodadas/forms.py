"""Formulários do estoque da rodada (E03-05); as regras ficam em `estoque.py`."""

from django import forms

from apps.catalogo.forms import CampoDecimalDigitado


class FormularioLimite(forms.Form):
    """Limite digitado (vírgula ou ponto); vazio significa sem limite."""

    limite = CampoDecimalDigitado(casas=3, required=False)


class FormularioInclusao(FormularioLimite):
    produto = forms.IntegerField(min_value=1)
