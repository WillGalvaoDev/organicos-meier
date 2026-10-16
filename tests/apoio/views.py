"""Views só de testes: simulam carrinho, pagamento e área do fornecedor (E02-10, T-25).

Existem apenas para provar os decoradores; nunca entram em `config/urls.py`. O contador mostra se
a view chegou a executar.
"""

from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.contas.permissoes import exige_comprador, exige_comprador_ativo, exige_fornecedor

CHAMADAS: list[str] = []


def zerar_chamadas() -> None:
    CHAMADAS.clear()


@exige_comprador_ativo
def carrinho(request: HttpRequest) -> HttpResponse:
    CHAMADAS.append(f"carrinho:{request.method}")
    return HttpResponse("carrinho")


@exige_comprador_ativo
def pagamento(request: HttpRequest) -> HttpResponse:
    CHAMADAS.append(f"pagamento:{request.method}")
    return HttpResponse("pagamento")


@exige_comprador
def meus_pedidos(request: HttpRequest) -> HttpResponse:
    CHAMADAS.append(f"meus-pedidos:{request.method}")
    return HttpResponse("meus pedidos")


@exige_fornecedor
def painel_do_fornecedor(request: HttpRequest) -> HttpResponse:
    CHAMADAS.append(f"fornecedor:{request.method}")
    return JsonResponse({"fornecedor": request.fornecedor_vinculado.pk})  # type: ignore[attr-defined]
