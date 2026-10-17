"""Emissão de eventos (E04-02).

As etapas chamam `emitir_evento` (ou `emitir_evento_para_varios`) dentro da transação do próprio
fato. A notificação no site e os envios de e-mail nascem e morrem junto com ele. A emissão nunca
fala com serviço externo: o envio acontece depois, em outra transação (E04-03).

Idempotência: a chave da notificação é `UNIQUE`; emitir de novo com a mesma chave devolve a
existente, sem criar nada. Chave reutilizada com conteúdo diferente é erro de quem emite.
Nada aqui registra e-mail, nome, título nem corpo em log.
"""

import logging
from collections.abc import Iterable
from typing import Any

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.transaction import TransactionManagementError

from apps.contas.models import Conta
from apps.notificacoes.eventos import CANAIS_POR_EVENTO, Canal, Evento
from apps.notificacoes.models import Envio, Notificacao
from apps.notificacoes.servicos import validar_notificacao
from apps.nucleo.tempo import agora

logger = logging.getLogger(__name__)

PREFIXO_DO_ASSUNTO = "Orgânicos Méier: "
MAIOR_ASSUNTO = 150
RODAPE = (
    "Você recebeu este aviso porque tem conta no Orgânicos Méier. "
    "As notificações também ficam no seu perfil do site."
)


class ChaveDeEventoReutilizada(Exception):
    """A chave já existe com conteúdo diferente: erro de programação de quem emite."""


def _exigir_transacao() -> None:
    if not connection.in_atomic_block:
        raise TransactionManagementError("a emissão de evento exige uma transação aberta.")


def _assunto(titulo: str) -> str:
    return (PREFIXO_DO_ASSUNTO + titulo)[:MAIOR_ASSUNTO]


def _corpo_do_email(corpo: str, link: str | None) -> str:
    partes = [corpo]
    if link:
        partes.append("Acesse: " + settings.ORIGEM_PUBLICA.rstrip("/") + link)
    partes.append(RODAPE)
    return "\n\n".join(partes)


def _mesmo_conteudo(
    existente: Notificacao, evento: str, conta_id: int, titulo: str, corpo: str, link: str | None
) -> bool:
    return (
        existente.evento == evento
        and existente.conta_id == conta_id
        and existente.titulo == titulo
        and existente.corpo == corpo
        and existente.link == link
    )


def _recusar_chave(evento: str, conta_id: int) -> ChaveDeEventoReutilizada:
    logger.error("chave de evento reutilizada: evento=%s conta=%s", evento, conta_id)
    return ChaveDeEventoReutilizada("chave de evento reutilizada com conteúdo diferente")


def _texto_do_whatsapp(titulo: str, link: str | None) -> str:
    if not link:
        return titulo
    return f"{titulo} {settings.ORIGEM_PUBLICA.rstrip('/')}{link}"


def _recebe_whatsapp(conta: Conta) -> bool:
    return (
        settings.CANAL_WHATSAPP != "desligado"
        and bool(conta.telefone)
        and conta.whatsapp_consentido_em is not None
    )


def _envios_externos(
    evento: Evento, notificacao: Notificacao, conta: Conta, criado_em: Any
) -> list[Envio]:
    """Um envio por canal externo do evento; o WhatsApp só com número e consentimento."""
    canais = CANAIS_POR_EVENTO[evento]
    envios: list[Envio] = []
    comum: dict[str, Any] = {
        "tipo": evento.value,
        "notificacao": notificacao,
        "conta": conta,
        "criado_em": criado_em,
        "proxima_tentativa_em": criado_em,
    }
    if Canal.EMAIL in canais:
        envios.append(
            Envio(
                canal=Canal.EMAIL,
                destino=conta.email_normalizado,
                assunto=_assunto(notificacao.titulo),
                corpo=_corpo_do_email(notificacao.corpo, notificacao.link),
                chave=f"{notificacao.chave}:{Canal.EMAIL.value}",
                **comum,
            )
        )
    if Canal.WHATSAPP in canais and _recebe_whatsapp(conta):
        envios.append(
            Envio(
                canal=Canal.WHATSAPP,
                destino="",  # o número é lido da conta no momento do envio
                assunto=_assunto(notificacao.titulo),
                corpo=_texto_do_whatsapp(notificacao.titulo, notificacao.link),
                chave=f"{notificacao.chave}:{Canal.WHATSAPP.value}",
                **comum,
            )
        )
    return envios


