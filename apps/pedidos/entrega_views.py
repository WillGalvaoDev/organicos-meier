"""As rotas do administrador para o recebimento, as ocorrências, a liberação, as retiradas e os
descartes (E14-06). Toda escrita passa pelos serviços das E14-01 a E14-05; as rotas só leem o
formulário, chamam o serviço e escolhem a resposta (302, 400 ou 409).
"""

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.catalogo.models import Produto
from apps.catalogo.quantidades import formatar_quantidade
from apps.catalogo.templatetags.catalogo import reais
from apps.contas.administracao import somente_administrador
from apps.contas.models import Conta
from apps.pedidos.entrega_tela import (
    ETAPAS_DA_ENTREGA,
    pagina_das_ocorrencias,
    pagina_das_retiradas,
    pagina_do_recebimento,
)
from apps.pedidos.liberacao_da_retirada import (
    LiberacaoRecusada,
    liberacao_da_rodada,
    liberar_retirada,
)
from apps.pedidos.models import ItemDoPedido, PedidoFormal
from apps.pedidos.ocorrencias import OcorrenciaRecusada, registrar_ocorrencia
from apps.pedidos.recebimento import RecebimentoRecusado, registrar_recebimento
from apps.pedidos.retirada import RetiradaRecusada, registrar_descarte, registrar_retirada
from apps.rodadas.models import Rodada

MENSAGEM_DO_ACIONAMENTO = "Recarregue a página e tente de novo."
MENSAGEM_DE_CAMPOS = "Preencha todos os campos."
MENSAGEM_DE_REPETIDO = "Este registro já tinha sido feito."


def _rodada_com_pedido_formal(pk: int) -> tuple[Rodada, PedidoFormal]:
    rodada = get_object_or_404(Rodada, pk=pk)
    pedido_formal = get_object_or_404(
        PedidoFormal.objects.select_related("fornecedor", "ciclo"), rodada=rodada
    )
    return rodada, pedido_formal


def _acionamento(request: HttpRequest) -> uuid.UUID | None:
    try:
        return uuid.UUID(request.POST.get("acionamento", ""))
    except ValueError:
        return None


def _quantidade(request: HttpRequest) -> Decimal | None:
    """A quantidade digitada, com vírgula ou ponto; `None` se não vira `Decimal`."""
    texto = request.POST.get("quantidade", "").strip().replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def _numero(request: HttpRequest, campo: str) -> int | None:
    try:
        return int(request.POST.get(campo, ""))
    except ValueError:
        return None


def _valores(request: HttpRequest) -> dict[str, str]:
    return {
        campo: request.POST.get(campo, "")
        for campo in ("produto", "item", "tipo", "quantidade")
        if campo in request.POST
    }


def _quantidade_e_unidade(quantidade: Decimal, unidade: str) -> str:
    return f"{formatar_quantidade(quantidade)} {unidade}"


# --- recebimento e liberação ----------------------------------------------------------------


def _pagina_do_recebimento(
    request: HttpRequest, rodada: Rodada, erro: str = "", status: int = 200
) -> HttpResponse:
    atual = Rodada.objects.get(pk=rodada.pk)
    contexto = pagina_do_recebimento(atual, valores=_valores(request), erro=erro)
    return render(request, "rodadas/recebimento.html", contexto, status=status)


@somente_administrador
@require_GET
def recebimento(request: HttpRequest, pk: int) -> HttpResponse:
    rodada, _pedido_formal = _rodada_com_pedido_formal(pk)
    return _pagina_do_recebimento(request, rodada)


