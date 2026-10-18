"""Rotas do comprador para interesse (E05-05).

As rotas só convertem a entrada, chamam o serviço e escolhem a resposta. Toda página de erro é
montada com o estado relido do banco depois da transação do serviço, e um 409 nunca oferece
formulário de quantidade para o produto recusado.
"""

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.catalogo.consultas import rodada_ativa_do_catalogo
from apps.catalogo.models import Produto
from apps.catalogo.quantidades import QuantidadeRecusada, formatar_quantidade
from apps.contas.models import Conta
from apps.contas.permissoes import exige_comprador, exige_comprador_ativo
from apps.interesses.apresentacao import Retorno, contexto_do_carrinho, contexto_do_catalogo
from apps.interesses.forms import FormularioInteresse
from apps.interesses.servicos import (
    EstoqueInsuficiente,
    InteresseDesatualizado,
    ProdutoForaDaRodada,
    ReducaoAcimaDoReservado,
    RemocaoAcimaDoPendente,
    definir_interesse,
    remover_pendente,
)
from apps.nucleo.valores import quantidade as converter_quantidade
from apps.rodadas.condicoes import InteressesBloqueados

RECUSAS_DE_QUANTIDADE = (
    QuantidadeRecusada,
    EstoqueInsuficiente,
    ReducaoAcimaDoReservado,
    RemocaoAcimaDoPendente,
)


def _pagina_do_carrinho(request: HttpRequest, retorno: Retorno | None = None) -> HttpResponse:
    conta: Conta = request.user  # type: ignore[assignment]
    status = retorno.status if retorno else 200
    return render(
        request, "interesses/carrinho.html", contexto_do_carrinho(conta, retorno), status=status
    )


def _pagina_de_origem(
    request: HttpRequest, origem: str, produto: Produto | None, retorno: Retorno
) -> HttpResponse:
    """A página de onde veio o envio; o catálogo só se o fornecedor ainda tem rodada ativa."""
    if origem == "catalogo" and produto is not None:
        rodada = rodada_ativa_do_catalogo(produto.fornecedor_id)
        if rodada is not None:
            conta: Conta = request.user  # type: ignore[assignment]
            contexto = contexto_do_catalogo(conta, rodada, retorno)
            return render(
                request, "catalogo/comprador_fornecedor.html", contexto, status=retorno.status
            )
    return _pagina_do_carrinho(request, retorno)


@exige_comprador
@require_GET
def carrinho(request: HttpRequest) -> HttpResponse:
    return _pagina_do_carrinho(request)


def _gravar(request: HttpRequest, acao: str) -> HttpResponse:
    form = FormularioInteresse(request.POST)
    if "produto" in form.errors or "produto" not in form.cleaned_data:
        return _pagina_do_carrinho(request, Retorno(200, topo="Produto inválido."))
    produto = (
        Produto.objects.select_related("fornecedor").filter(pk=form.cleaned_data["produto"]).first()
    )
    if produto is None:
        raise Http404
    origem = form.cleaned_data.get("origem", "carrinho") if acao == "quantidade" else "carrinho"
    texto = request.POST.get("quantidade", "")[:30]
    if "quantidade" in form.errors:
        retorno = Retorno(
            200, None, produto.pk, acao, texto, "Informe a quantidade.", produto_nome=produto.nome
        )
        return _pagina_de_origem(request, origem, produto, retorno)
    conta: Conta = request.user  # type: ignore[assignment]
    valor = form.cleaned_data["quantidade"].replace(",", ".")  # decimal digitado à brasileira
    desatualizado = Retorno(
        409,
        None,
        produto.pk,
        acao,
        None,
        InteresseDesatualizado().mensagem,
        produto_nome=produto.nome,
    )  # o formulário volta com os valores atuais
    estado_valido, esperado = form.estado_esperado()
    if not estado_valido:
        return _pagina_de_origem(request, origem, produto, desatualizado)
    estado = {} if esperado is None else {"esperado": esperado}  # sem estado: chamada simples
    try:
        if acao == "quantidade":
            resumo = definir_interesse(conta, produto, valor, **estado)
        else:
            resumo = remover_pendente(conta, produto, valor, **estado)
    except InteresseDesatualizado:
        return _pagina_de_origem(request, origem, produto, desatualizado)
    except RECUSAS_DE_QUANTIDADE as erro:
        mensagem = getattr(erro, "mensagem", None) or str(erro)
        retorno = Retorno(
            200,
            None,
            produto.pk,
            acao,
            form.cleaned_data["quantidade"],
            mensagem,
            produto_nome=produto.nome,
        )
        return _pagina_de_origem(request, origem, produto, retorno)
    except (InteressesBloqueados, ProdutoForaDaRodada) as erro:
        mensagem = getattr(erro, "mensagem", None) or str(erro)
        retorno = Retorno(409, mensagem, produto.pk, acao, sem_formulario=True)
        return _pagina_de_origem(request, origem, produto, retorno)
    if acao == "quantidade":
        reservado = formatar_quantidade(resumo.reservado)
        texto = f"Interesse atualizado: {produto.nome}, reservado {reservado}"
        texto += f", pendente {formatar_quantidade(resumo.pendente)}." if resumo.pendente else "."
        if converter_quantidade(valor) > 0 and resumo.reservado != converter_quantidade(valor):
            texto += " As pendências da fila, inclusive as suas, são atendidas primeiro."
        messages.success(request, texto)
        if origem == "catalogo":
            return redirect("catalogo_fornecedor", pk=produto.fornecedor_id)
    else:
        pendente = formatar_quantidade(resumo.pendente)
        messages.success(request, f"Pendência removida: {produto.nome}, pendente {pendente}.")
    return redirect("carrinho")


@exige_comprador_ativo
@require_POST
def definir(request: HttpRequest) -> HttpResponse:
    return _gravar(request, "quantidade")


@exige_comprador_ativo
@require_POST
def remover_pendentes(request: HttpRequest) -> HttpResponse:
    return _gravar(request, "pendentes")
