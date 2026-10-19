"""Formulários do estoque da rodada (E03-05); as regras ficam em `estoque.py`."""

import re
from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError

from apps.catalogo.forms import CampoDecimalDigitado
from apps.nucleo.tempo import FUSO_DA_OPERACAO

MAIOR_ID = 9223372036854775807  # maior bigint: o tipo da chave (BigAutoField)


class FormularioLimite(forms.Form):
    """Limite digitado (vírgula ou ponto); vazio significa sem limite."""

    limite = CampoDecimalDigitado(casas=3, required=False)


class FormularioInclusao(FormularioLimite):
    produto = forms.IntegerField(min_value=1, max_value=MAIOR_ID)


FORMATO_DO_PRAZO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}", re.ASCII)


class CampoDoPrazo(forms.CharField):
    """Data e hora exatamente como `AAAA-MM-DDTHH:MM`, lidas no horário de Brasília (E06-R02).

    O `DateTimeField` do Django tenta o leitor ISO 8601 antes dos `input_formats` e aceitaria só
    a data, segundos e deslocamento; por isso o formato é conferido aqui, com dígitos ASCII e
    `T` maiúsculo, e a data e a hora precisam existir. O fuso é sempre o da operação,
    qualquer que seja o fuso ativo.
    """

    def to_python(self, value: object) -> datetime | None:  # type: ignore[override]
        texto = super().to_python(value)  # tira os espaços das pontas
        if not texto:
            return None
        if FORMATO_DO_PRAZO.fullmatch(texto) is None:
            raise ValidationError("Formato inválido.", code="invalid")
        try:
            return datetime.strptime(texto, "%Y-%m-%dT%H:%M").replace(tzinfo=FUSO_DA_OPERACAO)
        except ValueError:
            raise ValidationError("Data ou hora inexistente.", code="invalid") from None


class FormularioProrrogacao(forms.Form):
    """Novo prazo digitado como `AAAA-MM-DDTHH:MM`, no horário de Brasília (E06-07)."""

    termino = CampoDoPrazo()
