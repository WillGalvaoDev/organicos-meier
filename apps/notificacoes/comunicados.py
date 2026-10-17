"""Publicação de comunicados (E04-06).

Um comunicado vai a todos os compradores `ativa` ou `suspensa` no momento da publicação, pelos
canais do evento `comunicado`. A conta removida não recebe (não entra mais, e o e-mail é banido).
O token do formulário impede publicar duas vezes o mesmo pedido: a `UNIQUE` resolve a corrida.
"""

import uuid
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from apps.contas.models import Conta, Papel, Situacao
from apps.notificacoes.emissao import emitir_evento_para_varios
from apps.notificacoes.eventos import Evento
from apps.notificacoes.models import Comunicado
from apps.notificacoes.servicos import MAIOR_CORPO, MAIOR_TITULO
from apps.nucleo.auditoria import registrar_auditoria

LINK_DOS_COMUNICADOS = "/comunicados/"


def compradores_do_comunicado() -> QuerySet[Conta]:
    return Conta.objects.filter(
        papel=Papel.COMPRADOR, situacao__in=[Situacao.ATIVA, Situacao.SUSPENSA]
    ).order_by("pk")


def _texto(valor: Any, maior: int) -> str | None:
    if not isinstance(valor, str):
        return None
    limpo = valor.strip()
    return limpo if 1 <= len(limpo) <= maior else None


def publicar_comunicado(
    autor: Conta, *, titulo: str, mensagem: str, token: uuid.UUID
) -> tuple[Comunicado, bool]:
    """Publica e distribui; token repetido devolve `(existente, False)` sem publicar de novo."""
    if autor.papel != Papel.ADMINISTRADOR:
        raise PermissionDenied
    titulo_limpo = _texto(titulo, MAIOR_TITULO)
    mensagem_limpa = _texto(mensagem, MAIOR_CORPO)
    erros: dict[str, list[str]] = {}
    if titulo_limpo is None:
        erros["titulo"] = [f"Informe um título de 1 a {MAIOR_TITULO} caracteres."]
    if mensagem_limpa is None:
        erros["mensagem"] = [f"Informe uma mensagem de 1 a {MAIOR_CORPO} caracteres."]
    if erros or titulo_limpo is None or mensagem_limpa is None:
        raise ValidationError(erros)
    with transaction.atomic():
        existente = Comunicado.objects.filter(token=token).first()
        if existente is not None:
            return existente, False
        compradores = list(compradores_do_comunicado())
        try:
            with transaction.atomic():
                comunicado = Comunicado.objects.create(
                    titulo=titulo_limpo,
                    mensagem=mensagem_limpa,
                    autor=autor,
                    token=token,
                    destinatarios=len(compradores),
                )
        except IntegrityError:
            # outra requisição com o mesmo token confirmou primeiro
            existente = Comunicado.objects.filter(token=token).first()
            if existente is None:
                raise
            return existente, False
        novas = emitir_evento_para_varios(
            Evento.COMUNICADO,
            compradores,
            titulo=titulo_limpo,
            corpo=mensagem_limpa,
            link=LINK_DOS_COMUNICADOS,
            chave_base=f"comunicado:{comunicado.pk}",
        )
        if novas != comunicado.destinatarios:
            raise RuntimeError("a distribuição do comunicado não coincide com os destinatários")
        registrar_auditoria(
            autor,
            "comunicado.publicar",
            comunicado,
            {"comunicado": comunicado.pk, "destinatarios": comunicado.destinatarios},
        )
    return comunicado, True
