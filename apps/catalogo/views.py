from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms import Form
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalogo.consultas import (
    fornecedores_no_catalogo,
    produtos_da_rodada,
    rodada_ativa_do_catalogo,
)
from apps.catalogo.forms import (
    FormularioEdicaoProduto,
    FormularioIncremento,
    FormularioMultiplo,
    FormularioProduto,
)
from apps.catalogo.models import Produto
from apps.catalogo.quantidades import (
    IncrementoInvalido,
    MultiploInvalido,
    QuantidadeRecusada,
    formatar_quantidade,
)
from apps.catalogo.servicos import (
    IncrementoIncompativel,
    alterar_incremento,
    alterar_multiplo,
    criar_produto,
    editar_produto,
)
from apps.contas.administracao import somente_administrador
from apps.contas.permissoes import exige_comprador
from apps.fornecedores.models import Fornecedor
from apps.rodadas.condicoes import MENSAGEM, CondicoesCongeladas, condicoes_editaveis


def _erros_do_servico(form: Form, erro: ValidationError) -> None:
    for campo, mensagens in erro.message_dict.items():
        for mensagem in mensagens:
            form.add_error(campo if campo in form.fields else None, mensagem)


def _erro_de_quantidade(form: Form, erro: QuantidadeRecusada) -> None:
    if isinstance(erro, IncrementoInvalido):
        campo = "incremento"
    elif isinstance(erro, MultiploInvalido):
        campo = "multiplo"
    else:
        campo = None
    form.add_error(campo, str(erro))


def _texto_decimal(valor: Decimal, virgula: bool = True) -> str:
    texto = str(valor)
    return texto.replace(".", ",") if virgula else texto


@somente_administrador
def novo(request: HttpRequest, pk: int) -> HttpResponse:
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    form = FormularioProduto(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        try:
            criar_produto(
                request.user,  # type: ignore[arg-type]
                fornecedor,
                nome=dados["nome"],
                descricao=dados["descricao"],
                unidade=dados["unidade"],
                incremento=dados["incremento"],
                preco=dados["preco"],
                multiplo=dados["multiplo"],
                disponivel=dados["disponivel"],
            )
        except QuantidadeRecusada as erro:
            _erro_de_quantidade(form, erro)
        except ValidationError as erro:
            _erros_do_servico(form, erro)
        else:
            messages.success(request, "Produto cadastrado.")
            return redirect("fornecedores_detalhe", pk=fornecedor.pk)
    return render(
        request,
        "catalogo/formulario.html",
        {"form": form, "fornecedor": fornecedor, "produto": None},
    )


@somente_administrador
def detalhe(request: HttpRequest, pk: int) -> HttpResponse:
    produto = get_object_or_404(Produto.objects.select_related("fornecedor"), pk=pk)
    form = FormularioEdicaoProduto(
        request.POST if request.method == "POST" else None,
        initial={
            "nome": produto.nome,
            "descricao": produto.descricao,
            "preco": _texto_decimal(produto.preco),
            "disponivel": produto.disponivel,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            editar_produto(request.user, produto, **form.cleaned_data)  # type: ignore[arg-type]
        except ValidationError as erro:
            _erros_do_servico(form, erro)
        else:
            messages.success(request, "Produto atualizado.")
            return redirect("fornecedores_detalhe", pk=produto.fornecedor_id)
    return render(
        request,
        "catalogo/formulario.html",
        {"form": form, "fornecedor": produto.fornecedor, "produto": produto},
    )


@somente_administrador
def multiplo(request: HttpRequest, pk: int) -> HttpResponse:
    produto = get_object_or_404(Produto.objects.select_related("fornecedor"), pk=pk)
    contexto: dict[str, object] = {"produto": produto, "mensagem_congelada": None}
    if request.method == "POST":
        if not condicoes_editaveis(produto.fornecedor):
            contexto["mensagem_congelada"] = MENSAGEM
            return render(request, "catalogo/multiplo.html", contexto, status=409)
        form = FormularioMultiplo(request.POST)
        if form.is_valid():
            try:
                alterar_multiplo(
                    request.user,  # type: ignore[arg-type]
                    produto,
                    form.cleaned_data["multiplo"],
                )
            except MultiploInvalido as erro:
                form.add_error("multiplo", str(erro))
            except CondicoesCongeladas as erro:
                contexto["mensagem_congelada"] = str(erro)
                return render(request, "catalogo/multiplo.html", contexto, status=409)
            else:
                messages.success(request, "Múltiplo atualizado.")
                return redirect("fornecedores_detalhe", pk=produto.fornecedor_id)
    else:
        inicial = "" if produto.multiplo is None else formatar_quantidade(produto.multiplo)
        form = FormularioMultiplo(initial={"multiplo": inicial})
        if not condicoes_editaveis(produto.fornecedor):
            contexto["mensagem_congelada"] = MENSAGEM
    contexto["form"] = form
    return render(request, "catalogo/multiplo.html", contexto)


@somente_administrador
def incremento(request: HttpRequest, pk: int) -> HttpResponse:
    produto = get_object_or_404(Produto.objects.select_related("fornecedor"), pk=pk)
    contexto: dict[str, object] = {"produto": produto, "mensagem_congelada": None}
    if request.method == "POST":
        if not condicoes_editaveis(produto.fornecedor):
            contexto["mensagem_congelada"] = MENSAGEM
            return render(request, "catalogo/incremento.html", contexto, status=409)
        form = FormularioIncremento(request.POST)
        if form.is_valid():
            try:
                alterar_incremento(
                    request.user,  # type: ignore[arg-type]
                    produto,
                    form.cleaned_data["incremento"],
                )
            except (IncrementoInvalido, IncrementoIncompativel) as erro:
                form.add_error("incremento", str(erro))
            except CondicoesCongeladas as erro:
                contexto["mensagem_congelada"] = str(erro)
                return render(request, "catalogo/incremento.html", contexto, status=409)
            else:
                messages.success(request, "Incremento atualizado.")
                return redirect("fornecedores_detalhe", pk=produto.fornecedor_id)
    else:
        form = FormularioIncremento(initial={"incremento": formatar_quantidade(produto.incremento)})
        if not condicoes_editaveis(produto.fornecedor):
            contexto["mensagem_congelada"] = MENSAGEM
    contexto["form"] = form
    return render(request, "catalogo/incremento.html", contexto)


@exige_comprador
def catalogo(request: HttpRequest) -> HttpResponse:
    return render(request, "catalogo/comprador_lista.html", {"rodadas": fornecedores_no_catalogo()})


@exige_comprador
def catalogo_do_fornecedor(request: HttpRequest, pk: int) -> HttpResponse:
    rodada = rodada_ativa_do_catalogo(pk)
    if rodada is None:
        raise Http404
    contexto = {"rodada": rodada, "itens": produtos_da_rodada(rodada)}
    return render(request, "catalogo/comprador_fornecedor.html", contexto)
