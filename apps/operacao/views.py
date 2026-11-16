"""As rotas do administrador da E15: a ciência do alerta e o histórico de ações."""

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.contas.administracao import somente_administrador
from apps.contas.models import Conta
from apps.financeiro.models import AlertaFinanceiro
from apps.operacao.ciencia import CienciaRecusada, dar_ciencia
from apps.operacao.historico import contexto_do_historico


@somente_administrador
@require_POST
def ciencia(request: HttpRequest, pk: int) -> HttpResponse:
    alerta = get_object_or_404(AlertaFinanceiro, pk=pk)
    autor: Conta = request.user  # type: ignore[assignment]
    try:
        dar_ciencia(autor, alerta)
    except CienciaRecusada as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, "Ciência registrada.")
    return redirect("painel_administracao")


@somente_administrador
@require_GET
def historico(request: HttpRequest) -> HttpResponse:
    """A lista de todas as entradas de auditoria, só de leitura."""
    return render(request, "administracao/historico.html", contexto_do_historico(request.GET))
