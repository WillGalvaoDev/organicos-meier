"""Processamento da fila de envios (E04-03).

Cada envio é tentado com a linha travada (`select_for_update(skip_locked=True)`) e o resultado é
gravado na mesma transação: se o processo cair depois de o serviço aceitar a mensagem e antes da
confirmação, a tentativa é desfeita e o envio se repete (pelo menos uma vez; o SMTP não tem chave
de idempotência). Nenhuma exceção do canal sai daqui, e nada fora de `Envio` e `TentativaDeEnvio`
é alterado. Nenhum log registra destino, assunto ou conteúdo.
"""

import logging
from collections.abc import Callable
from datetime import timedelta

from django.db import transaction

from apps.notificacoes.canais import enviar_email
from apps.notificacoes.eventos import Canal
from apps.notificacoes.models import (
    Envio,
    ResultadoDaTentativa,
    SituacaoEnvio,
    TentativaDeEnvio,
)
from apps.nucleo.tempo import agora

logger = logging.getLogger(__name__)

MAXIMO_DE_TENTATIVAS = 3
# espera depois da falha de cada tentativa; a terceira falha encerra o envio
INTERVALOS: dict[int, timedelta] = {1: timedelta(minutes=1), 2: timedelta(minutes=10)}
MAIOR_ERRO = 100


def _enviar_por_email(envio: Envio) -> None:
    enviar_email(envio.destino, envio.assunto, envio.corpo)


_CANAIS: dict[str, Callable[[Envio], None]] = {Canal.EMAIL.value: _enviar_por_email}


def _tentar(envio: Envio) -> None:
    numero = envio.tentativas + 1
    iniciada_em = agora()
    erro = ""
    try:
        _CANAIS[envio.canal](envio)
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
    """Tenta os envios pendentes já vencidos, até `limite`. Devolve quantas tentativas fez."""
    feitas = 0
    while feitas < limite:
        with transaction.atomic():
            envio = (
                Envio.objects.select_for_update(skip_locked=True)
                .filter(situacao=SituacaoEnvio.PENDENTE, proxima_tentativa_em__lte=agora())
                .order_by("proxima_tentativa_em", "id")
                .first()
            )
            if envio is None:
                break
            _tentar(envio)
            feitas += 1
    return feitas
