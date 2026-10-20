"""Consulta ao provedor antes de decisões irreversíveis (E07-06).

Apuração final, aprovação do resultado da cobrança, envio do pedido formal, devolução e repasse
não podem confiar só no que o sistema já registrou: um aviso pode ter se perdido ou atrasado. Este
é o serviço único que essas decisões chamam, antes de abrir a transação delas e sem segurar
travas: busca no provedor os pagamentos da referência (inclusive os desconhecidos), reconsulta os
já registrados (a busca pode atrasar, L-6) e sincroniza tudo. Se o provedor não responde, levanta
`ConsultaAoProvedorFalhou` e quem chamou não decide (infraestrutura 4.2).
"""

import logging

from django.db import transaction

from apps.pagamentos.models import PagamentoNoProvedor
from apps.pagamentos.provedor import (
    PagamentoNaoEncontrado,
    ProvedorIndisponivel,
    RecusaDoProvedor,
    obter_provedor,
)
from apps.pagamentos.sincronizacao import sincronizar_pagamento

logger = logging.getLogger(__name__)


class ConsultaAoProvedorFalhou(Exception):
    """O provedor não respondeu à consulta: a decisão fica bloqueada. `motivo`: `indisponivel`,
    `recusa` ou `nao_encontrado`. A mensagem não leva dado pessoal nem valor."""

    def __init__(self, referencia_externa: str, motivo: str) -> None:
        super().__init__(f"consulta ao provedor falhou: {motivo}")
        self.referencia_externa = referencia_externa
        self.motivo = motivo


_MOTIVOS: tuple[tuple[type[Exception], str], ...] = (
    (ProvedorIndisponivel, "indisponivel"),
    (RecusaDoProvedor, "recusa"),
    (PagamentoNaoEncontrado, "nao_encontrado"),
)


def consultar_antes_de_decidir(referencia_externa: str) -> list[PagamentoNoProvedor]:
    """Sincroniza todos os pagamentos da referência e devolve os registros, relidos do banco,
    por `criado_no_provedor_em` e `id_externo`. Cada pagamento é sincronizado numa transação
    curta própria; o que já foi sincronizado fica gravado mesmo se uma consulta depois falhar."""
    provedor = obter_provedor()
    try:
        encontrados = provedor.buscar_por_referencia(referencia_externa)
        vistos = set()
        for resposta in encontrados:
            with transaction.atomic():
                sincronizar_pagamento(resposta, origem="busca")
            vistos.add(resposta.id_externo)
        registrados = (
            PagamentoNoProvedor.objects.filter(
                provedor=provedor.nome, referencia_externa=referencia_externa
            )
            .exclude(id_externo__in=vistos)
            .order_by("criado_no_provedor_em", "id_externo")
        )
        for registro in list(registrados):
            resposta = provedor.consultar_pagamento(registro.id_externo)
            with transaction.atomic():
                sincronizar_pagamento(resposta, origem="decisao")
    except (ProvedorIndisponivel, RecusaDoProvedor, PagamentoNaoEncontrado) as erro:
        motivo = next(m for tipo, m in _MOTIVOS if isinstance(erro, tipo))
        logger.warning("Consulta antes de decidir: %s %s", referencia_externa, motivo)
        raise ConsultaAoProvedorFalhou(referencia_externa, motivo) from erro
    return list(
        PagamentoNoProvedor.objects.filter(
            provedor=provedor.nome, referencia_externa=referencia_externa
        ).order_by("criado_no_provedor_em", "id_externo")
    )


def situacao_registrada(id_externo: str | None) -> str | None:
    """A situação que o sistema tem do pagamento, ou `None` se ainda não o conhece. Só leitura."""
    return (
        PagamentoNoProvedor.objects.filter(id_externo=id_externo)
        .values_list("situacao", flat=True)
        .first()
    )


def aprovados_da_referencia(referencia_externa: str) -> list[PagamentoNoProvedor]:
    """Os pagamentos aprovados da referência, por criação e id. Só leitura."""
    return list(
        PagamentoNoProvedor.objects.filter(
            referencia_externa=referencia_externa, situacao="aprovado"
        ).order_by("criado_no_provedor_em", "id_externo")
    )


def travar_pagamento(pk: int) -> PagamentoNoProvedor:
    """Relê o pagamento com a linha travada (exige transação). É o primeiro item da ordem das
    travas: pagamento, situação do pedido, tentativa."""
    return PagamentoNoProvedor.objects.select_for_update().get(pk=pk)
