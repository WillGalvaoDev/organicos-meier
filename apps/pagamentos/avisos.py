"""Recebimento dos avisos do provedor (E07-05).

O aviso só avisa: não é prova de pagamento. Aqui se confere a autenticidade (pelo provedor),
registra-se o evento uma única vez e agenda-se a consulta do pagamento (E07-04); o estado só
muda quando a consulta volta (E07-03). Nada do corpo vira estado, e nenhum log leva o corpo nem
os cabeçalhos.
"""

import logging
from collections.abc import Mapping
from datetime import UTC

from django.db import connection, transaction

from apps.nucleo.tempo import agora
from apps.pagamentos.chamadas import agendar_chamada
from apps.pagamentos.models import AvisoRecebido
from apps.pagamentos.provedor import AvisoInvalido, obter_provedor

logger = logging.getLogger(__name__)

TAMANHO_MAXIMO_DO_AVISO = 64 * 1024
TIPO_DE_PAGAMENTO = "pagamento"


def receber_aviso(
    corpo: bytes, cabecalhos: Mapping[str, str], parametros: Mapping[str, str]
) -> int:
    """Devolve o código HTTP: 200 aceito (novo ou repetido), 400 corpo grande demais, 401 aviso
    não autêntico. Os dois últimos não gravam nada."""
    if len(corpo) > TAMANHO_MAXIMO_DO_AVISO:
        return 400
    provedor = obter_provedor()
    try:
        aviso = provedor.verificar_aviso(corpo, cabecalhos, parametros)
    except AvisoInvalido:
        logger.warning("Aviso de pagamento recusado")
        return 401
    recebido_em = agora()
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {AvisoRecebido._meta.db_table} "  # noqa: S608
                "(provedor, id_evento, tipo, id_externo, recebido_em) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (provedor, id_evento) DO NOTHING RETURNING id",
                [provedor.nome, aviso.id_evento, aviso.tipo, aviso.id_externo, recebido_em],
            )
            novo = cursor.fetchone() is not None
        if novo and aviso.tipo == TIPO_DE_PAGAMENTO:
            agendar_chamada(
                "consultar_pagamento",
                aviso.id_externo,
                parametros={
                    "origem": "aviso",
                    "aviso_recebido_em": recebido_em.astimezone(UTC).isoformat(),
                },
            )
    logger.info(
        "Aviso de pagamento %s: %s (%s)",
        aviso.id_evento,
        "novo" if novo else "repetido",
        aviso.id_externo,
    )
    return 200
