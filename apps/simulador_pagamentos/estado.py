"""Leitura e mudança do estado das cobranças simuladas (E07-01), usadas pelo provedor e pelos
controles. A situação só muda por aqui, e toda mudança gera um aviso não entregue."""

import hashlib
import hmac
import logging
import re
from datetime import datetime

from django.conf import settings

from apps.nucleo.tempo import agora
from apps.pagamentos.provedor import (
    PagamentoConsultado,
    PagamentoNaoEncontrado,
    SituacaoNoProvedor,
)
from apps.simulador_pagamentos.models import AvisoSimulado, CobrancaSimulada
from apps.simulador_pagamentos.plano import PLANO, Anterior

logger = logging.getLogger("apps.simulador_pagamentos")

NOME = "simulador"
CABECALHO_DA_ASSINATURA = "X-Simulador-Assinatura"
_IDENTIFICADOR = re.compile(r"sim-([1-9][0-9]{0,17})")


def registrar(operacao: str, id_externo: str = "") -> None:
    """Log sem valor, descrição, referência nem dados para pagar."""
    logger.info("Simulador de pagamentos: %s %s", operacao, id_externo)


def obter(id_externo: str, *, travar: bool = False) -> CobrancaSimulada:
    achado = _IDENTIFICADOR.fullmatch(id_externo)
    consulta = CobrancaSimulada.objects.select_for_update() if travar else CobrancaSimulada.objects
    cobranca = consulta.filter(pk=int(achado.group(1))).first() if achado else None
    if cobranca is None:
        raise PagamentoNaoEncontrado("pagamento desconhecido")
    return cobranca


def consultado(cobranca: CobrancaSimulada, *, atrasavel: bool = False) -> PagamentoConsultado:
    """O pagamento como o provedor o devolve agora.

    Só consultas e buscas (`atrasavel`) podem ver o atraso de consistência (L-6): a situação
    anterior à última mudança. Criação e cancelamento devolvem o que o provedor registrou.
    """
    anterior = PLANO.visao_atrasada(cobranca.pk) if atrasavel else None
    situacao = anterior.situacao if anterior else cobranca.situacao
    aprovado_em = anterior.aprovado_em if anterior else cobranca.aprovado_em
    return PagamentoConsultado(
        provedor=NOME,
        id_externo=cobranca.id_externo,
        referencia_externa=cobranca.referencia_externa,
        valor=cobranca.valor,
        situacao=SituacaoNoProvedor(situacao),
        criado_em=cobranca.criado_em,
        aprovado_em=aprovado_em,
        expira_em=cobranca.expira_em,
        consultado_em=agora(),
    )


def novo_aviso(id_externo: str) -> AvisoSimulado:
    return AvisoSimulado.objects.create(tipo="pagamento", id_externo=id_externo, criado_em=agora())


def mudar(
    cobranca: CobrancaSimulada, situacao: SituacaoNoProvedor, aprovado_em: datetime | None = None
) -> None:
    """Muda a situação (com a cobrança travada) e cria o aviso."""
    PLANO.registrar_mudanca(cobranca.pk, Anterior(cobranca.situacao, cobranca.aprovado_em))
    cobranca.situacao = situacao.value
    if aprovado_em is not None:
        cobranca.aprovado_em = aprovado_em
    cobranca.save(update_fields=["situacao", "aprovado_em"])
    novo_aviso(cobranca.id_externo)


def assinar(corpo: bytes) -> str:
    segredo = settings.SEGREDO_AVISOS_SIMULADOR
    if not segredo:
        raise RuntimeError("SEGREDO_AVISOS_SIMULADOR não configurado")
    return hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