def emitir_evento(
    evento: Evento,
    conta: Conta,
    *,
    titulo: str,
    corpo: str,
    link: str | None = None,
    chave: str,
) -> Notificacao:
    """Grava a notificação e os envios de e-mail do evento, ou devolve a já emitida."""
    _exigir_transacao()
    validar_notificacao(conta, evento, titulo=titulo, corpo=corpo, link=link, chave=chave)
    existente = Notificacao.objects.filter(chave=chave).first()
    if existente is None:
        agora_ = agora()
        try:
            with transaction.atomic():
                notificacao = Notificacao.objects.create(
                    conta=conta,
                    evento=evento,
                    titulo=titulo,
                    corpo=corpo,
                    link=link,
                    chave=chave,
                    criada_em=agora_,
                )
                Envio.objects.bulk_create(_envios_externos(evento, notificacao, conta, agora_))
        except IntegrityError:
            # outra transação confirmou a mesma chave entre a leitura e a gravação
            existente = Notificacao.objects.filter(chave=chave).first()
            if existente is None:
                raise
        else:
            return notificacao
    if not _mesmo_conteudo(existente, evento.value, conta.pk, titulo, corpo, link):
        raise _recusar_chave(evento.value, conta.pk)
    return existente


_INSERIR_EM_LOTE = """
    INSERT INTO notificacoes_notificacao
        (conta_id, evento, titulo, corpo, link, chave, criada_em)
    VALUES {valores}
    ON CONFLICT (chave) DO NOTHING
    RETURNING id, chave
"""


def emitir_evento_para_varios(
    evento: Evento,
    contas: Iterable[Conta],
    *,
    titulo: str,
    corpo: str,
    link: str | None = None,
    chave_base: str,
) -> int:
    """Emite o mesmo evento para várias contas, em lote. Devolve quantas notificações são novas."""
    _exigir_transacao()
    unicas: dict[int, Conta] = {}
    for conta in contas:
        unicas.setdefault(conta.pk, conta)
    if not unicas:
        return 0
    chaves = {pk: f"{chave_base}:{pk}" for pk in unicas}
    for pk, conta in unicas.items():
        validar_notificacao(conta, evento, titulo=titulo, corpo=corpo, link=link, chave=chaves[pk])
    agora_ = agora()
    with transaction.atomic():
        valores = ", ".join(["(%s, %s, %s, %s, %s, %s, %s)"] * len(unicas))
        parametros: list[Any] = []
        for pk in unicas:
            parametros += [pk, evento.value, titulo, corpo, link, chaves[pk], agora_]
        with connection.cursor() as cursor:
            cursor.execute(_INSERIR_EM_LOTE.format(valores=valores), parametros)
            novas = {chave: id_ for id_, chave in cursor.fetchall()}
        existentes = [pk for pk in unicas if chaves[pk] not in novas]
        if existentes:
            gravadas = Notificacao.objects.in_bulk(
                [chaves[pk] for pk in existentes], field_name="chave"
            )
            for pk in existentes:
                atual = gravadas.get(chaves[pk])
                if atual is None or not _mesmo_conteudo(
                    atual, evento.value, pk, titulo, corpo, link
                ):
                    raise _recusar_chave(evento.value, pk)
        envios: list[Envio] = []
        for pk, conta in unicas.items():
            if chaves[pk] in novas:
                notificacao = Notificacao(
                    pk=novas[chaves[pk]],
                    conta=conta,
                    titulo=titulo,
                    corpo=corpo,
                    link=link,
                    chave=chaves[pk],
                )
                envios += _envios_externos(evento, notificacao, conta, agora_)
        Envio.objects.bulk_create(envios)
    return len(novas)