@somente_administrador
@require_POST
def recebimento_registrar(request: HttpRequest, pk: int) -> HttpResponse:
    rodada, _pedido_formal = _rodada_com_pedido_formal(pk)
    autor: Conta = request.user  # type: ignore[assignment]
    acionamento = _acionamento(request)
    if acionamento is None:
        return _pagina_do_recebimento(request, rodada, MENSAGEM_DO_ACIONAMENTO, 400)
    pk_do_produto = _numero(request, "produto")
    quantidade = _quantidade(request)
    produto = Produto.objects.filter(pk=pk_do_produto).first() if pk_do_produto else None
    if produto is None or quantidade is None:
        return _pagina_do_recebimento(request, rodada, MENSAGEM_DE_CAMPOS, 400)
    try:
        resultado = registrar_recebimento(
            autor, rodada, produto, quantidade, acionamento=acionamento
        )
    except RecebimentoRecusado as erro:
        status = 400 if erro.codigo == "acionamento_invalido" else 409
        mensagem = MENSAGEM_DO_ACIONAMENTO if status == 400 else str(erro)
        return _pagina_do_recebimento(request, rodada, mensagem, status)
    if resultado.novo:
        unidade = resultado.recebimento.linha.unidade
        messages.success(
            request,
            "Recebimento registrado: "
            f"{_quantidade_e_unidade(quantidade, unidade)} de {produto.nome}.",
        )
    else:
        messages.success(request, MENSAGEM_DE_REPETIDO)
    return redirect("rodadas_recebimento", pk=rodada.pk)


@somente_administrador
@require_POST
def retirada_liberar(request: HttpRequest, pk: int) -> HttpResponse:
    rodada, _pedido_formal = _rodada_com_pedido_formal(pk)
    autor: Conta = request.user  # type: ignore[assignment]
    if _acionamento(request) is None:
        return _pagina_do_recebimento(request, rodada, MENSAGEM_DO_ACIONAMENTO, 400)
    try:
        liberar_retirada(autor, rodada)
    except LiberacaoRecusada as erro:
        if erro.codigo == "ja_liberada":
            messages.info(request, str(erro))
            return redirect("rodadas_retiradas", pk=rodada.pk)
        return _pagina_do_recebimento(request, rodada, str(erro), 409)
    messages.success(request, "Retirada liberada. Os compradores foram avisados.")
    return redirect("rodadas_retiradas", pk=rodada.pk)


# --- ocorrências ----------------------------------------------------------------------------


def _pagina_das_ocorrencias(
    request: HttpRequest, rodada: Rodada, erro: str = "", status: int = 200
) -> HttpResponse:
    atual = Rodada.objects.get(pk=rodada.pk)
    pedido_formal = PedidoFormal.objects.select_related("ciclo").get(rodada=atual)
    contexto = pagina_das_ocorrencias(atual, pedido_formal, valores=_valores(request), erro=erro)
    return render(request, "rodadas/ocorrencias.html", contexto, status=status)


@somente_administrador
@require_GET
def ocorrencias(request: HttpRequest, pk: int) -> HttpResponse:
    rodada, _pedido_formal = _rodada_com_pedido_formal(pk)
    if rodada.etapa not in ETAPAS_DA_ENTREGA:
        raise Http404
    return _pagina_das_ocorrencias(request, rodada)


def _item_da_rodada(request: HttpRequest, rodada: Rodada) -> ItemDoPedido | None:
    """O item do formulário, que precisa ser de um pedido da rodada da rota (senão 404, sem
    diferença entre "não existe" e "de outra rodada"); `None` se o campo não é um número."""
    pk_do_item = _numero(request, "item")
    if pk_do_item is None:
        return None
    item: ItemDoPedido | None = ItemDoPedido.objects.filter(
        pk=pk_do_item, pedido__abertura__rodada=rodada
    ).first()
    if item is None:
        raise Http404
    return item


