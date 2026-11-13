"""O ciclo automático de envio do pedido formal (E13-02).

Uma tarefa por minuto aplica as transições do `EnvioDoPedidoFormal`: até três tentativas
automáticas no total, a primeira na emissão, a segunda 5 minutos depois da falha da primeira e a
terceira 30 minutos depois da falha da segunda. Depois da terceira falha, o administrador é
avisado. A consulta ao provedor vem antes de cada tentativa, fora de transação e sem trava; a
tentativa acontece sob o envio (`skip_locked`) e a rodada (`FOR NO KEY UPDATE`), com as travas
retidas durante o envio, para que duas tentativas do mesmo pedido formal nunca saiam juntas e o
cancelamento da rodada (E12) espere uma tentativa em curso. Nada aqui escreve no livro-razão, nos
pedidos ou nos pagamentos (§12).
"""

import logging
from datetime import datetime, timedelta

from django.db import transaction

from apps.contas.models import Conta, Papel, Situacao
from apps.notificacoes.canais import enviar_email
from apps.notificacoes.emissao import emitir_evento_para_varios
from apps.notificacoes.eventos import Evento
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou, consultar_antes_de_decidir
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
    "consultar_antes_de_decidir",
    "enviar_email",
    "estado_do_envio",
    "processar_pedidos_formais",
]

logger = logging.getLogger(__name__)

RESPOSTA_DO_SUCESSO = "aceito pelo serviço de e-mail"
MAIOR_RESPOSTA = 100
INTERVALOS = {1: timedelta(minutes=5), 2: timedelta(minutes=30)}
INTERVALO_DA_CONSULTA = timedelta(minutes=5)
MOTIVO_RODADA_CANCELADA = "rodada_cancelada"
TENTATIVAS_AUTOMATICAS = 3


def estado_do_envio(pedido_formal: PedidoFormal) -> str:
    """A situação gravada do envio, sem trava, para as telas."""
    return str(
        EnvioDoPedidoFormal.objects.filter(pedido_formal=pedido_formal)
        .values_list("situacao", flat=True)
        .get()
    )


def processar_pedidos_formais(*, limite: int = 50) -> int:
    """Faz as tentativas automáticas vencidas. Devolve quantas tentativas fez."""
    vencidos = list(
        EnvioDoPedidoFormal.objects.filter(
            situacao=SituacaoDoEnvio.EM_ANDAMENTO, proxima_tentativa_em__lte=agora()
        )
        .order_by("proxima_tentativa_em", "pk")
        .values_list("pk", flat=True)[:limite]
    )
    return sum(_processar(pk) for pk in vencidos)


def _rodada_cancelada(envio: EnvioDoPedidoFormal) -> bool:
    etapa = Rodada.objects.filter(pk=envio.pedido_formal.rodada_id).values_list("etapa", flat=True)
    return etapa.get() == Etapa.CANCELADA


def _consultar_o_provedor(envio: EnvioDoPedidoFormal) -> bool:
    """A consulta obrigatória antes do envio (infraestrutura 4.2), fora de transação e sem trava.
    Falhou: a tentativa não acontece e não conta, e a próxima fica para daqui a 5 minutos, mas só se
    o envio continua como no retrato da seleção (`envio`): uma consulta atrasada não substitui o
    agendamento de uma tentativa posterior (regra 3-A)."""
    pedidos = Pedido.objects.filter(abertura__ciclo_id=envio.pedido_formal.ciclo_id).order_by("pk")
    try:
        for pedido in pedidos:
            consultar_antes_de_decidir(pedido.referencia_externa)
    except ConsultaAoProvedorFalhou:
        logger.warning(
            "Consulta ao provedor falhou antes do pedido formal %s", envio.pedido_formal_id
        )
        with transaction.atomic():
            travado = (
                EnvioDoPedidoFormal.objects.select_for_update(skip_locked=True)
                .filter(
                    pk=envio.pk,
                    situacao=SituacaoDoEnvio.EM_ANDAMENTO,
                    automaticas=envio.automaticas,
                    proxima_tentativa_em=envio.proxima_tentativa_em,
                )
                .first()
            )
            if travado is not None:
                travado.proxima_tentativa_em = agora() + INTERVALO_DA_CONSULTA
                travado.save(update_fields=["proxima_tentativa_em"])
        return False
    return True


def _processar(envio_pk: int) -> int:
    envio = EnvioDoPedidoFormal.objects.select_related("pedido_formal").get(pk=envio_pk)
    if not _rodada_cancelada(envio) and not _consultar_o_provedor(envio):
        return 0
    with transaction.atomic():
        travado = (
            EnvioDoPedidoFormal.objects.select_for_update(skip_locked=True, of=("self",))
            .select_related("pedido_formal__fornecedor")
            .filter(pk=envio_pk)
            .first()
        )
        if travado is None:
            return 0
        rodada = Rodada.objects.select_for_update(no_key=True).get(
            pk=travado.pedido_formal.rodada_id
        )
        instante = agora()
        vencido = (
            travado.proxima_tentativa_em is not None and travado.proxima_tentativa_em <= instante
        )
        if travado.situacao != SituacaoDoEnvio.EM_ANDAMENTO or not vencido:
            return 0
        if rodada.etapa != Etapa.CANCELADA and not _igual_ao_retrato(travado, envio):
            return 0
        if rodada.etapa == Etapa.CANCELADA:
            _interromper(travado, instante)
            return 0
        _tentar(travado)
        return 1


