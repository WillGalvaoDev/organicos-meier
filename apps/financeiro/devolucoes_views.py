"""Telas das devoluções do administrador (E10-07).

Só o administrador. As ações exigem passkey recente. Cada recusa de serviço vira uma mensagem na
própria tela, com o status 409 (ou 503, se o provedor não respondeu), sem escrita. O servidor
recusa a ação mesmo que o botão seja forjado: quem decide é o serviço.
"""

from typing import Any

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.contas.administracao import exige_reautenticacao_por_passkey, somente_administrador
from apps.contas.models import Conta
from apps.financeiro.devolucoes import (
    DevolucaoRecusada,
    _exigir_elegivel,
    autorizar_devolucao,
    confirmar_devolucao_excepcional,
    pagamento_da_obrigacao,
    tentar_devolucao_de_novo,
)
from apps.financeiro.estornos import texto_do_motivo
from apps.financeiro.livro import conta_da_obrigacao, saldo
from apps.financeiro.models import (
    ConfirmacaoDeDevolucaoExcepcional,
    ObrigacaoComComprador,
    ParcelaDeDevolucao,
    SituacaoDaParcela,
)
from apps.financeiro.reserva import sem_cobertura_da_obrigacao
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
from apps.pagamentos.models import ChamadaAoProvedor, SituacaoDaChamada

POR_PAGINA = 50
MENSAGEM_DO_PROVEDOR = "Não foi possível consultar o provedor; tente de novo."
S = SituacaoDaParcela
GRUPOS = (
    ("pendentes", "Pendentes de autorização"),
    ("solicitadas", "Solicitadas"),
    ("em-processamento", "Em processamento"),
    ("falhas", "Falhas"),
    ("elegiveis", "Elegíveis para devolução excepcional"),
    ("concluidas", "Concluídas"),
)
GRUPO_DA_SITUACAO = {
    "devida": "pendentes",
    S.SOLICITADA: "solicitadas",
    S.EM_PROCESSAMENTO: "em-processamento",
    S.FALHA_TEMPORARIA: "falhas",
    S.FALHA_DEFINITIVA: "falhas",
    S.ELEGIVEL_EXCEPCIONAL: "elegiveis",
    S.CONCLUIDA: "concluidas",
    S.CONCLUIDA_FORA_DA_PLATAFORMA: "concluidas",
}


def _administrador(request: HttpRequest) -> Conta:
    autor: Conta = request.user  # type: ignore[assignment]
    return autor


def _pagamento(obrigacao: ObrigacaoComComprador) -> str:
    try:
        return str(pagamento_da_obrigacao(obrigacao).id_externo)
    except (ValueError, ObjectDoesNotExist):
        return "-"


def _linha(obrigacao: ObrigacaoComComprador) -> dict[str, Any]:
    parcela = ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).first()
    situacao = "devida" if parcela is None else parcela.situacao
    chamada = None
    if parcela is not None and situacao in (S.SOLICITADA, S.FALHA_TEMPORARIA, S.EM_PROCESSAMENTO):
        chamada = ChamadaAoProvedor.objects.filter(
            alvo=f"parcela:{parcela.pk}", situacao=SituacaoDaChamada.PENDENTE
        ).first()
    return {
        "obrigacao": obrigacao,
        "parcela": parcela,
        "situacao": situacao,
        "grupo": GRUPO_DA_SITUACAO[situacao],
        "valor": obrigacao.devido,
        "motivo": texto_do_motivo(obrigacao.motivo),
        "comprador": obrigacao.comprador.nome if obrigacao.comprador else None,
        "pagamento": _pagamento(obrigacao),
        "chamada": chamada,
    }


@somente_administrador
@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    consulta = ObrigacaoComComprador.objects.select_related("comprador", "pedido").order_by("-pk")
    pagina = Paginator(consulta, POR_PAGINA).get_page(request.GET.get("pagina"))
    linhas = [_linha(o) for o in pagina]
    secoes = [
        {"id": id_, "titulo": titulo, "linhas": [x for x in linhas if x["grupo"] == id_]}
        for id_, titulo in GRUPOS
    ]
    return render(request, "financeiro/devolucoes.html", {"secoes": secoes, "pagina": pagina})


