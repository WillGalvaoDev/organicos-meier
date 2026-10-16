from allauth.mfa.adapter import get_adapter as get_adapter_mfa
from allauth.mfa.models import Authenticator
from allauth.mfa.webauthn.views import remove_webauthn
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.contas.administracao import somente_administrador
from apps.contas.convites import ConviteInvalido, EmailBanidoErro, emitir_convite
from apps.contas.emails import EmailInvalido
from apps.contas.formularios import FormularioConvite
from apps.contas.models import Convite, EmailEmUso


@login_required
def inicio(request: HttpRequest) -> HttpResponse:
    """Página inicial autenticada: nome e papel, até as telas de cada papel existirem."""
    return render(request, "inicio.html", {"conta": request.user})


@somente_administrador
def painel_administracao(request: HttpRequest) -> HttpResponse:
    """Início da área administrativa, sem conteúdo de negócio (E02-03)."""
    return render(request, "administracao/painel.html", {"conta": request.user})


def remover_passkey(request: HttpRequest, pk: int) -> HttpResponse:
    """Remoção de passkey do allauth, recusada quando seria a última (o allauth só consulta
    `can_delete_authenticator` no TOTP, então a regra é aplicada aqui)."""
    if request.method == "POST" and request.user.is_authenticated:
        autenticador = Authenticator.objects.filter(
            pk=pk, user=request.user, type=Authenticator.Type.WEBAUTHN
        ).first()
        if autenticador is not None and not get_adapter_mfa().can_delete_authenticator(
            autenticador
        ):
            messages.error(request, "A última passkey não pode ser removida.")
            return redirect("mfa_list_webauthn")
    resposta: HttpResponse = remove_webauthn(request, pk=pk)
    return resposta


@somente_administrador
def convites_administracao(request: HttpRequest) -> HttpResponse:
    """Emissão e consulta de convites (GET e POST)."""
    form = FormularioConvite(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            convite = emitir_convite(
                request.user,  # type: ignore[arg-type]
                form.cleaned_data["email"],
                form.cleaned_data["papel"],
                form.cleaned_data["fornecedor"],
                origem=request.build_absolute_uri("/"),
            )
        except EmailInvalido:
            form.add_error("email", "Informe um e-mail válido.")
        except EmailEmUso:
            form.add_error("email", "Este e-mail já está em uso por uma conta.")
        except EmailBanidoErro:
            form.add_error("email", "Este e-mail está banido e não pode receber convite.")
        except ConviteInvalido as erro:
            form.add_error(None, str(erro))
        else:
            if convite.email_enviado is False:
                messages.error(
                    request,
                    "Convite criado, mas o e-mail não pôde ser enviado. Emita um novo convite.",
                )
            else:
                messages.success(request, "Convite emitido.")
            return redirect("convites_administracao")
    convites = Convite.objects.select_related("fornecedor", "conta_criada").order_by(
        "-emitido_em", "-pk"
    )
    return render(request, "convites/administracao.html", {"form": form, "convites": convites})