@somente_administrador
@require_POST
def ocorrencias_registrar(request: HttpRequest, pk: int) -> HttpResponse:
    rodada, _pedido_formal = _rodada_com_pedido_formal(pk)
    autor: Conta = request.user  # type: ignore[assignment]
    acionamento = _acionamento(request)
    if acionamento is None:
        return _pagina_das_ocorrencias(request, rodada, MENSAGEM_DO_ACIONAMENTO, 400)
    item = _item_da_rodada(request, rodada)
    quantidade = _quantidade(request)
    tipo = request.POST.get("tipo", "")
    if item is None or quantidade is None or not tipo:
        return _pagina_das_ocorrencias(request, rodada, MENSAGEM_DE_CAMPOS, 400)
    try:
        resultado = registrar_ocorrencia(autor, item, quantidade, tipo, acionamento=acionamento)
    except OcorrenciaRecusada as erro:
        status = 400 if erro.codigo == "acionamento_invalido" else 409
        mensagem = MENSAGEM_DO_ACIONAMENTO if status == 400 else str(erro)
        return _pagina_das_ocorrencias(request, rodada, mensagem, status)
    if not resultado.nova:
        messages.success(request, MENSAGEM_DE_REPETIDO)
        return redirect("rodadas_ocorrencias", pk=rodada.pk)
    reembolso = resultado.reembolso.reembolso
    frase = (
        f"Ocorrência registrada. Reembolso de {reais(reembolso.total)} "
        f"(produtos {reais(reembolso.produtos)}, serviço {reais(reembolso.servico)}, "
        f"frete {reais(reembolso.frete)})."
    )
    if resultado.reembolso.sem_cobertura > 0:
        frase += (
            " Parte do reembolso ainda não tem cobertura: "
            f"{reais(resultado.reembolso.sem_cobertura)}. Cubra antes de autorizar a devolução."
        )
    messages.success(request, frase)
    return redirect("rodadas_ocorrencias", pk=rodada.pk)


# --- retiradas e descartes ------------------------------------------------------------------


def _rodada_liberada(pk: int) -> Rodada:
    rodada, _pedido_formal = _rodada_com_pedido_formal(pk)
    if liberacao_da_rodada(rodada) is None:
        raise Http404
    return rodada


def _pagina_das_retiradas(
    request: HttpRequest, rodada: Rodada, erro: str = "", status: int = 200
) -> HttpResponse:
    atual = Rodada.objects.get(pk=rodada.pk)
    contexto = pagina_das_retiradas(atual, valores=_valores(request), erro=erro)
    return render(request, "rodadas/retiradas.html", contexto, status=status)


@somente_administrador
@require_GET
def retiradas(request: HttpRequest, pk: int) -> HttpResponse:
    return _pagina_das_retiradas(request, _rodada_liberada(pk))


def _registrar_da_retirada(request: HttpRequest, pk: int, *, descarte: bool) -> HttpResponse:
    rodada = _rodada_liberada(pk)
    autor: Conta = request.user  # type: ignore[assignment]
    acionamento = _acionamento(request)
    if acionamento is None:
        return _pagina_das_retiradas(request, rodada, MENSAGEM_DO_ACIONAMENTO, 400)
    item = _item_da_rodada(request, rodada)
    quantidade = _quantidade(request)
    if item is None or quantidade is None:
        return _pagina_das_retiradas(request, rodada, MENSAGEM_DE_CAMPOS, 400)
    servico: Any = registrar_descarte if descarte else registrar_retirada
    try:
        resultado = servico(autor, item, quantidade, acionamento=acionamento)
    except RetiradaRecusada as erro:
        status = 400 if erro.codigo == "acionamento_invalido" else 409
        mensagem = MENSAGEM_DO_ACIONAMENTO if status == 400 else str(erro)
        return _pagina_das_retiradas(request, rodada, mensagem, status)
    if resultado.novo:
        rotulo = "Descarte registrado" if descarte else "Retirada registrada"
        messages.success(
            request,
            f"{rotulo}: {_quantidade_e_unidade(quantidade, item.unidade)} de {item.nome}.",
        )
    else:
        messages.success(request, MENSAGEM_DE_REPETIDO)
    return redirect("rodadas_retiradas", pk=rodada.pk)


@somente_administrador
@require_POST
def retiradas_registrar(request: HttpRequest, pk: int) -> HttpResponse:
    return _registrar_da_retirada(request, pk, descarte=False)


@somente_administrador
@require_POST
def descartes_registrar(request: HttpRequest, pk: int) -> HttpResponse:
    return _registrar_da_retirada(request, pk, descarte=True)
