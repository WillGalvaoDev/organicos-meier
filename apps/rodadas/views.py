from dataclasses import dataclass

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms import Form
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.catalogo.models import Produto
from apps.catalogo.templatetags.catalogo import quantidade_br
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


@dataclass(frozen=True)
class Submetido:
    """O formulário recusado: a ação, o id do produto (inclusão) ou do estoque (alteração) e o
    texto do limite, como veio no POST."""

    acao: str
    alvo: int | None
    texto: str


def _id(request: HttpRequest) -> int | None:
    bruto = request.POST.get("produto", "")
    return int(bruto) if bruto.isdigit() else None


def _pagina_do_estoque(
    request: HttpRequest,
    rodada: Rodada,
    erro: str | None = None,
    status: int = 200,
    submetido: Submetido | None = None,
) -> HttpResponse:
    """Um erro que tem linha correspondente aparece no formulário dela, com o valor digitado;
    os demais ficam no aviso do topo."""
    produtos = Produto.objects.filter(fornecedor_id=rodada.fornecedor_id).order_by("nome", "pk")
    estoques = {e.produto_id: e for e in EstoqueDaRodada.objects.filter(rodada=rodada)}
    na_rodada = []
    fora_da_rodada = []
    erro_da_linha = False
    for produto in produtos:
        estoque = estoques.get(produto.pk)
        if estoque is None:
            devolvido = submetido and submetido.acao == "incluir" and submetido.alvo == produto.pk
            erro_da_linha = erro_da_linha or bool(devolvido)
            fora_da_rodada.append(
                {
                    "produto": produto,
                    "valor": submetido.texto if devolvido and submetido else "",
                    "erro": erro if devolvido else None,
                }
            )
            continue
        estoque.produto = produto
        devolvido = submetido and submetido.acao == "alterar" and submetido.alvo == estoque.pk
        erro_da_linha = erro_da_linha or bool(devolvido)
        na_rodada.append(
            {
                "estoque": estoque,
                "produto": produto,
                "reservado": total_reservado(produto),
                "livre": estoque_livre(estoque),
                "valor": (
                    submetido.texto if devolvido and submetido else quantidade_br(estoque.limite)
                ),
                "erro": erro if devolvido else None,
            }
        )
    editavel = rodada.etapa == Etapa.INTERESSE
    contexto = {
        "rodada": rodada,
        "na_rodada": na_rodada,
        "fora_da_rodada": fora_da_rodada,
        "editavel": editavel,
        "mensagem_somente_leitura": None if editavel else MENSAGEM,
        "erro": None if erro_da_linha else erro,
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
    if rodada.etapa != Etapa.INTERESSE:
        return _pagina_do_estoque(request, rodada, MENSAGEM, status=409)
    texto = request.POST.get("limite", "")
    form = FormularioInclusao(request.POST)
    if not form.is_valid():
        return _pagina_do_estoque(
            request, rodada, _erros(form), submetido=Submetido("incluir", _id(request), texto)
        )
    alvo = form.cleaned_data["produto"]
    submetido = Submetido("incluir", alvo, texto)
    produto = Produto.objects.select_related("fornecedor").filter(pk=alvo).first()
    if produto is None:
        return _pagina_do_estoque(request, rodada, "Produto inválido.")
    try:
        incluir_produto_na_rodada(request.user, rodada, produto, form.cleaned_data["limite"])  # type: ignore[arg-type]
    except CondicoesCongeladas as erro:
        return _pagina_do_estoque(request, rodada, str(erro), status=409)
    except ValidationError as erro:
        return _pagina_do_estoque(request, rodada, " ".join(erro.messages), submetido=submetido)
    messages.success(request, "Produto incluído na rodada.")
    return redirect("rodadas_estoque", pk=rodada.pk)


@somente_administrador
@require_POST
def estoque_alterar(request: HttpRequest, pk: int) -> HttpResponse:
    estoque = get_object_or_404(
        EstoqueDaRodada.objects.select_related("rodada__fornecedor", "produto__fornecedor"), pk=pk
    )
    rodada = estoque.rodada
    if rodada.etapa != Etapa.INTERESSE:
        return _pagina_do_estoque(request, rodada, MENSAGEM, status=409)
    submetido = Submetido("alterar", estoque.pk, request.POST.get("limite", ""))
    form = FormularioLimite(request.POST)
    if not form.is_valid():
        return _pagina_do_estoque(request, rodada, _erros(form), submetido=submetido)
    try:
        alterar_estoque(request.user, estoque, form.cleaned_data["limite"])  # type: ignore[arg-type]
    except CondicoesCongeladas as erro:
        return _pagina_do_estoque(request, rodada, str(erro), status=409)
    except (EstoqueAbaixoDoReservado, ValidationError) as erro:
        mensagem = " ".join(erro.messages) if isinstance(erro, ValidationError) else str(erro)
        return _pagina_do_estoque(request, rodada, mensagem, submetido=submetido)
    messages.success(request, "Estoque atualizado.")
    return redirect("rodadas_estoque", pk=rodada.pk)


def _erros(form: Form) -> str:
    erros = form.errors.as_data().values()
    return " ".join(m for lista in erros for erro in lista for m in erro.messages)
