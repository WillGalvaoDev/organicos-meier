"""E-mails de acesso no registro de envios (E04-05).

Convite, link de acesso e recuperação de senha levam um token que só existe na memória da
requisição (no banco só há o hash). Por isso saem na hora, fora da fila, e o registro nasce já
concluído, com o corpo vazio e uma única tentativa. Não há retentativa automática: reenviar
exigiria guardar o token. A retentativa é a ação que já existe (novo convite, novo pedido), que
gera token e envio novos.

Nenhum token, link com token, destino ou corpo vai para o log.
"""

import logging
from typing import Any

from django.db import transaction

from apps.contas.models import Conta
from apps.notificacoes.canais import enviar_email
from apps.notificacoes.models import (  # noqa: F401
    CONTA_ALLAUTH,
    CONVITE,
    LINK_DE_ACESSO,
    TIPOS_DE_ACESSO,
    Envio,
    ResultadoDaTentativa,
    SituacaoEnvio,
    TentativaDeEnvio,
)
from apps.nucleo.tempo import agora

logger = logging.getLogger(__name__)

MAIOR_ERRO = 100


def enviar_email_de_acesso(
    tipo: str,
    *,
    destino: str,
    assunto: str,
    corpo: str,
    conta: Conta | None = None,
    referencia: Any,
    modelo: str = "",
) -> Envio:
    """Envia o e-mail, registra o resultado e devolve o `Envio`. Nunca propaga exceção.

    Sempre chamada de dentro do `transaction.on_commit` dos três fluxos, sem exceção (E04-R02).
    Se a gravação do registro falhar depois de um envio aceito, registra um erro com o tipo e a
    referência, sem destino, e devolve um `Envio` não gravado com o mesmo resultado.
    """
    iniciada_em = agora()
    erro = ""
    try:
        enviar_email(destino, assunto, corpo)
    except Exception as excecao:
        erro = type(excecao).__name__[:MAIOR_ERRO]
    concluida_em = agora()
    dados: dict[str, Any] = {
        "canal": "email",
        "tipo": tipo,
        "conta": conta,
        "destino": destino,
        "assunto": assunto[:150],
        "corpo": "",  # o corpo leva o segredo: nunca é gravado
        "chave": f"{tipo}:{referencia}",
        "situacao": SituacaoEnvio.FALHOU if erro else SituacaoEnvio.ENVIADO,
        "tentativas": 1,
        "criado_em": iniciada_em,
        "proxima_tentativa_em": iniciada_em,
        "concluido_em": concluida_em,
        "modelo": modelo,
    }
    try:
        with transaction.atomic():
            envio = Envio.objects.create(**dados)
            TentativaDeEnvio.objects.create(
                envio=envio,
                numero=1,
                iniciada_em=iniciada_em,
                concluida_em=concluida_em,
                resultado=ResultadoDaTentativa.FALHA if erro else ResultadoDaTentativa.SUCESSO,
                erro=erro,
            )
    except Exception:
        logger.error(
            "falha ao registrar o envio de acesso: tipo=%s referencia=%s", tipo, referencia
        )
        envio = Envio(**dados)
    if erro:
        logger.error(
            "falha no envio de acesso: tipo=%s referencia=%s erro=%s", tipo, referencia, erro
        )
    return envio
