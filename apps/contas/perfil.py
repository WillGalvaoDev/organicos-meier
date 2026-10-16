"""Dados opcionais do perfil: telefone, avatar e consentimento de WhatsApp (E02-09)."""

import re
import uuid
from io import BytesIO
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from apps.contas.models import Conta
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora

LIMITE_DO_AVATAR_EM_BYTES = 2 * 1024 * 1024
LIMITE_DO_AVATAR_EM_PIXELS = 4096
EXTENSAO_POR_FORMATO = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}

_CARACTERES_DO_TELEFONE = re.compile(r"[\d\s()\-+]+")


class TelefoneInvalido(Exception):
    """Telefone fora do formato brasileiro aceito. A mensagem não repete o número."""


class AvatarInvalido(Exception):
    """Arquivo que não é uma imagem JPEG, PNG ou WebP dentro dos limites."""


def normalizar_telefone(texto: str | None) -> str | None:
    """Telefone brasileiro em E.164 (`+55` + DDD + número de 8 ou 9 dígitos), ou `None` se vazio.

    Aceita dígitos e os separadores espaço, parênteses, hífen e `+` (este só no início, e só como
    `+55`). A entrada pode vir com `+55`, com `55` ou direto pelo DDD. O DDD não começa com 0.
    Números estrangeiros não são aceitos.
    """
    if texto is None or not texto.strip():
        return None
    limpo = texto.strip()
    if not _CARACTERES_DO_TELEFONE.fullmatch(limpo) or "+" in limpo[1:]:
        raise TelefoneInvalido("telefone inválido")
    digitos = re.sub(r"\D", "", limpo)
    if limpo.startswith("+"):
        if not digitos.startswith("55"):
            raise TelefoneInvalido("só números brasileiros são aceitos")
        digitos = digitos[2:]
    elif digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11) or digitos[0] == "0":
        raise TelefoneInvalido("informe DDD e número")
    return f"+55{digitos}"


def processar_avatar(arquivo: Any) -> "ContentFile[bytes]":
    """Valida e regrava o avatar sem metadados (EXIF/GPS), com nome UUID gerado no servidor.

    Aceita JPEG, PNG e WebP de até 2 MB e 4096 x 4096 px; verifica com Pillow, nunca pela
    extensão. Levanta `AvatarInvalido` para qualquer outra coisa.
    """
    if arquivo.size > LIMITE_DO_AVATAR_EM_BYTES:
        raise AvatarInvalido("o arquivo passa de 2 MB")
    try:
        arquivo.seek(0)
        with Image.open(arquivo) as imagem:
            formato = imagem.format
            if formato not in EXTENSAO_POR_FORMATO:
                raise AvatarInvalido("formato não aceito")
            largura, altura = imagem.size
            if largura > LIMITE_DO_AVATAR_EM_PIXELS or altura > LIMITE_DO_AVATAR_EM_PIXELS:
                raise AvatarInvalido("a imagem passa de 4096 x 4096 pixels")
            imagem.verify()
        arquivo.seek(0)
        with Image.open(arquivo) as imagem:
            imagem.load()
            corrigida = ImageOps.exif_transpose(imagem)  # respeita a orientação antes de limpar
            saida = BytesIO()
            opcoes: dict[str, Any] = {"quality": 90} if formato in ("JPEG", "WEBP") else {}
            corrigida.save(saida, format=formato, **opcoes)  # sem exif/pnginfo: metadados saem
    except AvatarInvalido:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise AvatarInvalido("o arquivo não é uma imagem válida") from None
    assert formato is not None  # noqa: S101 - garantido pela checagem acima
    return ContentFile(saida.getvalue(), name=f"{uuid.uuid4()}.{EXTENSAO_POR_FORMATO[formato]}")


def atualizar_perfil(
    conta: Conta,
    *,
    nome: str,
    telefone: str | None,
    whatsapp: bool,
    avatar_novo: "ContentFile[bytes] | None" = None,
    remover_avatar: bool = False,
) -> None:
    """Grava o perfil da própria conta, com o consentimento de WhatsApp e a auditoria.

    O consentimento vale para um número: remover ou trocar o telefone o revoga, e é preciso
    aceitar de novo. Marcar sem telefone é recusado pelo formulário e pelo `CHECK` do banco.
    """
    consentia = conta.whatsapp_consentido_em is not None
    telefone_anterior = conta.telefone
    novo_consentimento = whatsapp
    if telefone is None or (consentia and telefone != telefone_anterior):
        novo_consentimento = False
    avatar_antigo = conta.avatar.name if conta.avatar else None
    avatar_gravado: str | None = None
    try:
        with transaction.atomic():
            conta.nome = nome
            conta.telefone = telefone
            if novo_consentimento and not consentia:
                conta.whatsapp_consentido_em = agora()
                registrar_auditoria(conta, "perfil.whatsapp_consentir", conta, {"conta": conta.pk})
            elif not novo_consentimento and consentia:
                conta.whatsapp_consentido_em = None
                registrar_auditoria(conta, "perfil.whatsapp_revogar", conta, {"conta": conta.pk})
            if avatar_novo is not None:
                conta.avatar.save(avatar_novo.name or "avatar", avatar_novo, save=False)
                avatar_gravado = conta.avatar.name
            elif remover_avatar and avatar_antigo:
                conta.avatar = None
            conta.save()
            if avatar_antigo and conta.avatar.name != avatar_antigo:
                armazenamento = conta._meta.get_field("avatar").storage
                transaction.on_commit(lambda: armazenamento.delete(avatar_antigo))
    except Exception:
        if avatar_gravado:  # a gravação falhou: não deixa o arquivo novo órfão
            conta._meta.get_field("avatar").storage.delete(avatar_gravado)
        raise