def _igual_ao_retrato(travado: EnvioDoPedidoFormal, retrato: EnvioDoPedidoFormal) -> bool:
    """A consulta que precedeu esta tentativa pertence ao retrato lido na seleção; se uma tentativa
    ou um reagendamento mudou o envio depois dele, outra execução já agiu (regra 3-A)."""
    return (
        travado.automaticas == retrato.automaticas
        and travado.proxima_tentativa_em == retrato.proxima_tentativa_em
    )


def _interromper(envio: EnvioDoPedidoFormal, instante: datetime) -> None:
    envio.situacao = SituacaoDoEnvio.INTERROMPIDO
    envio.motivo_da_interrupcao = MOTIVO_RODADA_CANCELADA
    envio.concluido_em = instante
    envio.proxima_tentativa_em = None
    envio.save(
        update_fields=["situacao", "motivo_da_interrupcao", "concluido_em", "proxima_tentativa_em"]
    )
    dados = {"pedido_formal": envio.pedido_formal_id, "motivo": MOTIVO_RODADA_CANCELADA}
    registrar_auditoria(SISTEMA, "pedido_formal.interromper", envio.pedido_formal, dados)
    _auditar_a_conclusao(envio)


def _tentar(envio: EnvioDoPedidoFormal) -> None:
    pedido = envio.pedido_formal
    destino = pedido.fornecedor.email_pedido
    iniciada = agora()
    try:
        enviar_email(destino, pedido.assunto, pedido.corpo)
        resultado, resposta = ResultadoDoEnvio.SUCESSO, RESPOSTA_DO_SUCESSO
    except Exception as excecao:
        resultado, resposta = ResultadoDoEnvio.FALHA, type(excecao).__name__[:MAIOR_RESPOSTA]
    concluida = agora()
    ordem = envio.automaticas + 1
    numero = TentativaDeEnvioDoPedidoFormal.objects.filter(pedido_formal=pedido).count() + 1
    TentativaDeEnvioDoPedidoFormal.objects.create(
        pedido_formal=pedido,
        numero=numero,
        tipo=TipoDaTentativaDeEnvio.AUTOMATICA,
        ordem_automatica=ordem,
        iniciada_em=iniciada,
        concluida_em=concluida,
        resultado=resultado,
        resposta=resposta,
        destino=destino,
    )
    envio.automaticas = ordem
    if resultado == ResultadoDoEnvio.SUCESSO:
        _concluir(envio, SituacaoDoEnvio.CONCLUIDO_COM_SUCESSO, concluida)
    elif ordem < TENTATIVAS_AUTOMATICAS:
        envio.proxima_tentativa_em = concluida + INTERVALOS[ordem]
        envio.save(update_fields=["automaticas", "proxima_tentativa_em"])
    else:
        _concluir(envio, SituacaoDoEnvio.CONCLUIDO_COM_FALHAS, concluida)
        _avisar_os_administradores(envio)


def _concluir(envio: EnvioDoPedidoFormal, situacao: str, instante: datetime) -> None:
    envio.situacao = situacao
    envio.concluido_em = instante
    envio.proxima_tentativa_em = None
    envio.save(update_fields=["automaticas", "situacao", "concluido_em", "proxima_tentativa_em"])
    _auditar_a_conclusao(envio)


def _auditar_a_conclusao(envio: EnvioDoPedidoFormal) -> None:
    tentativas = TentativaDeEnvioDoPedidoFormal.objects.filter(
        pedido_formal_id=envio.pedido_formal_id
    ).order_by("numero")
    registrar_auditoria(
        SISTEMA,
        "pedido_formal.ciclo_concluido",
        envio.pedido_formal,
        {
            "pedido_formal": envio.pedido_formal_id,
            "estado": envio.situacao,
            "tentativas": [
                {"numero": t.numero, "resultado": t.resultado, "resposta": t.resposta}
                for t in tentativas
            ],
        },
    )


def _avisar_os_administradores(envio: EnvioDoPedidoFormal) -> None:
    """O aviso da terceira falha, na transação dela: um por pedido formal e administrador."""
    pedido = envio.pedido_formal
    administradores = list(
        Conta.objects.filter(papel=Papel.ADMINISTRADOR, situacao=Situacao.ATIVA).order_by("pk")
    )
    if not administradores:
        logger.warning("Falha no pedido formal %s sem aviso: nenhum administrador ativo", pedido.pk)
        return
    frases = [
        f"Tentativa {t.numero} em {no_fuso_da_operacao(t.iniciada_em):%d/%m/%Y %H:%M}: "
        f"{t.resposta}."
        for t in TentativaDeEnvioDoPedidoFormal.objects.filter(pedido_formal=pedido).order_by(
            "numero"
        )
    ]
    corpo = " ".join(
        [
            f"O pedido formal nº {pedido.pk} da rodada {pedido.rodada_id} de "
            f"{pedido.fornecedor.nome} não foi aceito pelo serviço de e-mail depois de "
            f"{TENTATIVAS_AUTOMATICAS} tentativas automáticas.",
            *frases,
            "Use Reenviar pedido na página do pedido formal.",
        ]
    )
    emitir_evento_para_varios(
        Evento.FALHA_NO_PEDIDO_FORMAL,
        administradores,
        titulo=f"Falha no envio do pedido formal: {pedido.fornecedor.nome}"[:150],
        corpo=corpo,
        link=f"/administracao/rodadas/{pedido.rodada_id}/pedido-formal/",
        chave_base=f"falha_no_pedido_formal:{pedido.pk}",
    )
