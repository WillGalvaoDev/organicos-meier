"""O reenvio manual do pedido formal (E13-03).

Cada acionamento do administrador faz exatamente uma tentativa, com o conteúdo gravado no pedido
formal, e nunca inicia outro ciclo automático. Durante o ciclo automático o reenvio é recusado
sem esperar; entre reenvios a trava do envio é esperada, e os dois se executam em sequência. O
token único de cada acionamento faz o duplo clique gerar um só envio.
"""

import logging
import uuid
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction

from apps.contas.models import Conta, Papel, Situacao
from apps.notificacoes.canais import enviar_email
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora
from apps.pagamentos.consulta import consultar_antes_de_decidir, exigir_fora_de_transacao
from apps.pedidos.envio_do_pedido_formal import RESPOSTA_DO_SUCESSO
from apps.pedidos.models import (
    EnvioDoPedidoFormal,
    Pedido,
    PedidoFormal,
    ResultadoDoEnvio,
    SituacaoDoEnvio,
    TentativaDeEnvioDoPedidoFormal,
    TipoDaTentativaDeEnvio,
)
from apps.rodadas.models import Etapa, Rodada

__all__ = [
    "ReenvioRecusado",
    "ReenvioRegistrado",
    "consultar_antes_de_decidir",
    "enviar_email",
    "pode_reenviar",
    "reenviar_pedido_formal",
]

logger = logging.getLogger(__name__)

MAIOR_RESPOSTA = 100
CHAVE_DA_TRAVA_DOS_ACIONAMENTOS = 7_151_013
MENSAGENS = {
    "token_invalido": "O reenvio não pôde ser identificado; recarregue a página e tente de novo.",
    "rodada_cancelada": "A rodada foi cancelada; o pedido formal não é reenviado.",
    "ciclo_em_andamento": (
        "O envio automático ainda está em andamento; o reenvio fica disponível quando ele terminar."
    ),
}


class ReenvioRecusado(Exception):
    """O reenvio não pode ser feito agora. `codigo` diz o motivo; a mensagem é a da tela."""

    def __init__(self, codigo: str) -> None:
        self.codigo = codigo
        super().__init__(MENSAGENS[codigo])


@dataclass(frozen=True)
class ReenvioRegistrado:
    """A tentativa do acionamento. `nova` é falso quando o token já tinha gerado a tentativa."""

    tentativa: TentativaDeEnvioDoPedidoFormal
    nova: bool


def _motivo_da_recusa(rodada_etapa: str, situacao: str) -> str | None:
    """A conferência da regra 5, na ordem: a primeira que falha vale."""
    if rodada_etapa == Etapa.CANCELADA:
        return "rodada_cancelada"
    if situacao == SituacaoDoEnvio.EM_ANDAMENTO:
        return "ciclo_em_andamento"
    if situacao == SituacaoDoEnvio.INTERROMPIDO:
        return "rodada_cancelada"
    return None


def _codigo_da_recusa(pedido_formal: PedidoFormal) -> str | None:
    etapa = Rodada.objects.values_list("etapa", flat=True).get(pk=pedido_formal.rodada_id)
    situacao = EnvioDoPedidoFormal.objects.values_list("situacao", flat=True).get(
        pedido_formal=pedido_formal
    )
    return _motivo_da_recusa(etapa, situacao)


def pode_reenviar(pedido_formal: PedidoFormal) -> tuple[bool, str]:
    """Se o reenvio está disponível agora, sem trava, e a mensagem que explica quando não está."""
    motivo = _codigo_da_recusa(pedido_formal)
    return (True, "") if motivo is None else (False, MENSAGENS[motivo])


def _exigir_administrador(autor: Conta | None) -> Conta:
    if autor is None or autor.papel != Papel.ADMINISTRADOR or autor.situacao != Situacao.ATIVA:
        raise PermissionDenied
    return autor


def _como_uuid(token: object) -> uuid.UUID:
    if isinstance(token, uuid.UUID):
        return token
    if isinstance(token, str) and token:
        try:
            return uuid.UUID(token)
        except ValueError:
            pass
    raise ReenvioRecusado("token_invalido")


