"""A previsão de entrega (E13-05): o ajuste do administrador, o aviso aos compradores e a leitura
para as telas. A previsão inicial nasce com o pedido formal (E13-01); aqui só se acrescentam
ajustes, e nenhum deles muda o pedido formal congelado."""

import logging
from datetime import date, datetime

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.contas.models import Conta, Papel, Situacao
from apps.financeiro.models import PedidoApurado
from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao
from apps.pedidos.models import (
    OrigemDaPrevisao,
    Pedido,
    PedidoFormal,
    PrevisaoDeEntrega,
    SituacaoDePagamento,
)
from apps.pedidos.pedido_formal import previsao_vigente
from apps.rodadas.models import Etapa, Rodada

logger = logging.getLogger(__name__)

MENSAGENS = {
    "data_invalida": "Informe uma data válida.",
    "fora_de_aguardando_fornecedor": (
        "A previsão só pode ser ajustada com a rodada aguardando o fornecedor."
    ),
    "data_passada": "A previsão não pode ser uma data passada.",
    "sem_alteracao": "A data informada já é a previsão vigente.",
}


class PrevisaoRecusada(Exception):
    """O ajuste não pode ser feito. `codigo` diz o motivo; a mensagem é a da tela."""

    def __init__(self, codigo: str) -> None:
        self.codigo = codigo
        super().__init__(MENSAGENS[codigo])


def _formatar(data: date) -> str:
    return f"{data:%d/%m/%Y}"


def _exigir_administrador(autor: Conta | None) -> Conta:
    if autor is None or autor.papel != Papel.ADMINISTRADOR or autor.situacao != Situacao.ATIVA:
        raise PermissionDenied
    return autor


def previsao_do_pedido(pedido: Pedido) -> date | None:
    """A previsão vigente que o comprador vê: só no pedido válido (pago e na apuração aprovada)
    de uma rodada que aguarda o fornecedor."""
    if pedido.abertura.rodada.etapa != Etapa.AGUARDANDO_FORNECEDOR:
        return None
    if pedido.estado.situacao != SituacaoDePagamento.PAGO:
        return None
    valido = PedidoApurado.objects.filter(
        apuracao__ciclo_id=pedido.abertura.ciclo_id, pedido=pedido
    ).exists()
    if not valido:
        return None
    vigente = previsao_vigente(pedido.abertura.ciclo)
    return vigente.data if vigente is not None else None


def _avisar_os_compradores(
    previsao: PrevisaoDeEntrega, anterior: date, pedido_formal: PedidoFormal
) -> int:
    """Um aviso por comprador de pedido válido do ciclo. As suspensas recebem (consultam os
    pedidos pagos); as removidas não (acesso bloqueado, §2)."""
    nome = pedido_formal.fornecedor.nome
    validos = PedidoApurado.objects.filter(apuracao__ciclo_id=pedido_formal.ciclo_id).values(
        "pedido_id"
    )
    pedidos = Pedido.objects.filter(pk__in=validos).select_related("comprador").order_by("pk")
    avisados = 0
    for pedido in pedidos:
        if pedido.comprador.situacao == Situacao.REMOVIDA:
            continue
        emitir_evento(
            Evento.PREVISAO_DE_ENTREGA_ALTERADA,
            pedido.comprador,
            titulo=f"Previsão de entrega alterada: {nome}"[:150],
            corpo=(
                f"A previsão de entrega do seu pedido {pedido.pk} da rodada de {nome} passou de "
                f"{_formatar(anterior)} para {_formatar(previsao.data)}."
            ),
            link=f"/pedidos/{pedido.pk}/",
            chave=f"{Evento.PREVISAO_DE_ENTREGA_ALTERADA.value}:{previsao.pk}:{pedido.comprador_id}",
        )
        avisados += 1
    return avisados


def ajustar_previsao_de_entrega(
    autor: Conta | None, rodada: Rodada, data: object
) -> PrevisaoDeEntrega:
    """Ajusta a previsão de entrega do ciclo aprovado. Só o administrador ativo
    (`PermissionDenied`). A data é um `date`, não anterior a hoje em Brasília e diferente da
    vigente (`PrevisaoRecusada`). Avisa os compradores dos pedidos válidos na mesma transação."""
    administrador = _exigir_administrador(autor)
    if not isinstance(data, date) or isinstance(data, datetime):
        raise PrevisaoRecusada("data_invalida")
    with transaction.atomic():
        travada = Rodada.objects.select_for_update(no_key=True).get(pk=rodada.pk)
        pedido_formal = (
            PedidoFormal.objects.select_related("fornecedor", "ciclo")
            .filter(rodada=travada)
            .first()
        )
        if travada.etapa != Etapa.AGUARDANDO_FORNECEDOR or pedido_formal is None:
            raise PrevisaoRecusada("fora_de_aguardando_fornecedor")
        if data < no_fuso_da_operacao(agora()).date():
            raise PrevisaoRecusada("data_passada")
        vigente = previsao_vigente(pedido_formal.ciclo)
        anterior = vigente.data if vigente is not None else pedido_formal.previsao_inicial
        if data == anterior:
            raise PrevisaoRecusada("sem_alteracao")
        previsao = PrevisaoDeEntrega.objects.create(
            rodada=travada,
            ciclo=pedido_formal.ciclo,
            data=data,
            origem=OrigemDaPrevisao.AJUSTE,
            autor=administrador,
        )
        avisados = _avisar_os_compradores(previsao, anterior, pedido_formal)
        registrar_auditoria(
            administrador,
            "rodada.previsao_de_entrega",
            travada,
            {
                "rodada": travada.pk,
                "ciclo": pedido_formal.ciclo_id,
                "anterior": anterior.isoformat(),
                "nova": data.isoformat(),
                "compradores_avisados": avisados,
            },
        )
        return previsao
