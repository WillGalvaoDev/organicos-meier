"""Entradas dos pagamentos e tarifas no livro-razão (E09-04).

A E08-04 decide, uma vez por pagamento aprovado, se ele quita o pedido ou gera devolução integral.
Aqui essa decisão chega ao livro-razão, dentro da mesma transação (o sinal de destino decidido):
o pagamento que quita entra na custódia da rodada, por componente do pedido congelado; o que não
quita vira uma obrigação com o comprador, financiada pelo próprio pagamento, e nunca receita. A
tarifa é uma despesa, e não muda nenhum valor de fornecedor ou de comprador.

Este módulo não cita as classes dos registros de pagamento: só a sincronização escreve nelas
(cenário 37), e ele lê o pagamento pelo que o destino e o protocolo abaixo expõem.
"""

import logging
from decimal import Decimal
from typing import Protocol

from django.db import transaction

from apps.financeiro.alertas import abrir_alerta
from apps.financeiro.apuracao import cobrir_tarifas_pendentes_da_rodada, rodada_apurada
from apps.financeiro.livro import EXTERIOR, Transferencia, conta, lancar
from apps.financeiro.models import (
    Componente,
    Despesa,
    Destinacao,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    TipoDeDespesa,
    TipoDeMovimento,
)
from apps.nucleo.auditoria import SISTEMA
from apps.pagamentos.consulta import pagamentos_com_tarifa_e_destino, travar_pagamento
from apps.pedidos.models import DestinoDaDecisao, DestinoDoPagamento, MotivoDoDestino

logger = logging.getLogger(__name__)

ORIGEM_DA_OBRIGACAO = "pedidos.destinodopagamento"
MOTIVOS_COM_ALERTA = (MotivoDoDestino.APROVADO_APOS_A_MARGEM, MotivoDoDestino.DUPLICIDADE)


class _Pagamento(Protocol):
    pk: int
    id_externo: str
    valor: Decimal
    tarifa: Decimal | None


def _entrada_que_quita(destino: DestinoDoPagamento) -> MovimentoFinanceiro:
    pedido = destino.pedido
    if pedido is None:
        raise ValueError("um destino que quita sempre tem pedido")
    abertura = pedido.abertura
    componentes = (
        (Componente.PRODUTOS, pedido.produtos),
        (Componente.SERVICO, pedido.servico),
        (Componente.FRETE, pedido.frete),
    )
    transferencias = [
        Transferencia(
            EXTERIOR,
            conta(
                Destinacao.CUSTODIA,
                rodada=abertura.rodada_id,
                ciclo=abertura.ciclo_id,
                comprador=pedido.comprador_id,
                componente=componente,
            ),
            valor,
        )
        for componente, valor in componentes
        if valor > 0
    ]
    return lancar(
        tipo=TipoDeMovimento.ENTRADA_DE_PAGAMENTO,
        transferencias=transferencias,
        autor=SISTEMA,
        justificativa="Pagamento aprovado e aceito (P-6): entrada na custódia",
        origem=destino.pagamento,
        chave=f"entrada:{destino.pk}",
    )


def _obrigacao_do(destino: DestinoDoPagamento) -> tuple[ObrigacaoComComprador, bool]:
    """A obrigação de devolução integral do destino, e se ela acabou de ser criada."""
    existente: ObrigacaoComComprador | None = ObrigacaoComComprador.objects.filter(
        origem_tipo=ORIGEM_DA_OBRIGACAO, origem_id=str(destino.pk)
    ).first()
    if existente is not None:
        return existente, False
    pedido = destino.pedido
    abertura = pedido.abertura if pedido is not None else None
    criada = ObrigacaoComComprador.objects.create(
        rodada_id=abertura.rodada_id if abertura else None,
        ciclo_id=abertura.ciclo_id if abertura else None,
        pedido=pedido,
        comprador_id=pedido.comprador_id if pedido else None,
        origem_tipo=ORIGEM_DA_OBRIGACAO,
        origem_id=str(destino.pk),
        motivo=destino.motivo,
        integral=destino.pagamento.valor,
    )
    return criada, True


