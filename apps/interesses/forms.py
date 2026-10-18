"""Formulário das rotas de interesse (E05-05); toda regra fica nos serviços."""

from django import forms

from apps.interesses.servicos import ResumoDoInteresse
from apps.nucleo.valores import ValorInvalido, quantidade
from apps.rodadas.forms import MAIOR_ID


class FormularioInteresse(forms.Form):
    """`quantidade` é só texto aqui: quem converte e valida é o serviço."""

    produto = forms.IntegerField(min_value=1, max_value=MAIOR_ID)
    quantidade = forms.CharField(max_length=30, strip=True)
    origem = forms.CharField(required=False)
    reservado_atual = forms.CharField(max_length=30, required=False)
    pendente_atual = forms.CharField(max_length=30, required=False)

    def clean_origem(self) -> str:
        return "catalogo" if self.cleaned_data.get("origem") == "catalogo" else "carrinho"

    def estado_esperado(self) -> tuple[bool, ResumoDoInteresse | None]:
        """O estado que a página mostrou: `(True, None)` se nenhum campo veio (cliente que não
        é a página), `(True, resumo)` se vieram os dois válidos e `(False, None)` em qualquer
        outro caso, que tem a resposta do estado desatualizado (E05-R02)."""
        textos = [self.data.get("reservado_atual", ""), self.data.get("pendente_atual", "")]
        if not any(t.strip() for t in textos):
            return True, None
        try:
            reservado, pendente = (quantidade(t.strip().replace(",", ".")) for t in textos)
        except ValorInvalido:
            return False, None
        if reservado < 0 or pendente < 0:
            return False, None
        return True, ResumoDoInteresse(reservado, pendente)
