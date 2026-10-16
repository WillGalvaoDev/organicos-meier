from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms import Form
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.catalogo.models import Produto
from apps.contas.administracao import somente_administrador
from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.interesses.consultas import total_reservado
from apps.rodadas.condicoes import MENSAGEM, CondicoesCongeladas
from apps.rodadas.estoque import (
    EstoqueAbaixoDoReservado,
    alterar_estoque,
    estoque_livre,
    incluir_produto_na_rodada,
)
from apps.rodadas.forms import FormularioInclusao, FormularioLimite
from apps.rodadas.models import EstoqueDaRodada, Etapa, Rodada
from apps.rodadas.servicos import RodadaAtivaExistente, abrir_rodada


@somente_administrador
@require_POST
def abrir(request: HttpRequest, pk: int) -> HttpResponse:
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    autor: Conta = request.user  # type: ignore[assignment]
    try:
        abrir_rodada(autor, fornecedor)
    except RodadaAtivaExistente as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, "Rodada aberta na fase de interesse.")
    return redirect("fornecedores_detalhe", pk=fornecedor.pk)


def _pagina_do_estoque(
    request: HttpRequest, rodada: Rodada, erro: str | None = None, status: int = 200
) -> HttpResponse:
    produtos = Produto.objects.filter(fornecedor_id=rodada.fornecedor_id).order_by("nome", "pk")
    estoques = {e.produto_id: e for e in EstoqueDaRodada.objects.filter(rodada=rodada)}
    na_rodada = []
    fora_da_rodada = []
    for produto in produtos:
        estoque = estoques.get(produto.pk)
        if estoque is None:
            fora_da_rodada.append(produto)
            continue
        estoque.produto = produto
        na_rodada.append(
            {
                "estoque": estoque,
                "produto": produto,
                "reservado": total_reservado(produto),
                "livre": estoque_livre(estoque),
            }
        )
    editavel = rodada.etapa == Etapa.INTERESSE
    contexto = {
        "rodada": rodada,
        "na_rodada": na_rodada,
        "fora_da_rodada": fora_da_rodada,
        "editavel": editavel,
        "mensagem_somente_leitura": None if editavel else MENSAGEM,
        "erro": erro,
    }
    return render(request, "rodadas/estoque.html", contexto, status=status)


@somente_administrador
@require_GET
def estoque(request: HttpRequest, pk: int) -> HttpResponse:
    return _pagina_do_estoque(
        request, get_object_or_404(Rodada.objects.select_related("fornecedor"), pk=pk)
    )


@somente_administrador
@require_POST
def estoque_incluir(request: HttpRequest, pk: int) -> HttpResponse:
    rodada = get_object_or_404(Rodada.objects.select_related("fornecedor"), pk=pk)
    form = FormularioInclusao(request.POST)
    if not form.is_valid():
        return _pagina_do_estoque(request, rodada, _erros(form))
    produto = (
        Produto.objects.select_related("fornecedor").filter(pk=form.cleaned_data["produto"]).first()
    )
    if produto is None:
        return _pagina_do_estoque(request, rodada, "Produto inválido.")
    try:
        incluir_produto_na_rodada(request.user, rodada, produto, form.cleaned_data["limite"])  # type: ignore[arg-type]
    except CondicoesCongeladas as erro:
        return _pagina_do_estoque(request, rodada, str(erro), status=409)
    except ValidationError as erro:
        return _pagina_do_estoque(request, rodada, " ".join(erro.messages))
    messages.success(request, "Produto incluído na rodada.")
    return redirect("rodadas_estoque", pk=rodada.pk)


@somente_administrador
@require_POST
def estoque_alterar(request: HttpRequest, pk: int) -> HttpResponse:
    estoque = get_object_or_404(
        EstoqueDaRodada.objects.select_related("rodada__fornecedor", "produto__fornecedor"), pk=pk
    )
    rodada = estoque.rodada
    form = FormularioLimite(request.POST)
    if not form.is_valid():
        return _pagina_do_estoque(request, rodada, _erros(form))
    try:
        alterar_estoque(request.user, estoque, form.cleaned_data["limite"])  # type: ignore[arg-type]
    except CondicoesCongeladas as erro:
        return _pagina_do_estoque(request, rodada, str(erro), status=409)
    except (EstoqueAbaixoDoReservado, ValidationError) as erro:
        mensagem = " ".join(erro.messages) if isinstance(erro, ValidationError) else str(erro)
        return _pagina_do_estoque(request, rodada, mensagem)
    messages.success(request, "Estoque atualizado.")
    return redirect("rodadas_estoque", pk=rodada.pk)


def _erros(form: Form) -> str:
    erros = form.errors.as_data().values()
    return " ".join(m for lista in erros for erro in lista for m in erro.messages)
