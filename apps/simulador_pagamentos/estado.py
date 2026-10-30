"""Leitura e mudança do estado das cobranças simuladas (E07-01), usadas pelo provedor e pelos
controles. A situação só muda por aqui, e toda mudança gera um aviso não entregue."""

import hashlib
import hmac
import logging
import re
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.db import connections

from apps.nucleo.tempo import agora, somar_horas
from apps.nucleo.valores import arredondar_centavos
from apps.pagamentos.provedor import (
    PagamentoConsultado,
    PagamentoNaoEncontrado,
    SituacaoNoProvedor,
)
from apps.simulador_pagamentos.models import (
    AvisoSimulado,
    CobrancaSimulada,
    EstornoSimulado,
    MovimentoSimulado,
)
from apps.simulador_pagamentos.plano import PLANO, Anterior
from apps.simulador_pagamentos.roteador import ALIAS

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
    aprovada = situacao == SituacaoNoProvedor.APROVADO
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
        tarifa=cobranca.tarifa if aprovada else None,
        liberado_em=cobranca.liberado_em if aprovada else None,
    )


def novo_aviso(id_externo: str) -> AvisoSimulado:
    return AvisoSimulado.objects.create(tipo="pagamento", id_externo=id_externo, criado_em=agora())


def mudar(
    cobranca: CobrancaSimulada, situacao: SituacaoNoProvedor, aprovado_em: datetime | None = None
) -> None:
    """Muda a situação (com a cobrança travada) e cria o aviso."""
    PLANO.registrar_mudanca(cobranca.pk, Anterior(cobranca.situacao, cobranca.aprovado_em))
    cobranca.situacao = situacao.value
    campos = ["situacao", "aprovado_em"]
    if aprovado_em is not None:
        cobranca.aprovado_em = aprovado_em
    if situacao == SituacaoNoProvedor.APROVADO and aprovado_em is not None:
        _registrar_aprovacao(cobranca, aprovado_em)
        campos += ["tarifa", "liberado_em"]
    cobranca.save(update_fields=campos)
    novo_aviso(cobranca.id_externo)


def _registrar_aprovacao(cobranca: CobrancaSimulada, aprovado_em: datetime) -> None:
    """A tarifa do meio, arredondada uma vez a centavos, e a liberação; a conta do provedor
    recebe o pagamento e, havendo tarifa, o desconto dela, ambos liberados juntos."""
    percentual, fixa = PLANO.tarifa_do(cobranca.meio)
    tarifa = arredondar_centavos(cobranca.valor * percentual / Decimal(100) + fixa)
    liberado_em = somar_horas(aprovado_em, PLANO.liberacao_do(cobranca.meio))
    cobranca.tarifa = tarifa
    cobranca.liberado_em = liberado_em
    novo_movimento("pagamento", "pagamento", cobranca.valor, aprovado_em, liberado_em, cobranca)
    if tarifa > 0:
        novo_movimento("tarifa", "tarifa", -tarifa, aprovado_em, liberado_em, cobranca)


def novo_movimento(
    tipo: str,
    descricao: str,
    valor: Decimal,
    ocorrido_em: datetime,
    liberado_em: datetime,
    cobranca: CobrancaSimulada | None = None,
    id_estorno: str = "",
) -> MovimentoSimulado:
    return MovimentoSimulado.objects.create(
        tipo=tipo,
        descricao=descricao,
        valor=valor,
        id_externo=cobranca.id_externo if cobranca is not None else "",
        ocorrido_em=ocorrido_em,
        liberado_em=liberado_em,
        id_estorno=id_estorno,
    )


_ID_DO_ESTORNO = re.compile(r"sim-est-([1-9][0-9]{0,17})")


def obter_estorno(id_estorno: str, *, travar: bool = False) -> EstornoSimulado:
    achado = _ID_DO_ESTORNO.fullmatch(id_estorno)
    consulta = EstornoSimulado.objects.select_for_update() if travar else EstornoSimulado.objects
    estorno = consulta.filter(pk=int(achado.group(1))).first() if achado else None
    if estorno is None:
        raise ValueError("estorno desconhecido")
    return estorno


# O saldo liberado da conta simulada é um recurso único, comum a todos os pagamentos (E10-R02): a
# trava consultiva de transação serializa quem lê o saldo para aceitar um débito e quem muda um
# estorno em processamento. A chave é fixa.
CHAVE_DA_TRAVA_DO_SALDO = 7_151_002


def travar_o_saldo() -> None:
    """Toma a trava do saldo até o fim da transação do simulador. Vem sempre depois da trava da
    cobrança ou do estorno (a ordem é a mesma em toda operação), então não há inversão."""
    with connections[ALIAS].cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [CHAVE_DA_TRAVA_DO_SALDO])


def concluir(estorno: EstornoSimulado, instante: datetime) -> None:
    """Conclui o estorno: ele passa a ser visível e o débito entra na conta."""
    estorno.situacao = "concluido"
    estorno.concluido_em = instante
    estorno.visivel = True
    estorno.save(update_fields=["situacao", "concluido_em", "visivel"])
    novo_movimento(
        "devolucao",
        "refund",
        -estorno.valor,
        instante,
        instante,
        estorno.cobranca,
        id_estorno=estorno.id_estorno,
    )


def assinar(corpo: bytes) -> str:
    segredo = settings.SEGREDO_AVISOS_SIMULADOR
    if not segredo:
        raise RuntimeError("SEGREDO_AVISOS_SIMULADOR não configurado")
    return hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
