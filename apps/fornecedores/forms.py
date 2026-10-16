"""Formulários do administrador para fornecedores (E03-01).

O formulário só lê e tipa a entrada; as regras de negócio e as mensagens por campo vivem nos
serviços (`criar_fornecedor`, `editar_fornecedor`), que a view chama em seguida.
"""

from typing import Any

from django import forms


class FormularioEdicaoFornecedor(forms.Form):
    """Campos editáveis a qualquer momento. O mínimo não é campo daqui (E03-02)."""

    nome = forms.CharField(max_length=150, strip=True)
    email_pedido = forms.CharField(max_length=254, strip=True)
    prazo_entrega_dias = forms.IntegerField(min_value=1, max_value=365)
    informacoes_frete = forms.CharField(required=False, max_length=1000, strip=True)


class FormularioFornecedor(FormularioEdicaoFornecedor):
    """Cadastro: os campos de edição mais o mínimo, digitado como texto (vírgula ou ponto)."""

    minimo = forms.CharField(max_length=20, strip=True)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.order_fields(
            ["nome", "email_pedido", "minimo", "prazo_entrega_dias", "informacoes_frete"]
        )


class FormularioMinimo(forms.Form):
    """Novo mínimo, digitado como texto (vírgula ou ponto); o serviço valida (E03-02)."""

    minimo = forms.CharField(max_length=20, strip=True)
