import mimetypes

from allauth.account.internal.flows.login import perform_login, record_authentication
from allauth.account.models import Login
from allauth.mfa.adapter import get_adapter as get_adapter_mfa
from allauth.mfa.models import Authenticator
from allauth.mfa.webauthn.views import remove_webauthn
from allauth.socialaccount.internal.flows.signup import get_pending_signup
from allauth.socialaccount.providers.google.views import oauth2_login
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.contas import google as apoio_google
from apps.contas.administracao import somente_administrador, tem_prova_de_passkey
from apps.contas.convites import (
    ConviteInvalido,
    EmailBanidoErro,
    MetodoCadastro,
    consumir_convite,
    emitir_convite,
    validar_convite,
)
from apps.contas.emails import EmailInvalido
from apps.contas.forms import (
    FormularioCadastroPorConvite,
    FormularioConclusaoGoogle,
    FormularioPerfil,
)
from apps.contas.formularios import FormularioConvite, FormularioPedidoDeLink
from apps.contas.google import (
    CHAVE_CONVITE_PENDENTE,
    encerrar_cadastro_pendente,
    recusar_login_google,
)
from apps.contas.link_de_acesso import LinkInvalido, pedir_link, usar_link, validar_link
from apps.contas.models import Conta, Convite, EmailEmUso, Papel, Situacao
from apps.contas.moderacao import ModeracaoInvalida, reativar, remover, suspender
from apps.contas.perfil import atualizar_perfil
from apps.contas.permissoes import exige_login, publica
from apps.notificacoes.consultas import contar_falhas


@exige_login
def inicio(request: HttpRequest) -> HttpResponse:
    """Página inicial autenticada: nome e papel, até as telas de cada papel existirem."""
    return render(request, "inicio.html", {"conta": request.user})


@somente_administrador
def painel_administracao(request: HttpRequest) -> HttpResponse:
    """Início da área administrativa, sem conteúdo de negócio (E02-03)."""
    return render(
        request,
        "administracao/painel.html",
        {"conta": request.user, "envios_com_falha": contar_falhas()},
    )


def _ha_outra_passkey(conta_id: int, excluindo: int) -> bool:
    """Decisão sobre o estado travado: a conta tem outra passkey além da que será removida?"""
    outras = Authenticator.objects.filter(
        user_id=conta_id, type=Authenticator.Type.WEBAUTHN
    ).exclude(pk=excluindo)
    return bool(outras.exists())


@exige_login
def remover_passkey(request: HttpRequest, pk: int) -> HttpResponse:
    """Remoção de passkey do allauth, recusada quando seria a última.

    O allauth só consulta `can_delete_authenticator` no TOTP, então a regra é aplicada aqui. A
    verificação e a exclusão são serializadas por conta: a linha da conta da sessão é travada
    (`select_for_update`) e a decisão que vale é tomada sob a trava, por `_ha_outra_passkey`.
    Travar só a linha do `Authenticator` não bastaria: duas remoções de passkeys diferentes
    travariam linhas diferentes.
    """
    if request.method != "POST" or not request.user.is_authenticated:
        resposta: HttpResponse = remove_webauthn(request, pk=pk)
        return resposta
    autenticador = Authenticator.objects.filter(
        pk=pk, user=request.user, type=Authenticator.Type.WEBAUTHN
    ).first()
    # Resposta rápida, sem trava; não é a decisão final.
    if autenticador is not None and not get_adapter_mfa().can_delete_authenticator(autenticador):
        messages.error(request, "A última passkey não pode ser removida.")
        return redirect("mfa_list_webauthn")
    with transaction.atomic():
        conta_id = request.user.pk
        Conta.objects.select_for_update().get(pk=conta_id)
        if autenticador is not None and not _ha_outra_passkey(conta_id, pk):
            messages.error(request, "A última passkey não pode ser removida.")
            return redirect("mfa_list_webauthn")
        resposta = remove_webauthn(request, pk=pk)  # dentro da mesma transação
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


