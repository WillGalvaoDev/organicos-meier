"""Reconhecimento único dos pagamentos do provedor (E07-03).

O provedor é a fonte da verdade (infraestrutura 4.2): o sistema só sabe de um pagamento pelo que
uma consulta devolve. Este é o único módulo que escreve em `PagamentoNoProvedor` e
`ConsultaDoPagamento` (cenário 37): não existe rota, comando nem tela que registre um pagamento
recebido por fora.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from django.conf import settings
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError

from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.pagamentos.models import (
    ConsultaDoPagamento,
    DivergenciaDaConsulta,
    OrigemDaConsulta,
    PagamentoNoProvedor,
)
from apps.pagamentos.provedor import PagamentoConsultado, SituacaoNoProvedor
from apps.pagamentos.sinais import situacao_do_pagamento_mudou

logger = logging.getLogger(__name__)

ORIGENS_DA_CONSULTA = tuple(OrigemDaConsulta.values)


@dataclass(frozen=True)
class Sincronizacao:
    pagamento: PagamentoNoProvedor
    anterior: SituacaoNoProvedor | None
    atual: SituacaoNoProvedor
    mudou: bool
    divergencia: str


def _divergencia(pagamento: PagamentoNoProvedor, resposta: PagamentoConsultado) -> str:
    """O primeiro campo de identidade em que a resposta contraria o registro, ou vazio."""
    if resposta.referencia_externa != pagamento.referencia_externa:
        return DivergenciaDaConsulta.REFERENCIA.value
    if resposta.valor != pagamento.valor:
        return DivergenciaDaConsulta.VALOR.value
    if resposta.criado_em != pagamento.criado_no_provedor_em:
        return DivergenciaDaConsulta.CRIACAO.value
    gravado = pagamento.aprovado_no_provedor_em
    if gravado is not None and resposta.aprovado_em not in (None, gravado):
        return DivergenciaDaConsulta.APROVACAO.value
    # a tarifa e a liberação, uma vez gravadas, não mudam (E09-02)
    if pagamento.tarifa is not None and resposta.tarifa not in (None, pagamento.tarifa):
        return DivergenciaDaConsulta.TARIFA.value
    liberado = pagamento.liberado_no_provedor_em
    if liberado is not None and resposta.liberado_em not in (None, liberado):
        return DivergenciaDaConsulta.LIBERACAO.value
    return ""


def _aplica(anterior: SituacaoNoProvedor, resposta: SituacaoNoProvedor) -> bool:
    """Uma situação terminal nunca volta a pendente: seria uma leitura atrasada (L-6)."""
    if resposta == anterior:
        return False
    return not (resposta == SituacaoNoProvedor.PENDENTE and anterior != SituacaoNoProvedor.PENDENTE)


def sincronizar_pagamento(
    consultado: PagamentoConsultado, *, origem: str, aviso_recebido_em: datetime | None = None
) -> Sincronizacao:
    """Registra uma resposta do provedor e aplica a mudança de situação uma única vez.

    Insere o registro se ele não existir (`ON CONFLICT DO NOTHING`), trava a linha e só então
    compara e aplica: duas sincronizações do mesmo pagamento ficam em fila, e a segunda vê o que
    a primeira gravou. Cada resposta vira uma linha do histórico. Exige transação; uma exceção
    (inclusive de um receptor do sinal) desfaz toda a sincronização.
    """
    if not connection.in_atomic_block:
        raise TransactionManagementError("sincronizar_pagamento exige uma transação aberta.")
    if origem not in ORIGENS_DA_CONSULTA:
        raise ValueError(f"origem da consulta desconhecida: {origem!r}")
    with transaction.atomic():
        PagamentoNoProvedor.objects.bulk_create(
            [
                PagamentoNoProvedor(
                    provedor=consultado.provedor,
                    ambiente=settings.AMBIENTE,
                    id_externo=consultado.id_externo,
                    referencia_externa=consultado.referencia_externa,
                    valor=consultado.valor,
                    situacao=consultado.situacao.value,
                    criado_no_provedor_em=consultado.criado_em,
                    expira_em=consultado.expira_em,
                    aprovado_no_provedor_em=consultado.aprovado_em,
                    tarifa=consultado.tarifa,
                    liberado_no_provedor_em=consultado.liberado_em,
                    primeiro_aviso_em=aviso_recebido_em,
                    primeira_consulta_em=consultado.consultado_em,
                    ultima_consulta_em=consultado.consultado_em,
                )
            ],
            ignore_conflicts=True,
        )
        pagamento = PagamentoNoProvedor.objects.select_for_update().get(
            provedor=consultado.provedor, id_externo=consultado.id_externo
        )
        # a linha nova só é visível junto com o histórico da transação que a criou
        criado = not pagamento.consultas.exists()
        anterior: SituacaoNoProvedor | None
        if criado:
            # a criação conta como aplicada; já aprovada ou recusada, também como mudança
            anterior, divergencia, aplicada = None, "", True
            mudou = consultado.situacao != SituacaoNoProvedor.PENDENTE
        else:
            anterior = SituacaoNoProvedor(pagamento.situacao)
            divergencia = _divergencia(pagamento, consultado)
            mudou = _aplica(anterior, consultado.situacao)
            preenche = pagamento.aprovado_no_provedor_em is None and (
                consultado.aprovado_em is not None and (mudou or consultado.situacao == anterior)
            )
            preenche_tarifa = pagamento.tarifa is None and consultado.tarifa is not None
            preenche_liberacao = (
                pagamento.liberado_no_provedor_em is None and consultado.liberado_em is not None
            )
            aplicada = mudou or preenche or preenche_tarifa or preenche_liberacao
            campos = ["ultima_consulta_em"]
            if mudou:
                pagamento.situacao = consultado.situacao.value
                campos.append("situacao")
            if preenche:
                pagamento.aprovado_no_provedor_em = consultado.aprovado_em
                campos.append("aprovado_no_provedor_em")
            if preenche_tarifa:
                pagamento.tarifa = consultado.tarifa
                campos.append("tarifa")
            if preenche_liberacao:
                pagamento.liberado_no_provedor_em = consultado.liberado_em
                campos.append("liberado_no_provedor_em")
            pagamento.ultima_consulta_em = max(
                pagamento.ultima_consulta_em, consultado.consultado_em
            )
            if pagamento.primeiro_aviso_em is None and aviso_recebido_em is not None:
                pagamento.primeiro_aviso_em = aviso_recebido_em
                campos.append("primeiro_aviso_em")
            pagamento.save(update_fields=campos)
        ConsultaDoPagamento.objects.create(
            pagamento=pagamento,
            origem=origem,
            situacao=consultado.situacao.value,
            aprovado_em=consultado.aprovado_em,
            referencia_externa=consultado.referencia_externa,
            valor=consultado.valor,
            consultado_em=consultado.consultado_em,
            aplicada=aplicada,
            divergencia=divergencia,
        )
        if divergencia:
            logger.warning("Pagamento %s: divergência em %s", pagamento.id_externo, divergencia)
        if mudou:
            atual = SituacaoNoProvedor(pagamento.situacao)
            aprovado_em = pagamento.aprovado_no_provedor_em
            registrar_auditoria(
                SISTEMA,
                "pagamento.situacao",
                pagamento,
                {
                    "id_externo": pagamento.id_externo,
                    "anterior": anterior.value if anterior else None,
                    "atual": atual.value,
                    "aprovado_em": aprovado_em.astimezone(UTC).isoformat() if aprovado_em else None,
                    "origem": origem,
                },
            )
            situacao_do_pagamento_mudou.send(
                sender=PagamentoNoProvedor, pagamento=pagamento, anterior=anterior, atual=atual
            )
    return Sincronizacao(
        pagamento, anterior, SituacaoNoProvedor(pagamento.situacao), mudou, divergencia
    )
