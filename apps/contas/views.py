from allauth.account.internal.flows.login import perform_login
from allauth.account.models import Login
from allauth.mfa.adapter import get_adapter as get_adapter_mfa
from allauth.mfa.models import Authenticator
from allauth.mfa.webauthn.views import remove_webauthn
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.contas.administracao import somente_administrador
from apps.contas.convites import (
    ConviteInvalido,
    EmailBanidoErro,
    MetodoCadastro,
    consumir_convite,
    emitir_convite,
    validar_convite,
)
from apps.contas.emails import EmailInvalido
from apps.contas.forms import FormularioCadastroPorConvite
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
            form.add_error(None, erro.mensagem)
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


def aceitar_convite(request: HttpRequest, token: str) -> HttpResponse:
    """Página (GET) e cadastro (POST) por convite. O GET nunca consome o convite."""
    if request.user.is_authenticated:  # contas independentes: não mistura sessões (§2)
        return render(request, "convites/sair_antes.html")
    try:
        convite = validar_convite(token)
    except ConviteInvalido:
        return render(request, "convites/invalido.html", status=410)
    form = FormularioCadastroPorConvite(
        request.POST if request.method == "POST" else None, convite=convite
    )
    if request.method == "POST" and form.is_valid():
        try:
            conta = consumir_convite(
                token,
                form.cleaned_data["nome"],
                form.cleaned_data["senha"],
                metodo=MetodoCadastro.SENHA,
            )
        except ConviteInvalido:
            return render(request, "convites/invalido.html", status=410)
        except ValidationError as erro:
            for campo, mensagens in erro.message_dict.items():
                for mensagem in mensagens:
                    form.add_error(campo if campo in form.fields else None, mensagem)
        else:
            resposta: HttpResponse = perform_login(
                request, Login(user=conta, email=conta.email_normalizado)
            )
            return resposta
    return render(request, "convites/cadastro.html", {"form": form, "convite": convite})