def _detalhe(
    request: HttpRequest,
    obrigacao: ObrigacaoComComprador,
    erro: str | None = None,
    status: int = 200,
) -> HttpResponse:
    linha = _linha(obrigacao)
    parcela = linha["parcela"]
    contexto = {
        **linha,
        "erro": erro,
        "sem_cobertura": sem_cobertura_da_obrigacao(obrigacao),
        "financiado": saldo(conta_da_obrigacao(obrigacao)),
        "historico": list(parcela.historico.order_by("pk")) if parcela is not None else [],
        "confirmacao": getattr(parcela, "confirmacao", None) if parcela is not None else None,
        "pode_autorizar": parcela is None,
        "pode_tentar": parcela is not None and parcela.situacao == S.FALHA_TEMPORARIA,
        "pode_confirmar": parcela is not None and parcela.situacao == S.ELEGIVEL_EXCEPCIONAL,
    }
    return render(request, "financeiro/devolucao.html", contexto, status=status)


@somente_administrador
@require_GET
def detalhe(request: HttpRequest, pk: int) -> HttpResponse:
    return _detalhe(request, get_object_or_404(ObrigacaoComComprador, pk=pk))


def _executar(
    request: HttpRequest, obrigacao: ObrigacaoComComprador, acao: Any, sucesso: str
) -> HttpResponse:
    try:
        acao()
    except ConsultaAoProvedorFalhou:
        return _detalhe(request, obrigacao, MENSAGEM_DO_PROVEDOR, 503)
    except (DevolucaoRecusada, ValueError) as recusa:
        return _detalhe(request, obrigacao, str(recusa), 409)
    messages.success(request, sucesso)
    return redirect("financeiro_devolucao", pk=obrigacao.pk)


@exige_reautenticacao_por_passkey
@require_POST
def autorizar(request: HttpRequest, pk: int) -> HttpResponse:
    obrigacao = get_object_or_404(ObrigacaoComComprador, pk=pk)
    return _executar(
        request,
        obrigacao,
        lambda: autorizar_devolucao(obrigacao, autor=_administrador(request)),
        "Devolução solicitada ao provedor",
    )


@exige_reautenticacao_por_passkey
@require_POST
def tentar_de_novo(request: HttpRequest, pk: int) -> HttpResponse:
    obrigacao = get_object_or_404(ObrigacaoComComprador, pk=pk)
    parcela = ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).first()
    if parcela is None:
        return _detalhe(request, obrigacao, "A devolução ainda não foi autorizada", 409)
    return _executar(
        request,
        obrigacao,
        lambda: tentar_devolucao_de_novo(parcela, autor=_administrador(request)),
        "Nova tentativa solicitada",
    )


@exige_reautenticacao_por_passkey
@require_http_methods(["GET", "POST"])
def excepcional(request: HttpRequest, pk: int) -> HttpResponse:
    obrigacao = get_object_or_404(ObrigacaoComComprador, pk=pk)
    parcela = ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).first()
    try:
        if parcela is None:
            raise DevolucaoRecusada("a devolução pela plataforma não foi tentada")
        _exigir_elegivel(parcela)
    except DevolucaoRecusada as recusa:
        return _detalhe(request, obrigacao, str(recusa), 409)
    if request.method == "GET":
        return render(
            request, "financeiro/devolucao_excepcional.html", {"obrigacao": obrigacao, "dados": {}}
        )
    try:
        confirmar_devolucao_excepcional(
            parcela,
            autor=_administrador(request),
            meio=request.POST.get("meio", ""),
            identificacao=request.POST.get("identificacao", "").strip(),
            justificativa=request.POST.get("justificativa", "").strip(),
            comprovante=request.FILES.get("comprovante"),
        )
    except ConsultaAoProvedorFalhou:
        return _detalhe(request, obrigacao, MENSAGEM_DO_PROVEDOR, 503)
    except DevolucaoRecusada as recusa:
        return _detalhe(request, obrigacao, str(recusa), 409)
    except ValueError as invalido:
        return render(
            request,
            "financeiro/devolucao_excepcional.html",
            {"obrigacao": obrigacao, "dados": request.POST, "erro": str(invalido)},
            status=400,
        )
    messages.success(request, "Devolução feita fora da plataforma confirmada")
    return redirect("financeiro_devolucao", pk=obrigacao.pk)


@somente_administrador
@require_GET
def comprovante(request: HttpRequest, pk: int) -> HttpResponse:
    confirmacao = ConfirmacaoDeDevolucaoExcepcional.objects.filter(obrigacao_id=pk).first()
    if confirmacao is None:
        raise Http404("sem comprovante")
    return FileResponse(  # type: ignore[return-value]
        confirmacao.comprovante.open("rb"),
        as_attachment=True,
        filename=confirmacao.comprovante_nome,
        content_type=confirmacao.comprovante_tipo,
    )
