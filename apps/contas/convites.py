"""Emissão de convites (E02-04).

Só o administrador emite. O token nasce aqui, vai apenas para o e-mail e é gravado somente como
hash. O e-mail sai em `transaction.on_commit`, depois que convite e auditoria foram gravados.
"""

import logging
import secrets
from enum import StrEnum

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.template.loader import render_to_string

from apps.contas.emails import email_banido, normalizar_email
from apps.contas.models import Conta, Convite, EmailEmUso, Papel, Situacao
from apps.fornecedores.models import Fornecedor
from apps.notificacoes.acesso import enviar_email_de_acesso
from apps.notificacoes.models import CONVITE, SituacaoEnvio
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao, prazo_encerrado, somar_horas

logger = logging.getLogger(__name__)

VALIDADE_EM_HORAS = 24


class ConviteInvalido(Exception):
    """Convite que não pode ser emitido ou usado. `codigo` é interno (testes e logs).

    Emissão: `papel_invalido`, `fornecedor_inconsistente`. Uso (cadastro): `inexistente`,
    `consumido`, `expirado`, `banido`, `email_em_uso`.
    """

    def __init__(self, codigo: str, mensagem: str | None = None) -> None:
        super().__init__(mensagem or codigo)
        self.codigo = codigo
        self.mensagem = mensagem or codigo


class MetodoCadastro(StrEnum):
    SENHA = "senha"
    GOOGLE = "google"


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
    envio = enviar_email_de_acesso(
        CONVITE,
        destino=convite.email_normalizado,
        assunto=assunto,
        corpo=corpo,
        referencia=convite.pk,
    )
    convite.email_enviado = envio.situacao == SituacaoEnvio.ENVIADO


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
        raise ConviteInvalido(
            "papel_invalido", "o papel do convite deve ser comprador ou fornecedor"
        )
    if (papel == Papel.FORNECEDOR) != (fornecedor is not None):
        raise ConviteInvalido(
            "fornecedor_inconsistente",
            "convite de fornecedor exige fornecedor; o de comprador não aceita",
        )
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


def _conferir(convite: Convite | None) -> Convite:
    """Regras de uso do convite, com o relógio do servidor. Levanta `ConviteInvalido(codigo)`."""
    if convite is None:
        raise ConviteInvalido("inexistente")
    if convite.consumido_em is not None:
        raise ConviteInvalido("consumido")
    if prazo_encerrado(agora(), convite.expira_em):
        raise ConviteInvalido("expirado")
    if email_banido(convite.email_normalizado):
        raise ConviteInvalido("banido")
    if Conta.objects.filter(email_normalizado=convite.email_normalizado).exists():
        raise ConviteInvalido("email_em_uso")
    return convite


def validar_convite(token: str) -> Convite:
    """Valida o convite sem consumi-lo (página do cadastro)."""
    convite = (
        Convite.objects.select_related("fornecedor")
        .filter(token_hash=Convite.hash_do_token(token))
        .first()
    )
    return _conferir(convite)


def consumir_convite(
    token: str, nome: str, senha: str | None = None, *, metodo: MetodoCadastro
) -> Conta:
    """Cria a conta do convite e o consome, numa única transação.

    Papel, e-mail e fornecedor vêm do convite. O convite é travado (`select_for_update`) e todas
    as regras são conferidas de novo, de modo que duas tentativas simultâneas resultam em uma
    conta e um consumo. Levanta `ConviteInvalido` (com `codigo`) ou `ValidationError` (nome ou
    senha); em qualquer erro nada é gravado.
    """
    with transaction.atomic():
        convite = _conferir(
            Convite.objects.select_for_update(of=("self",))
            .select_related("fornecedor")
            .filter(token_hash=Convite.hash_do_token(token))
            .first()
        )
        nome = (nome or "").strip()
        if not nome or len(nome) > 150:
            raise ValidationError({"nome": "Informe um nome de 1 a 150 caracteres."})
        conta = Conta(
            email_normalizado=convite.email_normalizado,
            nome=nome,
            papel=convite.papel,
            fornecedor=convite.fornecedor,
            situacao=Situacao.ATIVA,
        )
        if metodo == MetodoCadastro.SENHA:
            if not senha:
                raise ValidationError({"senha": "Informe uma senha."})
            validate_password(senha, user=conta)
            conta.set_password(senha)
        try:
            conta.save()
        except EmailEmUso:  # corrida com outro convite do mesmo e-mail: vence o banco
            raise ConviteInvalido("email_em_uso") from None
        EmailAddress.objects.create(
            user=conta, email=conta.email_normalizado, verified=True, primary=True
        )
        convite.consumido_em = agora()
        convite.conta_criada = conta
        convite.save(update_fields=["consumido_em", "conta_criada"])
        registrar_auditoria(
            conta,
            "convite.consumir",
            convite,
            {"convite": convite.pk, "conta": conta.pk, "papel": convite.papel},
        )
    return conta
