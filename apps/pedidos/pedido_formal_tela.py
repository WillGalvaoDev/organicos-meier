"""O que as telas do administrador mostram do pedido formal (E13-04): o pedido consolidado, o
envio e as tentativas, e o bloco da página da rodada. Tudo vem do `PedidoFormal`, das linhas e das
tentativas gravados, nunca recalculado."""

import uuid
from typing import Any

from apps.nucleo.tempo import no_fuso_da_operacao
from apps.pedidos.models import (
    EnvioDoPedidoFormal,
    PedidoFormal,
    SituacaoDoEnvio,
    TentativaDeEnvioDoPedidoFormal,
    TipoDaTentativaDeEnvio,
)
from apps.pedidos.reenvio_do_pedido_formal import pode_reenviar
from apps.rodadas.models import Rodada

TENTATIVAS_AUTOMATICAS = 3
NOTA_DA_ENTREGA = "A aceitação pelo serviço de e-mail não comprova a entrega ao fornecedor."


def _data_hora(instante: Any) -> str:
    return f"{no_fuso_da_operacao(instante):%d/%m/%Y %H:%M}"


def texto_do_envio(envio: EnvioDoPedidoFormal) -> str:
    """A situação do ciclo automático, em uma frase."""
    if envio.situacao == SituacaoDoEnvio.EM_ANDAMENTO and envio.proxima_tentativa_em is not None:
        return (
            f"Envio automático em andamento: tentativa {envio.automaticas + 1} de "
            f"{TENTATIVAS_AUTOMATICAS} prevista para {_data_hora(envio.proxima_tentativa_em)}."
        )
    if envio.situacao == SituacaoDoEnvio.CONCLUIDO_COM_SUCESSO:
        return "Envio automático concluído: aceito pelo serviço de e-mail."
    if envio.situacao == SituacaoDoEnvio.CONCLUIDO_COM_FALHAS:
        return (
            f"Envio automático concluído sem sucesso depois de {TENTATIVAS_AUTOMATICAS} tentativas."
        )
    return "Envio interrompido: a rodada foi cancelada."


def _tentativas(pedido_formal: PedidoFormal) -> list[dict[str, Any]]:
    tentativas = TentativaDeEnvioDoPedidoFormal.objects.filter(
        pedido_formal=pedido_formal
    ).select_related("autor")
    return [
        {
            "numero": t.numero,
            "tipo": (
                f"Automática {t.ordem_automatica}/{TENTATIVAS_AUTOMATICAS}"
                if t.tipo == TipoDaTentativaDeEnvio.AUTOMATICA
                else "Manual"
            ),
            "inicio": _data_hora(t.iniciada_em),
            "resultado": t.get_resultado_display(),
            "resposta": t.resposta,
            "destino": t.destino,
            "autor": t.autor.nome if t.autor is not None else "",
        }
        for t in tentativas.order_by("numero")
    ]


def pagina_do_pedido_formal(pedido_formal: PedidoFormal) -> dict[str, Any]:
    """O contexto da página do pedido formal. O token do formulário é novo a cada carregamento."""
    envio = EnvioDoPedidoFormal.objects.get(pedido_formal=pedido_formal)
    pode, mensagem = pode_reenviar(pedido_formal)
    return {
        "pedido_formal": pedido_formal,
        "rodada": pedido_formal.rodada,
        "fornecedor": pedido_formal.fornecedor,
        "emitido_em": _data_hora(pedido_formal.emitido_em),
        "linhas": list(pedido_formal.linhas.order_by("nome", "produto_id")),
        "situacao_do_envio": texto_do_envio(envio),
        "nota_da_entrega": NOTA_DA_ENTREGA,
        "tentativas": _tentativas(pedido_formal),
        "pode_reenviar": pode,
        "mensagem_do_reenvio": mensagem,
        "token": uuid.uuid4(),
    }


def bloco_do_pedido_formal(rodada: Rodada) -> dict[str, Any] | None:
    """O bloco da página da rodada: o número, o total e a situação do envio, com o link."""
    pedido = PedidoFormal.objects.filter(rodada=rodada).first()
    if pedido is None:
        return None
    envio = EnvioDoPedidoFormal.objects.get(pedido_formal=pedido)
    return {
        "numero": pedido.pk,
        "total": pedido.total_produtos,
        "situacao": texto_do_envio(envio),
    }
