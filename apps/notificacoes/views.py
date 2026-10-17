"""Central de notificações da conta (E04-01). Cada conta vê e marca só as suas."""

import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import CharField, Count, F, Func, Value
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.contas.administracao import somente_administrador
from apps.contas.models import Conta
from apps.contas.permissoes import exige_comprador, exige_login
from apps.notificacoes.comunicados import compradores_do_comunicado, publicar_comunicado
from apps.notificacoes.consultas import (
    ROTULOS_CANAL,
    ROTULOS_SITUACAO,
    ROTULOS_TIPO,
    contar_falhas,
    envios_para_administracao,
    filtros_validos,
)
from apps.notificacoes.eventos import Evento
from apps.notificacoes.forms import FormularioComunicado
from apps.notificacoes.models import TIPOS_DE_ACESSO, Comunicado, Envio, Notificacao
from apps.notificacoes.servicos import marcar_como_lida, marcar_todas_como_lidas

POR_PAGINA = 30
POR_PAGINA_DOS_ENVIOS = 50
ROTULOS_DE_CANAL = {"email": "e-mail", "whatsapp": "WhatsApp"}


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


def _resumo_dos_envios(ids: list[int]) -> dict[int, list[str]]:
    """Contagem dos envios por canal e situação de cada comunicado, numa única consulta."""
    comunicado_id = Func(
        F("chave"), Value(r"^comunicado:(\d+):"), function="substring", output_field=CharField()
    )
    linhas = (
        Envio.objects.filter(tipo=Evento.COMUNICADO.value)
        .annotate(comunicado_id=comunicado_id)
        .filter(comunicado_id__in=[str(i) for i in ids])
        .values("comunicado_id", "canal", "situacao")
        .annotate(total=Count("id"))
    )
    contagens: dict[int, dict[str, dict[str, int]]] = {}
    for linha in linhas:
        por_canal = contagens.setdefault(int(linha["comunicado_id"]), {})
        por_canal.setdefault(linha["canal"], {})[linha["situacao"]] = linha["total"]
    return {
        i: [
            f"{ROTULOS_DE_CANAL[canal]}: " + ", ".join(_frases(contagens[i][canal]))
            for canal in ROTULOS_DE_CANAL
            if canal in contagens.get(i, {})
        ]
        for i in ids
    }


def _frases(por_situacao: dict[str, int]) -> list[str]:
    modelos = {
        "enviado": ("{} aceito", "{} aceitos"),
        "falhou": ("{} com falha", "{} com falha"),
        "pendente": ("{} pendente", "{} pendentes"),
        "cancelado": ("{} cancelado", "{} cancelados"),
    }
    return [
        modelos[situacao][0 if por_situacao[situacao] == 1 else 1].format(por_situacao[situacao])
        for situacao in modelos
        if situacao in por_situacao
    ]


def _compradores(n: int) -> str:
    return f"{n} comprador" + ("" if n == 1 else "es")


@somente_administrador
def comunicados_administracao(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = FormularioComunicado(request.POST)
        if form.is_valid():
            try:
                comunicado, novo = publicar_comunicado(
                    _conta(request),
                    titulo=form.cleaned_data["titulo"],
                    mensagem=form.cleaned_data["mensagem"],
                    token=form.cleaned_data["token"],
                )
            except ValidationError as erro:
                for campo, mensagens in erro.message_dict.items():
                    for mensagem in mensagens:
                        form.add_error(campo, mensagem)
            else:
                if novo:
                    messages.success(
                        request,
                        f"Comunicado publicado para {_compradores(comunicado.destinatarios)}.",
                    )
                else:
                    messages.info(request, "Este comunicado já tinha sido publicado.")
                return redirect("comunicados_administracao")
    else:
        form = FormularioComunicado(initial={"token": uuid.uuid4()})
    comunicados_publicados = Comunicado.objects.select_related("autor").order_by(
        "-publicado_em", "-pk"
    )
    pagina = Paginator(comunicados_publicados, POR_PAGINA).get_page(request.GET.get("pagina"))
    resumos = _resumo_dos_envios([c.pk for c in pagina.object_list])
    historico = [(c, resumos[c.pk]) for c in pagina.object_list]
    return render(
        request,
        "notificacoes/comunicados_administracao.html",
        {
            "form": form,
            "pagina": pagina,
            "historico": historico,
            "compradores": _compradores(compradores_do_comunicado().count()),
        },
    )


@exige_comprador
def comunicados(request: HttpRequest) -> HttpResponse:
    publicados = Comunicado.objects.order_by("-publicado_em", "-pk")
    pagina = Paginator(publicados, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(request, "notificacoes/comunicados.html", {"pagina": pagina})


@somente_administrador
@require_GET
def envios_lista(request: HttpRequest) -> HttpResponse:
    filtros = filtros_validos(request.GET.dict())
    pagina = Paginator(envios_para_administracao(filtros), POR_PAGINA_DOS_ENVIOS).get_page(
        request.GET.get("pagina")
    )
    return render(
        request,
        "notificacoes/envios_lista.html",
        {
            "pagina": pagina,
            "filtros": filtros,
            "tem_filtro": bool(filtros),
            "situacoes": ROTULOS_SITUACAO,
            "canais": ROTULOS_CANAL,
            "tipos": ROTULOS_TIPO,
            "rotulo_situacao": ROTULOS_SITUACAO,
            "rotulo_canal": ROTULOS_CANAL,
            "rotulo_tipo": ROTULOS_TIPO,
            "falhas": contar_falhas(),
        },
    )


@somente_administrador
@require_GET
def envio_detalhe(request: HttpRequest, pk: int) -> HttpResponse:
    envio = get_object_or_404(Envio.objects.select_related("conta", "notificacao"), pk=pk)
    return render(
        request,
        "notificacoes/envio_detalhe.html",
        {
            "envio": envio,
            "tentativas": envio.tentativas_feitas.order_by("numero"),
            "de_acesso": envio.tipo in TIPOS_DE_ACESSO,
            "rotulo_situacao": ROTULOS_SITUACAO,
            "rotulo_canal": ROTULOS_CANAL,
            "rotulo_tipo": ROTULOS_TIPO,
        },
    )
