"""Telas do comprador para os pedidos e o pagamento (E08-03)."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.catalogo.models import Unidade
from apps.contas.models import Conta, Situacao
from apps.contas.permissoes import exige_comprador, exige_comprador_ativo
from apps.nucleo.tempo import agora
from apps.pedidos.apresentacao import (
    data_e_hora,
    prazo_do_pedido,
    situacao_do_pagamento,
    texto_da_situacao,
)
from apps.pedidos.models import Pedido
from apps.pedidos.pagamento import PagamentoRecusado, pedir_pagamento


def _do_comprador(request: HttpRequest, pk: int) -> Pedido:
    comprador: Conta = request.user  # type: ignore[assignment]
    pedido: Pedido = get_object_or_404(
        Pedido.objects.select_related("abertura__rodada__fornecedor", "estado"),
        pk=pk,
        comprador=comprador,
    )
    return pedido


def _pagina_do_pedido(
    request: HttpRequest, pedido: Pedido, erro: str | None = None, status: int = 200
) -> HttpResponse:
    comprador: Conta = request.user  # type: ignore[assignment]
    itens = [
        {"item": item, "unidade": Unidade(item.unidade).label}
        for item in pedido.itens.order_by("produto_id")
    ]
    contexto = {
        "pedido": pedido,
        "fornecedor": pedido.abertura.rodada.fornecedor,
        "itens": itens,
        "prazo": data_e_hora(prazo_do_pedido(pedido)),
        "situacao": texto_da_situacao(pedido, agora()),
        "pagamento": situacao_do_pagamento(pedido, comprador.situacao == Situacao.ATIVA),
        "erro": erro,
    }
    return render(request, "pedidos/detalhe.html", contexto, status=status)


@exige_comprador
@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    comprador: Conta = request.user  # type: ignore[assignment]
    pedidos = (
        Pedido.objects.filter(comprador=comprador)
        .select_related("abertura__rodada__fornecedor", "estado")
        .order_by("-pk")
    )
    instante = agora()
    linhas = [
        {
            "pedido": pedido,
            "fornecedor": pedido.abertura.rodada.fornecedor.nome,
            "situacao": texto_da_situacao(pedido, instante),
        }
        for pedido in pedidos
    ]
    return render(request, "pedidos/lista.html", {"linhas": linhas})


@exige_comprador
@require_GET
def detalhe(request: HttpRequest, pk: int) -> HttpResponse:
    return _pagina_do_pedido(request, _do_comprador(request, pk))


@exige_comprador_ativo
@require_POST
def pagar(request: HttpRequest, pk: int) -> HttpResponse:
    pedido = _do_comprador(request, pk)
    comprador: Conta = request.user  # type: ignore[assignment]
    try:
        pedir_pagamento(comprador, pedido)
    except PagamentoRecusado as erro:
        atual = _do_comprador(request, pk)
        return _pagina_do_pedido(request, atual, str(erro), status=409)
    return redirect("pedidos_detalhe", pk=pedido.pk)
