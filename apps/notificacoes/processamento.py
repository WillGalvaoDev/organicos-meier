"""Processamento da fila de envios (E04-03 e E04-04).

Cada envio é tentado com a linha travada (`select_for_update(skip_locked=True)`) e o resultado é
gravado na mesma transação: se o processo cair depois de o serviço aceitar a mensagem e antes da
confirmação, a tentativa é desfeita e o envio se repete (pelo menos uma vez; o SMTP não tem chave
de idempotência). Nenhuma exceção do canal sai daqui, e nada fora de `Envio` e `TentativaDeEnvio`
é alterado: uma falha do canal externo nunca desfaz o fato nem a notificação no site (cenário 24).
Nenhum log registra destino, número, assunto ou conteúdo.

No WhatsApp, o consentimento é relido da conta no início de cada tentativa: a revogação vale para
mensagens ainda não enviadas, e o número usado é o atual.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction

from apps.contas.models import Conta
from apps.notificacoes.canais import enviar_email
from apps.notificacoes.eventos import Canal
from apps.notificacoes.models import (
    Envio,
    ResultadoDaTentativa,
    SituacaoEnvio,
    TentativaDeEnvio,
)
from apps.notificacoes.whatsapp import FalhaNoCanalExterno, obter_canal_whatsapp
from apps.nucleo.tempo import agora

logger = logging.getLogger(__name__)

MAXIMO_DE_TENTATIVAS = 3
# espera depois da falha de cada tentativa; a terceira falha encerra o envio
INTERVALOS: dict[int, timedelta] = {1: timedelta(minutes=1), 2: timedelta(minutes=10)}
MAIOR_ERRO = 100


def _enviar(envio: Envio, conta: Conta | None) -> None:
    if envio.canal == Canal.WHATSAPP:
        telefone = conta.telefone if conta is not None else None
        if not telefone:
            raise FalhaNoCanalExterno("conta sem telefone")
        obter_canal_whatsapp().enviar(telefone, envio.corpo, envio_id=envio.pk)
    else:
        enviar_email(envio.destino, envio.assunto, envio.corpo)


def _motivo_do_cancelamento(envio: Envio) -> tuple[str, Conta | None]:
    """Vazio se o envio pode ser tentado; senão o código do cancelamento (sem tentativa)."""
    if envio.canal != Canal.WHATSAPP:
        return "", None
    if envio.conta_id is None:
        return "sem_consentimento", None
    conta = Conta.objects.get(pk=envio.conta_id)
    if not conta.telefone or conta.whatsapp_consentido_em is None:
        return "sem_consentimento", conta
    if settings.CANAL_WHATSAPP == "desligado":
        return "canal_desligado", conta
    return "", conta


def _cancelar(envio: Envio, motivo: str) -> None:
    envio.situacao = SituacaoEnvio.CANCELADO
    envio.motivo_cancelamento = motivo
    envio.concluido_em = agora()
    envio.save(update_fields=["situacao", "motivo_cancelamento", "concluido_em"])


def _tentar(envio: Envio, conta: Conta | None) -> None:
    numero = envio.tentativas + 1
    iniciada_em = agora()
    erro = ""
    try:
        _enviar(envio, conta)
    except Exception as excecao:
        erro = type(excecao).__name__[:MAIOR_ERRO]
    concluida_em = agora()
    resultado = ResultadoDaTentativa.FALHA if erro else ResultadoDaTentativa.SUCESSO
    TentativaDeEnvio.objects.create(
        envio=envio,
        numero=numero,
        iniciada_em=iniciada_em,
        concluida_em=concluida_em,
        resultado=resultado,
        erro=erro,
    )
    envio.tentativas = numero
    campos = ["tentativas"]
    if not erro:
        envio.situacao = SituacaoEnvio.ENVIADO
        envio.concluido_em = concluida_em
        campos += ["situacao", "concluido_em"]
    elif numero < MAXIMO_DE_TENTATIVAS:
        envio.proxima_tentativa_em = concluida_em + INTERVALOS[numero]
        campos.append("proxima_tentativa_em")
        logger.warning("falha no envio: envio=%s tentativa=%s erro=%s", envio.pk, numero, erro)
    else:
        envio.situacao = SituacaoEnvio.FALHOU
        envio.concluido_em = concluida_em
        campos += ["situacao", "concluido_em"]
        logger.error(
            "envio encerrado sem sucesso: envio=%s tentativa=%s erro=%s", envio.pk, numero, erro
        )
    envio.save(update_fields=campos)


def processar_envios(*, limite: int = 100) -> int:
    """Trata os envios pendentes já vencidos, até `limite`. Devolve quantas tentativas fez.

    O `limite` conta os envios retirados da fila, inclusive os cancelados sem tentativa.
    """
    retirados = 0
    tentativas = 0
    while retirados < limite:
        with transaction.atomic():
            envio = (
                Envio.objects.select_for_update(skip_locked=True)
                .filter(situacao=SituacaoEnvio.PENDENTE, proxima_tentativa_em__lte=agora())
                .order_by("proxima_tentativa_em", "id")
                .first()
            )
            if envio is None:
                break
            retirados += 1
            motivo, conta = _motivo_do_cancelamento(envio)
            if motivo:
                _cancelar(envio, motivo)
            else:
                _tentar(envio, conta)
                tentativas += 1
    return tentativas
