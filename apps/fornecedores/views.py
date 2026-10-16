"""Telas do administrador para fornecedores (E03-01)."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms import Form
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalogo.models import Produto
from apps.contas.administracao import somente_administrador
from apps.contas.models import Conta
from apps.fornecedores.forms import (
    FormularioEdicaoFornecedor,
    FormularioFornecedor,
    FormularioMinimo,
)
from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import alterar_minimo, criar_fornecedor, editar_fornecedor
from apps.rodadas.condicoes import MENSAGEM, CondicoesCongeladas
from apps.rodadas.models import ETAPAS_ATIVAS, Etapa, Rodada


def _erros_do_servico(form: Form, erro: ValidationError) -> None:
    for campo, mensagens in erro.message_dict.items():
        for mensagem in mensagens:
            form.add_error(campo if campo in form.fields else None, mensagem)


@somente_administrador
def lista(request: HttpRequest) -> HttpResponse:
    fornecedores = Fornecedor.objects.order_by("nome", "pk")
    return render(request, "fornecedores/lista.html", {"fornecedores": fornecedores})


@somente_administrador
def novo(request: HttpRequest) -> HttpResponse:
    form = FormularioFornecedor(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            fornecedor = criar_fornecedor(
                request.user,  # type: ignore[arg-type]
                nome=form.cleaned_data["nome"],
                email_pedido=form.cleaned_data["email_pedido"],
                minimo=form.cleaned_data["minimo"],
                prazo_entrega_dias=form.cleaned_data["prazo_entrega_dias"],
                informacoes_frete=form.cleaned_data["informacoes_frete"],
            )
        except ValidationError as erro:
            _erros_do_servico(form, erro)
        else:
            messages.success(request, "Fornecedor cadastrado.")
            return redirect("fornecedores_detalhe", pk=fornecedor.pk)
    return render(request, "fornecedores/formulario.html", {"form": form, "fornecedor": None})


@somente_administrador
def detalhe(request: HttpRequest, pk: int) -> HttpResponse:
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    contas = Conta.objects.filter(fornecedor=fornecedor).order_by("nome", "pk")
    rodada = Rodada.objects.filter(fornecedor=fornecedor, etapa__in=ETAPAS_ATIVAS).first()
    return render(
        request,
        "fornecedores/detalhe.html",
        {
            "fornecedor": fornecedor,
            "contas": contas,
            "rodada": rodada,
            "produtos": Produto.objects.filter(fornecedor=fornecedor).order_by("nome", "pk"),
        },
    )


@somente_administrador
def editar(request: HttpRequest, pk: int) -> HttpResponse:
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    form = FormularioEdicaoFornecedor(
        request.POST if request.method == "POST" else None,
        initial={
            "nome": fornecedor.nome,
            "email_pedido": fornecedor.email_pedido,
            "prazo_entrega_dias": fornecedor.prazo_entrega_dias,
            "informacoes_frete": fornecedor.informacoes_frete,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            editar_fornecedor(request.user, fornecedor, **form.cleaned_data)  # type: ignore[arg-type]
        except ValidationError as erro:
            _erros_do_servico(form, erro)
        else:
            messages.success(request, "Fornecedor atualizado.")
            return redirect("fornecedores_detalhe", pk=fornecedor.pk)
    return render(request, "fornecedores/formulario.html", {"form": form, "fornecedor": fornecedor})


@somente_administrador
def minimo(request: HttpRequest, pk: int) -> HttpResponse:
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    contexto: dict[str, object] = {"fornecedor": fornecedor, "mensagem_congelada": None}
    if request.method == "POST":
        form = FormularioMinimo(request.POST)
        if form.is_valid():
            try:
                alterar_minimo(request.user, fornecedor, form.cleaned_data["minimo"])  # type: ignore[arg-type]
            except ValidationError as erro:
                _erros_do_servico(form, erro)
            except CondicoesCongeladas as erro:
                contexto["mensagem_congelada"] = str(erro)
                return render(request, "fornecedores/minimo.html", contexto, status=409)
            else:
                messages.success(request, "Mínimo atualizado.")
                return redirect("fornecedores_detalhe", pk=fornecedor.pk)
    else:
        form = FormularioMinimo(initial={"minimo": str(fornecedor.minimo).replace(".", ",")})
        if not Rodada.objects.filter(fornecedor=fornecedor, etapa=Etapa.INTERESSE).exists():
            contexto["mensagem_congelada"] = MENSAGEM
    contexto["form"] = form
    return render(request, "fornecedores/minimo.html", contexto)
