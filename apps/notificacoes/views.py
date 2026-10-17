"""Central de notificações da conta (E04-01). Cada conta vê e marca só as suas."""

from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.contas.models import Conta
from apps.contas.permissoes import exige_login
from apps.notificacoes.models import Notificacao
from apps.notificacoes.servicos import marcar_como_lida, marcar_todas_como_lidas

POR_PAGINA = 30


def _conta(request: HttpRequest) -> Conta:
    conta: Conta = request.user  # type: ignore[assignment]
    return conta


def _volta(request: HttpRequest) -> HttpResponse:
    pagina = request.POST.get("pagina") or request.GET.get("pagina") or ""
    destino = "/notificacoes/"
    if pagina.isascii() and pagina.isdigit():
        destino += f"?pagina={pagina}"
    return redirect(destino)


@exige_login
def central(request: HttpRequest) -> HttpResponse:
    conta = _conta(request)
    notificacoes = Notificacao.objects.filter(conta=conta).order_by("-criada_em", "-pk")
    pagina = Paginator(notificacoes, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "notificacoes/central.html",
        {"pagina": pagina, "ha_nao_lidas": notificacoes.filter(lida_em__isnull=True).exists()},
    )


@exige_login
@require_POST
def marcar_lida(request: HttpRequest, pk: int) -> HttpResponse:
    conta = _conta(request)
    if marcar_como_lida(conta, pk) is None:
        raise Http404
    if request.headers.get("HX-Request") == "true":
        notificacao = Notificacao.objects.get(pk=pk, conta=conta)
        return render(request, "notificacoes/_item.html", {"item": notificacao})
    return _volta(request)


@exige_login
@require_POST
def marcar_todas(request: HttpRequest) -> HttpResponse:
    marcar_todas_como_lidas(_conta(request))
    return redirect("/notificacoes/")
