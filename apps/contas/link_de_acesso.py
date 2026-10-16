"""Link de acesso por e-mail (E02-06).

Uso único, validade de 15 minutos, token só como hash. O pedido responde igual para qualquer
e-mail; só quem tem conta e passa por `verificar_acesso` recebe o link.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.template.loader import render_to_string

from apps.contas.acesso import AcessoRecusado, Metodo, verificar_acesso
from apps.contas.emails import normalizar_email
from apps.contas.models import Conta, LinkDeAcesso
from apps.nucleo.tempo import agora, prazo_encerrado

logger = logging.getLogger(__name__)

VALIDADE_EM_MINUTOS = 15
LIMITE_DE_LINKS_NA_JANELA = 3


class LinkInvalido(Exception):
    """Link inexistente, usado, expirado ou cuja conta não pode mais entrar."""


def _enviar_email(email: str, link_id: int, token: str, origem: str) -> None:
    contexto = {"link": f"{origem}/entrar/link/{token}/", "minutos": VALIDADE_EM_MINUTOS}
    assunto = " ".join(render_to_string("contas/link_email_assunto.txt", contexto).split())
    corpo = render_to_string("contas/link_email_corpo.txt", contexto)
    try:
        EmailMessage(assunto, corpo, to=[email]).send(fail_silently=False)
    except Exception as erro:
        logger.error("falha no envio do link de acesso %s (%s)", link_id, type(erro).__name__)


def pedir_link(email: str, *, origem: str | None = None) -> None:
    """Cria e envia um link de acesso, quando permitido. Nunca revela o resultado.

    Levanta `EmailInvalido` apenas para texto que não é e-mail (erro de formulário).
    """
    normalizado = normalizar_email(email)  # EmailInvalido: o único caso com resposta diferente
    base = (origem or settings.ORIGEM_PUBLICA).rstrip("/")
    with transaction.atomic():
        # Trava a conta para que pedidos simultâneos não furem o limite.
        conta = Conta.objects.select_for_update().filter(email_normalizado=normalizado).first()
        try:
            verificar_acesso(conta, normalizado, Metodo.LINK)
        except AcessoRecusado:
            return  # sem conta, banido, removido ou administrador: nada é criado nem enviado
        if conta is None:  # inalcançável: verificar_acesso já recusa "sem_conta"
            return
        agora_ = agora()
        recentes = LinkDeAcesso.objects.filter(
            conta=conta, criado_em__gt=agora_ - timedelta(minutes=VALIDADE_EM_MINUTOS)
        ).count()
        if recentes >= LIMITE_DE_LINKS_NA_JANELA:
            return
        token = secrets.token_urlsafe(32)
        link = LinkDeAcesso.objects.create(
            conta=conta,
            token_hash=LinkDeAcesso.hash_do_token(token),
            criado_em=agora_,
            expira_em=agora_ + timedelta(minutes=VALIDADE_EM_MINUTOS),
        )
        destino = conta.email_normalizado
        transaction.on_commit(lambda: _enviar_email(destino, link.pk, token, base))


def validar_link(token: str) -> LinkDeAcesso:
    """Confere o link sem consumi-lo (página de confirmação)."""
    link = (
        LinkDeAcesso.objects.select_related("conta")
        .filter(token_hash=LinkDeAcesso.hash_do_token(token))
        .first()
    )
    return _conferir(link)


def _conferir(link: LinkDeAcesso | None) -> LinkDeAcesso:
    if link is None or link.usado_em is not None or prazo_encerrado(agora(), link.expira_em):
        raise LinkInvalido
    try:
        verificar_acesso(link.conta, link.conta.email_normalizado, Metodo.LINK)
    except AcessoRecusado:
        raise LinkInvalido from None
    return link


def usar_link(token: str) -> Conta:
    """Consome o link (uso único) e devolve a conta. A autenticação na sessão é da view."""
    with transaction.atomic():
        link = _conferir(
            LinkDeAcesso.objects.select_for_update(of=("self",))
            .select_related("conta")
            .filter(token_hash=LinkDeAcesso.hash_do_token(token))
            .first()
        )
        link.usado_em = agora()
        link.save(update_fields=["usado_em"])
        return link.conta
