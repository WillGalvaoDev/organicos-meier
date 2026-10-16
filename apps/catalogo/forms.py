"""Formulários de produto (E03-03).

Os formulários só leem e tipam a entrada (decimais digitados com vírgula ou ponto); as regras e
as mensagens por campo vivem nos serviços, que a view chama em seguida.
"""

from typing import Any

from django import forms

from apps.catalogo.models import Unidade
from apps.nucleo.valores import ValorInvalido, ler_decimal_digitado


class CampoDecimalDigitado(forms.CharField):
    """Texto digitado (vírgula ou ponto, sem milhar) convertido em `Decimal`; vazio vira `None`."""

    def __init__(self, *, casas: int, **kwargs: Any) -> None:
        super().__init__(strip=True, **kwargs)
        self.casas = casas

    def clean(self, value: Any) -> Any:
        texto = super().clean(value)
        if not texto:
            return None
        try:
            return ler_decimal_digitado(texto, self.casas)
        except ValorInvalido:
            raise forms.ValidationError("Informe um número válido.") from None


class FormularioEdicaoProduto(forms.Form):
    """Campos editáveis a qualquer momento. Unidade, fornecedor e incremento não são campos."""

    nome = forms.CharField(max_length=150, strip=True)
    descricao = forms.CharField(required=False, max_length=2000, strip=True, widget=forms.Textarea)
    preco = CampoDecimalDigitado(casas=2)
    disponivel = forms.BooleanField(required=False, initial=True)


class FormularioProduto(FormularioEdicaoProduto):
    """Cadastro: os campos de edição mais unidade, incremento e múltiplo."""

    unidade = forms.ChoiceField(choices=Unidade.choices)
    incremento = CampoDecimalDigitado(casas=3)
    multiplo = CampoDecimalDigitado(casas=3, required=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.order_fields(
            ["nome", "descricao", "unidade", "incremento", "multiplo", "preco", "disponivel"]
        )


class FormularioMultiplo(forms.Form):
    multiplo = CampoDecimalDigitado(casas=3, required=False)