@publica
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
    return render(
        request, "convites/cadastro.html", {"form": form, "convite": convite, "token": token}
    )


@publica
def pedir_link_de_acesso(request: HttpRequest) -> HttpResponse:
    """Pedido do link de acesso. A resposta é a mesma para qualquer e-mail válido."""
    form = FormularioPedidoDeLink(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        pedir_link(form.cleaned_data["email"], origem=request.build_absolute_uri("/"))
        return render(request, "contas/link_pedido_enviado.html")
    return render(request, "contas/link_pedido.html", {"form": form})


@publica
def usar_link_de_acesso(request: HttpRequest, token: str) -> HttpResponse:
    """GET confirma (não consome); POST consome o link e autentica a conta."""
    if request.method == "POST":
        try:
            conta = usar_link(token)
        except LinkInvalido:
            return render(request, "contas/link_invalido.html", status=410)
        record_authentication(request, conta, "link")
        resposta: HttpResponse = perform_login(
            request, Login(user=conta, email=conta.email_normalizado)
        )
        return resposta
    try:
        validar_link(token)
    except LinkInvalido:
        return render(request, "contas/link_invalido.html", status=410)
    return render(request, "contas/link_confirmar.html")


@publica
@require_POST
def cadastrar_com_google(request: HttpRequest, token: str) -> HttpResponse:
    """Guarda o convite na sessão e inicia o login do Google (sem consumir o convite)."""
    if request.user.is_authenticated:
        return render(request, "convites/sair_antes.html")
    try:
        validar_convite(token)
    except ConviteInvalido:
        return render(request, "convites/invalido.html", status=410)
    request.session[CHAVE_CONVITE_PENDENTE] = token
    resposta: HttpResponse = oauth2_login(request)
    return resposta


@publica
def concluir_cadastro_google(request: HttpRequest) -> HttpResponse:
    """Último passo do cadastro com Google: confirma o nome e consome o convite."""
    pendente = get_pending_signup(request)
    token = request.session.get(CHAVE_CONVITE_PENDENTE)
    if pendente is None or not token:
        return recusar_login_google(request)
    dados = pendente.account.extra_data or {}
    email = apoio_google.email_verificado_do_google(dados)
    if email is None:
        return recusar_login_google(request)
    try:
        convite = validar_convite(token)
    except ConviteInvalido:
        return recusar_login_google(request)
    if convite.email_normalizado != email:
        return recusar_login_google(request)
    form = FormularioConclusaoGoogle(
        request.POST if request.method == "POST" else None,
        initial={"nome": str(dados.get("name", ""))[:150]},
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                conta = consumir_convite(
                    token, form.cleaned_data["nome"], metodo=MetodoCadastro.GOOGLE
                )
                pendente.connect(request, conta)
        except ConviteInvalido:
            return recusar_login_google(request)
        except ValidationError as erro:
            for mensagens in erro.message_dict.values():
                for mensagem in mensagens:
                    form.add_error("nome", mensagem)
        else:
            encerrar_cadastro_pendente(request)
            record_authentication(
                request,
                conta,
                "socialaccount",
                provider=pendente.account.provider,
                uid=pendente.account.uid,
            )
            resultado: HttpResponse = perform_login(
                request, Login(user=conta, email=conta.email_normalizado)
            )
            return resultado
    return render(request, "convites/google_concluir.html", {"form": form, "convite": convite})


@publica
def google_recusado(request: HttpRequest) -> HttpResponse:
    """Erro ou cancelamento no Google: a mesma recusa única."""
    return recusar_login_google(request)


def _acoes_permitidas(conta: Conta) -> list[str]:
    """Botões da tela, conforme a tabela de alvos da moderação."""
    if conta.situacao == Situacao.REMOVIDA:
        return []
    acoes: list[str] = []
    if conta.papel == Papel.COMPRADOR:
        acoes.append("suspender" if conta.situacao == Situacao.ATIVA else "reativar")
    acoes.append("remover")
    return acoes


@somente_administrador
def usuarios_administracao(request: HttpRequest) -> HttpResponse:
    """Lista de compradores e fornecedores, com as ações permitidas para cada um."""
    contas = (
        Conta.objects.exclude(papel=Papel.ADMINISTRADOR)
        .select_related("fornecedor")
        .order_by("nome", "pk")
    )
    itens = [{"conta": conta, "acoes": _acoes_permitidas(conta)} for conta in contas]
    return render(request, "usuarios/administracao.html", {"itens": itens})


@somente_administrador
@require_POST
def acao_de_moderacao(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    """Suspende ou reativa um comprador. A remoção tem página de confirmação própria."""
    servicos = {
        "suspender": (suspender, "Conta suspensa."),
        "reativar": (reativar, "Conta reativada."),
    }
    if acao not in servicos:
        raise Http404
    conta = get_object_or_404(Conta, pk=pk)
    servico, sucesso = servicos[acao]
    try:
        servico(request.user, conta)  # type: ignore[arg-type]
    except ModeracaoInvalida:
        messages.error(request, "Esta ação não é permitida para esta conta.")
    else:
        messages.success(request, sucesso)
    return redirect("usuarios_administracao")


@somente_administrador
def confirmar_remocao(request: HttpRequest, pk: int) -> HttpResponse:
    """GET pede a confirmação; POST remove a conta (definitivo) e bane o e-mail."""
    conta = get_object_or_404(Conta, pk=pk)
    if request.method == "POST":
        try:
            remover(request.user, conta)  # type: ignore[arg-type]
        except ModeracaoInvalida:
            messages.error(request, "Esta ação não é permitida para esta conta.")
        else:
            messages.success(request, "Conta removida e e-mail banido.")
        return redirect("usuarios_administracao")
    if "remover" not in _acoes_permitidas(conta) or conta.papel == Papel.ADMINISTRADOR:
        messages.error(request, "Esta ação não é permitida para esta conta.")
        return redirect("usuarios_administracao")
    return render(request, "usuarios/confirmar_remocao.html", {"conta": conta})


@exige_login
def perfil(request: HttpRequest) -> HttpResponse:
    """Perfil da própria conta da sessão (não há parâmetro de identificação de conta)."""
    conta = Conta.objects.get(pk=request.user.pk)  # type: ignore[misc]
    form = FormularioPerfil(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        conta=conta,
        initial={
            "nome": conta.nome,
            "telefone": conta.telefone or "",
            "whatsapp": conta.whatsapp_consentido_em is not None,
        },
    )
    if request.method == "POST" and form.is_valid():
        atualizar_perfil(
            conta,
            nome=form.cleaned_data["nome"],
            telefone=form.telefone_normalizado,
            whatsapp=form.cleaned_data["whatsapp"],
            avatar_novo=form.avatar_processado,
            remover_avatar=form.cleaned_data["remover_avatar"],
        )
        messages.success(request, "Perfil atualizado.")
        return redirect("perfil")
    return render(request, "contas/perfil.html", {"form": form, "conta": conta})


@exige_login
def avatar(request: HttpRequest, pk: int) -> HttpResponseBase:
    """Serve o avatar à própria conta e ao administrador (com passkey); os demais veem 404."""
    usuario = request.user
    permitido = usuario.pk == pk or (
        getattr(usuario, "papel", None) == Papel.ADMINISTRADOR and tem_prova_de_passkey(request)
    )
    conta = Conta.objects.filter(pk=pk).first()
    if not permitido or conta is None or not conta.avatar:
        raise Http404
    try:
        arquivo = conta.avatar.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    tipo = mimetypes.guess_type(conta.avatar.name)[0] or "application/octet-stream"
    resposta = FileResponse(arquivo, content_type=tipo)
    resposta["Cache-Control"] = "private, no-store"
    return resposta
