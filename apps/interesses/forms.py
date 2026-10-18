"""Formulário das rotas de interesse (E05-05); toda regra fica nos serviços."""

from django import forms

from apps.rodadas.forms import MAIOR_ID


class FormularioInteresse(forms.Form):
    """`quantidade` é só texto aqui: quem converte e valida é o serviço."""

    produto = forms.IntegerField(min_value=1, max_value=MAIOR_ID)
    quantidade = forms.CharField(max_length=30, strip=True)
    origem = forms.CharField(required=False)

    def clean_origem(self) -> str:
        return "catalogo" if self.cleaned_data.get("origem") == "catalogo" else "carrinho"
