"""Emissão de convites (E02-04).

Só o administrador emite. O token nasce aqui, vai apenas para o e-mail e é gravado somente como
hash. O e-mail sai em `transaction.on_commit`, depois que convite e auditoria foram gravados.
"""

import logging
import secrets

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.db import transaction
from django.template.loader import render_to_string

from apps.contas.emails import email_banido, normalizar_email
from apps.contas.models import Conta, Convite, EmailEmUso, Papel
from apps.fornecedores.models import Fornecedor
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao, somar_horas

logger = logging.getLogger(__name__)

VALIDADE_EM_HORAS = 24


class ConviteInvalido(Exception):
    """Combinação inválida de papel e fornecedor."""


class EmailBanidoErro(Exception):
    """O e-mail está banido: não se cadastra, nem com convite novo."""


def _enviar_email(convite: Convite, token: str, origem: str, nome_fornecedor: str | None) -> None:
    """Envia o e-mail do convite. Falha não desfaz o convite e não registra e-mail nem token."""
    contexto = {
        "link": f"{origem}/convite/{token}/",
        "papel": convite.papel,
        "nome_fornecedor": nome_fornecedor,
        "expira_em": no_fuso_da_operacao(convite.expira_em).strftime("%d/%m/%Y às %H:%M"),
    }
    assunto = " ".join(render_to_string("convites/email_assunto.txt", contexto).split())
    corpo = render_to_string("convites/email_corpo.txt", contexto)
    try:
        EmailMessage(assunto, corpo, to=[convite.email_normalizado]).send(fail_silently=False)
    except Exception as erro:
        convite.email_enviado = False
        logger.error("falha no envio do e-mail do convite %s (%s)", convite.pk, type(erro).__name__)
    else:
        convite.email_enviado = True


def emitir_convite(
    autor: Conta,
    email: str,
    papel: str,
    fornecedor: Fornecedor | None = None,
    *,
    origem: str | None = None,
) -> Convite:
    """Emite um convite de uso único com validade de 24 horas.

    `origem` (esquema + domínio) vem da requisição; sem requisição, vale `ORIGEM_PUBLICA`.
    Levanta `PermissionDenied`, `EmailInvalido`, `EmailEmUso`, `EmailBanidoErro` ou
    `ConviteInvalido`, sem gravar nada.
    """
    if getattr(autor, "papel", None) != Papel.ADMINISTRADOR:
        raise PermissionDenied
    normalizado = normalizar_email(email)
    if papel not in (Papel.COMPRADOR, Papel.FORNECEDOR):
        raise ConviteInvalido("o papel do convite deve ser comprador ou fornecedor")
    if (papel == Papel.FORNECEDOR) != (fornecedor is not None):
        raise ConviteInvalido("convite de fornecedor exige fornecedor; o de comprador não aceita")
    if Conta.objects.filter(email_normalizado=normalizado).exists():
        raise EmailEmUso("já existe uma conta com este e-mail")
    if email_banido(normalizado):
        raise EmailBanidoErro("este e-mail está banido")

    token = secrets.token_urlsafe(32)
    emitido_em = agora()
    base = (origem or settings.ORIGEM_PUBLICA).rstrip("/")
    with transaction.atomic():
        convite = Convite.objects.create(
            email_normalizado=normalizado,
            papel=papel,
            fornecedor=fornecedor,
            token_hash=Convite.hash_do_token(token),
            emitido_por=autor,
            emitido_em=emitido_em,
            expira_em=somar_horas(emitido_em, VALIDADE_EM_HORAS),
        )
        registrar_auditoria(
            autor,
            "convite.emitir",
            convite,
            {
                "convite": convite.pk,
                "papel": papel,
                "fornecedor": fornecedor.pk if fornecedor is not None else None,
            },
        )
        nome = fornecedor.nome if fornecedor is not None else None
        transaction.on_commit(lambda: _enviar_email(convite, token, base, nome))
    return convite
