"""As páginas do endereço de retirada e das regras (E14-03)."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.contas.administracao import somente_administrador
from apps.contas.models import Conta, Papel
from apps.contas.permissoes import exige_login
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.pedidos.endereco_de_retirada import (
    EnderecoRecusado,
    definir_endereco_de_retirada,
    endereco_vigente,
)
from apps.pedidos.models import EnderecoDeRetirada


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
    return render(request, "pedidos/regras.html", {"endereco": endereco_vigente()})
