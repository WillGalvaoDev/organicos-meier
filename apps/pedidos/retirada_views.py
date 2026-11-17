"""As páginas do endereço de retirada e das regras (E14-03 e E16-06)."""

from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.contas.administracao import somente_administrador
from apps.contas.models import Conta, Papel
from apps.contas.permissoes import exige_login
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.pedidos import calculo, liberacao_da_retirada, prazos
from apps.pedidos.endereco_de_retirada import (
    EnderecoRecusado,
    definir_endereco_de_retirada,
    endereco_vigente,
)
from apps.pedidos.models import EnderecoDeRetirada
from apps.rodadas import fechamento

POR_EXTENSO = {
    1: "um",
    2: "dois",
    3: "três",
    4: "quatro",
    5: "cinco",
    6: "seis",
    7: "sete",
    8: "oito",
    9: "nove",
}


def _pagina_do_endereco(
    request: HttpRequest, texto: str | None = None, erro: str = "", status: int = 200
) -> HttpResponse:
    vigente = endereco_vigente()
    historico = [
        {
            "quando": f"{no_fuso_da_operacao(e.registrado_em):%d/%m/%Y %H:%M}",
            "autor": e.autor.nome,
            "texto": e.texto,
        }
        for e in EnderecoDeRetirada.objects.select_related("autor").order_by("-pk")
    ]
    contexto = {
        "vigente": vigente,
        "texto": vigente.texto if texto is None and vigente is not None else (texto or ""),
        "erro": erro,
        "historico": historico,
    }
    return render(request, "pedidos/endereco_de_retirada.html", contexto, status=status)


@somente_administrador
@require_http_methods(["GET", "POST"])
def endereco_de_retirada(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        return _pagina_do_endereco(request)
    autor: Conta = request.user  # type: ignore[assignment]
    texto = request.POST.get("texto", "")
    try:
        definir_endereco_de_retirada(autor, texto)
    except EnderecoRecusado as erro:
        return _pagina_do_endereco(request, texto, str(erro), 400)
    messages.success(request, "Endereço de retirada atualizado.")
    return redirect("retirada_endereco")


@exige_login
@require_GET
def regras(request: HttpRequest) -> HttpResponse:
    """As regras de funcionamento, só a seção de retirada por enquanto. O fornecedor não vê: o
    endereço e as regras de retirada não estão na lista da §2."""
    if getattr(request.user, "papel", None) not in (Papel.COMPRADOR, Papel.ADMINISTRADOR):
        raise PermissionDenied
    return render(
        request,
        "pedidos/regras.html",
        {"endereco": endereco_vigente(), **_valores_das_regras()},
    )


def _numero(valor: Any) -> str:
    """O número sem zeros à direita e com vírgula decimal (`5`, `7`, `5,5`)."""
    return f"{valor.normalize():f}".replace(".", ",")


def _valores_das_regras() -> dict[str, Any]:
    """Os números da página, lidos das constantes que o servidor aplica (E16-06, regra 3): a
    página não diverge do cálculo do pedido, dos prazos nem da retirada."""
    dias = liberacao_da_retirada.PRAZO_DE_RETIRADA.days
    return {
        "taxa_de_servico": _numero(calculo.TAXA_DE_SERVICO * 100),
        "horas_do_fechamento": fechamento.HORAS_DO_FECHAMENTO,
        "horas_do_pagamento": prazos.HORAS_DO_PRAZO_DE_PAGAMENTO,
        "horas_depois_do_prazo": prazos.HORAS_DA_MARGEM - prazos.HORAS_DO_PRAZO_DE_PAGAMENTO,
        "dias_de_retirada": POR_EXTENSO.get(dias, str(dias)),
    }
