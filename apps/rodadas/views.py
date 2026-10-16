from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.contas.administracao import somente_administrador
from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
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