def _da_tentativa_do_token(
    pedido_formal: PedidoFormal, token: uuid.UUID
) -> TentativaDeEnvioDoPedidoFormal | None:
    """A tentativa que o token já gerou neste pedido formal; em outro pedido formal, recusa."""
    existente: TentativaDeEnvioDoPedidoFormal | None = (
        TentativaDeEnvioDoPedidoFormal.objects.filter(token=token).first()
    )
    if existente is not None and existente.pedido_formal_id != pedido_formal.pk:
        raise ReenvioRecusado("token_invalido")
    return existente


def reenviar_pedido_formal(
    autor: Conta | None, pedido_formal: PedidoFormal, *, token: object
) -> ReenvioRegistrado:
    """Reenvia o pedido formal uma vez, com o token do acionamento.

    Só o administrador ativo (`PermissionDenied`). Só fora de transação (`RuntimeError`): a
    consulta ao provedor vem antes da transação e, se falhar, bloqueia o reenvio.
    """
    administrador = _exigir_administrador(autor)
    exigir_fora_de_transacao()
    chave = _como_uuid(token)
    existente = _da_tentativa_do_token(pedido_formal, chave)
    if existente is not None:
        return ReenvioRegistrado(existente, nova=False)
    motivo = _codigo_da_recusa(pedido_formal)
    if motivo is not None:
        raise ReenvioRecusado(motivo)
    pedidos = Pedido.objects.filter(abertura__ciclo_id=pedido_formal.ciclo_id).order_by("pk")
    for pedido in pedidos:
        consultar_antes_de_decidir(pedido.referencia_externa)
    try:
        with transaction.atomic():
            return _tentar(administrador, pedido_formal, chave)
    except IntegrityError:
        existente = _da_tentativa_do_token(pedido_formal, chave)
        if existente is None:
            raise
        return ReenvioRegistrado(existente, nova=False)


def _tomar_a_posse_do_token(token: uuid.UUID) -> None:
    """A posse exclusiva do token no sistema inteiro, retida até o fim da transação. É a primeira
    instrução da transação, antes de qualquer outra trava, e espera. Dois tokens com o mesmo
    `hashtext` só se executam em sequência; a conferência continua sendo pelo token."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s, hashtext(%s))",
            [CHAVE_DA_TRAVA_DOS_ACIONAMENTOS, str(token)],
        )


def _tentar(
    administrador: Conta, pedido_formal: PedidoFormal, token: uuid.UUID
) -> ReenvioRegistrado:
    _tomar_a_posse_do_token(token)
    envio = (
        EnvioDoPedidoFormal.objects.select_for_update(of=("self",))
        .select_related("pedido_formal__fornecedor")
        .get(pedido_formal=pedido_formal)
    )
    rodada = Rodada.objects.select_for_update(no_key=True).get(pk=pedido_formal.rodada_id)
    existente = _da_tentativa_do_token(pedido_formal, token)
    if existente is not None:
        return ReenvioRegistrado(existente, nova=False)
    motivo = _motivo_da_recusa(rodada.etapa, envio.situacao)
    if motivo is not None:
        raise ReenvioRecusado(motivo)
    pedido = envio.pedido_formal
    destino = pedido.fornecedor.email_pedido
    iniciada = agora()
    try:
        enviar_email(destino, pedido.assunto, pedido.corpo)
        resultado, resposta = ResultadoDoEnvio.SUCESSO, RESPOSTA_DO_SUCESSO
    except Exception as excecao:
        resultado, resposta = ResultadoDoEnvio.FALHA, type(excecao).__name__[:MAIOR_RESPOSTA]
    numero = TentativaDeEnvioDoPedidoFormal.objects.filter(pedido_formal=pedido).count() + 1
    tentativa = TentativaDeEnvioDoPedidoFormal.objects.create(
        pedido_formal=pedido,
        numero=numero,
        tipo=TipoDaTentativaDeEnvio.MANUAL,
        ordem_automatica=None,
        iniciada_em=iniciada,
        concluida_em=agora(),
        resultado=resultado,
        resposta=resposta,
        destino=destino,
        autor=administrador,
        token=token,
    )
    registrar_auditoria(
        administrador,
        "pedido_formal.reenviar",
        pedido,
        {
            "pedido_formal": pedido.pk,
            "numero": numero,
            "resultado": str(resultado),
            "acionamento": str(token),
        },
    )
    return ReenvioRegistrado(tentativa, nova=True)
