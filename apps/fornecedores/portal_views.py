"""As telas do portal do fornecedor (E13-07). Só leitura: nenhuma rota aceita escrita, e toda
consulta parte do fornecedor vinculado à conta. Uma rodada de outro fornecedor e uma rodada
inexistente dão o mesmo 404."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.contas.permissoes import exige_fornecedor
from apps.fornecedores.portal import csv_do_pedido_formal, dados_da_rodada, dados_do_painel
from apps.pedidos.models import PedidoFormal
from apps.rodadas.models import Rodada


def _rodada_do_fornecedor(request: HttpRequest, pk: int) -> Rodada:
    return get_object_or_404(
        Rodada.objects.filter(fornecedor=request.fornecedor_vinculado),  # type: ignore[attr-defined]
        pk=pk,
    )


@exige_fornecedor
@require_GET
def painel(request: HttpRequest) -> HttpResponse:
    dados = dados_do_painel(request.fornecedor_vinculado)  # type: ignore[attr-defined]
    return render(request, "fornecedores/portal_painel.html", dados)


@exige_fornecedor
@require_GET
def rodada(request: HttpRequest, pk: int) -> HttpResponse:
    dados = dados_da_rodada(_rodada_do_fornecedor(request, pk))
    return render(request, "fornecedores/portal_rodada.html", dados | {"numero": pk})


@exige_fornecedor
@require_GET
def pedido_formal_csv(request: HttpRequest, pk: int) -> HttpResponse:
    pedido = get_object_or_404(PedidoFormal, rodada=_rodada_do_fornecedor(request, pk))
    resposta = HttpResponse(csv_do_pedido_formal(pedido), content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="pedido-formal-{pedido.pk}.csv"'
    return resposta