def _entrada_para_devolucao(destino: DestinoDoPagamento) -> MovimentoFinanceiro:
    obrigacao, criada = _obrigacao_do(destino)
    movimento = lancar(
        tipo=TipoDeMovimento.ENTRADA_PARA_DEVOLUCAO,
        transferencias=[
            Transferencia(
                EXTERIOR,
                conta(
                    Destinacao.OBRIGACAO_COMPRADOR,
                    obrigacao=obrigacao.pk,
                    rodada=obrigacao.rodada_id,
                    ciclo=obrigacao.ciclo_id,
                    comprador=obrigacao.comprador_id,
                ),
                destino.pagamento.valor,
            )
        ],
        autor=SISTEMA,
        justificativa=(
            "Pagamento que não quita (§8.3): obrigação de devolução integral financiada "
            "pelo próprio pagamento"
        ),
        origem=destino.pagamento,
        chave=f"entrada:{destino.pk}",
    )
    # o alerta abre uma vez, junto com a obrigação: repetir o registro não o reabre depois de
    # resolvido
    if criada and destino.motivo in MOTIVOS_COM_ALERTA:
        abrir_alerta(
            destino.motivo,
            destino.pagamento.id_externo,
            {
                "pagamento": destino.pagamento.id_externo,
                "pedido": destino.pedido_id,
                "valor": destino.pagamento.valor,
            },
        )
    return movimento


def registrar_entrada(destino: DestinoDoPagamento) -> MovimentoFinanceiro:
    """A entrada do destino no livro-razão, uma só por destino (chave `entrada:<destino>`).
    Exige transação, com o pagamento já travado."""
    if destino.destino == DestinoDaDecisao.QUITA:
        return _entrada_que_quita(destino)
    return _entrada_para_devolucao(destino)


def registrar_tarifa(pagamento: _Pagamento) -> MovimentoFinanceiro | None:
    """A despesa de tarifa do pagamento e o seu movimento, uma só por pagamento. Sem tarifa
    (nula ou zero) ou sem destino decidido, não faz nada: a tarefa registra quando vier."""
    if pagamento.tarifa is None or pagamento.tarifa <= 0:
        return None
    destino = (
        DestinoDoPagamento.objects.select_related("pedido__abertura")
        .filter(pagamento_id=pagamento.pk)
        .first()
    )
    if destino is None:
        return None
    rodada_id = destino.pedido.abertura.rodada_id if destino.pedido is not None else None
    Despesa.objects.get_or_create(
        pagamento_id=pagamento.pk,
        tipo=TipoDeDespesa.TARIFA,
        defaults={"valor": pagamento.tarifa, "rodada_id": rodada_id},
    )
    movimento = lancar(
        tipo=TipoDeMovimento.TARIFA,
        transferencias=[
            Transferencia(conta(Destinacao.DESPESAS_A_COBRIR), EXTERIOR, pagamento.tarifa)
        ],
        autor=SISTEMA,
        justificativa="Tarifa do provedor (P-1): despesa operacional",
        origem=destino.pagamento,
        chave=f"tarifa:{pagamento.pk}",
    )
    if destino.pedido is not None and rodada_apurada(destino.pedido.abertura.rodada):
        # a receita da rodada já existe: a tarifa nova tenta ser coberta por ela (P-1)
        cobrir_tarifas_pendentes_da_rodada(destino.pedido.abertura.rodada)
    return movimento


def registrar_tarifas_pendentes_agora() -> int:
    """Registra a tarifa dos pagamentos que têm destino e tarifa, mas ainda não têm despesa
    (a tarifa chegou depois da decisão). Devolve quantas despesas nasceram."""
    registradas = 0
    for pk in pagamentos_com_tarifa_e_destino():
        with transaction.atomic():
            pagamento = travar_pagamento(pk)  # a primeira trava da ordem global
            if Despesa.objects.filter(pagamento_id=pk, tipo=TipoDeDespesa.TARIFA).exists():
                continue
            if registrar_tarifa(pagamento) is not None:
                registradas += 1
    return registradas
