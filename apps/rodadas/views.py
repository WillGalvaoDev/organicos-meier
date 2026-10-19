from dataclasses import dataclass
from datetime import datetime

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
from apps.interesses.progresso import progresso_da_rodada
from apps.nucleo.tempo import agora, no_fuso_da_operacao, prazo_encerrado
from apps.rodadas.ciclos import ciclo_vigente
from apps.rodadas.condicoes import MENSAGEM, CondicoesCongeladas
from apps.rodadas.estoque import (
    EstoqueAbaixoDoReservado,
    alterar_estoque,
    estoque_livre,
    incluir_produto_na_rodada,
)
from apps.rodadas.fechamento import (
    TransicaoRecusada,
    iniciar_fechamento,
    prazo_do_fechamento,
    prorrogar_fechamento,
)
from apps.rodadas.forms import FormularioInclusao, FormularioLimite, FormularioProrrogacao
from apps.rodadas.models import EstoqueDaRodada, Etapa, OrigemDoPrazo, PrazoDoFechamento, Rodada
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


def _pagina_congelada(request: HttpRequest, rodada: Rodada) -> HttpResponse:
    """409 só de leitura, com a etapa relida do banco depois da recusa (E03-R03, complemento)."""
    atual = Rodada.objects.select_related("fornecedor").get(pk=rodada.pk)
    return _pagina_do_estoque(request, atual, MENSAGEM, status=409)


