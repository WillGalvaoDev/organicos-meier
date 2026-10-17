"""Criação, validação e leitura de notificações (E04-01).

As etapas nunca chamam `criar_notificacao` diretamente: usam `emitir_evento` (E04-02). As
validações vivem em `validar_notificacao`, que a gravação em lote também usa, para que nenhuma
notificação seja gravada sem as mesmas regras. Violação é erro de programação de quem emite.
"""

import re
from typing import Any

from apps.contas.models import Conta
from apps.notificacoes.eventos import DESTINATARIO_POR_EVENTO, Evento
from apps.notificacoes.models import PADRAO_LINK_INTERNO, Notificacao
from apps.nucleo.tempo import agora

MAIOR_TITULO = 150
MAIOR_CORPO = 2000
MAIOR_LINK = 500
MAIOR_CHAVE = 200


class NotificacaoInvalida(Exception):
    """Violação de regra por quem emite; `campo` diz qual."""

    def __init__(self, campo: str, mensagem: str) -> None:
        super().__init__(f"{campo}: {mensagem}")
        self.campo = campo


def _texto(campo: str, valor: Any, maior: int) -> None:
    if not isinstance(valor, str) or not (1 <= len(valor) <= maior):
        raise NotificacaoInvalida(campo, f"deve ter de 1 a {maior} caracteres")


def validar_notificacao(
    conta: Conta, evento: Any, *, titulo: Any, corpo: Any, link: Any, chave: Any
) -> None:
    """Levanta `NotificacaoInvalida` na primeira violação; não grava nada."""
    if not isinstance(evento, str) or evento not in Evento.values:
        raise NotificacaoInvalida("evento", "evento desconhecido")
    if conta.papel != DESTINATARIO_POR_EVENTO[Evento(evento)]:
        raise NotificacaoInvalida("conta", "o papel da conta não é o destinatário do evento")
    _texto("titulo", titulo, MAIOR_TITULO)
    _texto("corpo", corpo, MAIOR_CORPO)
    if link is not None:
        _texto("link", link, MAIOR_LINK)
        if link.startswith("//") or not re.fullmatch(PADRAO_LINK_INTERNO, link):
            raise NotificacaoInvalida("link", "deve ser um caminho relativo do site")
    _texto("chave", chave, MAIOR_CHAVE)


def criar_notificacao(
    conta: Conta,
    evento: Evento,
    *,
    titulo: str,
    corpo: str,
    link: str | None = None,
    chave: str,
) -> Notificacao:
    validar_notificacao(conta, evento, titulo=titulo, corpo=corpo, link=link, chave=chave)
    return Notificacao.objects.create(
        conta=conta, evento=evento, titulo=titulo, corpo=corpo, link=link, chave=chave
    )


def marcar_como_lida(conta: Conta, pk: int) -> bool | None:
    """Marca a notificação da conta como lida, uma única vez.

    Devolve `True` se gravou, `False` se já estava lida e `None` se não existe ou é de outra
    conta. A gravação é condicional (`lida_em IS NULL`): duas marcações simultâneas gravam uma só.
    """
    gravadas = Notificacao.objects.filter(pk=pk, conta=conta, lida_em__isnull=True).update(
        lida_em=agora()
    )
    if gravadas:
        return True
    return False if Notificacao.objects.filter(pk=pk, conta=conta).exists() else None


def marcar_todas_como_lidas(conta: Conta) -> int:
    """Um único `UPDATE` das não lidas da conta."""
    return Notificacao.objects.filter(conta=conta, lida_em__isnull=True).update(lida_em=agora())