def _pagina_do_estoque(
    request: HttpRequest,
    rodada: Rodada,
    erro: str | None = None,
    status: int = 200,
    submetido: Submetido | None = None,
    termino: tuple[str, str | None] | None = None,
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
    editavel = status != 409 and rodada.etapa == Etapa.INTERESSE
    progresso = progresso_da_rodada(rodada)
    bloco = _bloco_do_fechamento(rodada, progresso.atingido, termino)
    if termino is not None and (bloco is None or bloco["tipo"] != "prorrogar"):
        erro = f"Prorrogar fechamento: {termino[1]}"  # sem formulário para receber a mensagem
    contexto = {
        "rodada": rodada,
        "na_rodada": na_rodada,
        "fora_da_rodada": fora_da_rodada,
        "editavel": editavel,
        "progresso": progresso,
        "fechamento": bloco,
        "mensagem_somente_leitura": None if editavel or erro else MENSAGEM,
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
        return _pagina_congelada(request, rodada)
    texto = request.POST.get("limite", "")
    form = FormularioInclusao(request.POST)
    if not form.is_valid():
        # só um id já validado identifica a linha; `produto` inválido vai para o aviso do topo
        alvo_valido = None if "produto" in form.errors else form.cleaned_data.get("produto")
        submetido = Submetido("incluir", alvo_valido, texto)
        return _pagina_do_estoque(request, rodada, _erros(form), submetido=submetido)
    alvo = form.cleaned_data["produto"]
    submetido = Submetido("incluir", alvo, texto)
    produto = Produto.objects.select_related("fornecedor").filter(pk=alvo).first()
    if produto is None:
        return _pagina_do_estoque(request, rodada, "Produto inválido.")
    try:
        incluir_produto_na_rodada(request.user, rodada, produto, form.cleaned_data["limite"])  # type: ignore[arg-type]
    except CondicoesCongeladas:
        return _pagina_congelada(request, rodada)
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
        return _pagina_congelada(request, rodada)
    submetido = Submetido("alterar", estoque.pk, request.POST.get("limite", ""))
    form = FormularioLimite(request.POST)
    if not form.is_valid():
        return _pagina_do_estoque(request, rodada, _erros(form), submetido=submetido)
    try:
        alterar_estoque(request.user, estoque, form.cleaned_data["limite"])  # type: ignore[arg-type]
    except CondicoesCongeladas:
        return _pagina_congelada(request, rodada)
    except (EstoqueAbaixoDoReservado, ValidationError) as erro:
        mensagem = " ".join(erro.messages) if isinstance(erro, ValidationError) else str(erro)
        return _pagina_do_estoque(request, rodada, mensagem, submetido=submetido)
    messages.success(request, "Estoque atualizado.")
    return redirect("rodadas_estoque", pk=rodada.pk)


def _erros(form: Form) -> str:
    erros = form.errors.as_data().values()
    return " ".join(m for lista in erros for erro in lista for m in erro.messages)


def _data_hora(instante: datetime) -> str:
    return f"{no_fuso_da_operacao(instante):%d/%m/%Y %H:%M}"


def _bloco_do_fechamento(
    rodada: Rodada, atingido: bool, termino: tuple[str, str | None] | None
) -> dict[str, object] | None:
    """O que a página de estoque mostra do fechamento, conforme a etapa e o prazo (E06-07)."""
    historico: list[dict[str, str]] = []
    ciclo = ciclo_vigente(rodada)
    if ciclo is not None:
        for prazo in PrazoDoFechamento.objects.filter(ciclo=ciclo).order_by("pk"):
            historico.append(
                {
                    "origem": "Início" if prazo.origem == OrigemDoPrazo.INICIO else "Prorrogação",
                    "termina_em": _data_hora(prazo.termina_em),
                    "registrado_em": _data_hora(prazo.registrado_em),
                }
            )
    bloco: dict[str, object] = {"historico": historico, "tipo": None}
    if rodada.etapa == Etapa.INTERESSE:
        bloco["tipo"] = "iniciar" if atingido else "aguardando_minimo"
        return bloco
    if rodada.etapa not in (Etapa.FECHAMENTO, Etapa.FECHAMENTO_ENCERRADO):
        return bloco if historico else None
    prazo = prazo_do_fechamento(rodada)
    if prazo is None:
        return bloco if historico else None
    bloco["prazo"] = _data_hora(prazo)
    bloco["prazo_campo"] = f"{no_fuso_da_operacao(prazo):%Y-%m-%dT%H:%M}"
    if rodada.etapa == Etapa.FECHAMENTO_ENCERRADO:
        bloco["tipo"] = "encerrado"
    elif prazo_encerrado(agora(), prazo):
        bloco["tipo"] = "vencido"
    else:
        bloco["tipo"] = "prorrogar"
        bloco["termino"] = termino[0] if termino else bloco["prazo_campo"]
        bloco["erro_do_termino"] = termino[1] if termino else None
    return bloco


@somente_administrador
@require_POST
def fechamento_iniciar(request: HttpRequest, pk: int) -> HttpResponse:
    rodada = get_object_or_404(Rodada.objects.select_related("fornecedor"), pk=pk)
    autor: Conta = request.user  # type: ignore[assignment]
    try:
        iniciar_fechamento(autor, rodada)
    except TransicaoRecusada as erro:
        atual = Rodada.objects.select_related("fornecedor").get(pk=rodada.pk)
        return _pagina_do_estoque(request, atual, erro.mensagem, status=409)
    prazo = prazo_do_fechamento(rodada)
    if prazo is not None:
        local = no_fuso_da_operacao(prazo)
        messages.success(
            request,
            f"Fechamento iniciado. Prazo: {local:%d/%m/%Y} às {local:%H:%M} (horário de Brasília).",
        )
    return redirect("rodadas_estoque", pk=rodada.pk)


@somente_administrador
@require_POST
def fechamento_prorrogar(request: HttpRequest, pk: int) -> HttpResponse:
    rodada = get_object_or_404(Rodada.objects.select_related("fornecedor"), pk=pk)
    form = FormularioProrrogacao(request.POST)
    if not form.is_valid():
        texto = request.POST.get("termino", "")[:40]
        return _pagina_do_estoque(
            request, rodada, termino=(texto, "Informe a data e a hora do novo prazo.")
        )
    autor: Conta = request.user  # type: ignore[assignment]
    try:
        novo = prorrogar_fechamento(autor, rodada, form.cleaned_data["termino"])
    except TransicaoRecusada as erro:
        atual = Rodada.objects.select_related("fornecedor").get(pk=rodada.pk)
        return _pagina_do_estoque(request, atual, erro.mensagem, status=409)
    local = no_fuso_da_operacao(novo)
    messages.success(
        request,
        "Prazo do fechamento prorrogado para "
        f"{local:%d/%m/%Y} às {local:%H:%M} (horário de Brasília).",
    )
    return redirect("rodadas_estoque", pk=rodada.pk)
