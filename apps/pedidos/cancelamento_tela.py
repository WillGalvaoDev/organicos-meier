"""O que as telas mostram do cancelamento da rodada (E12-06): o bloco da página da rodada, para o
administrador, e o aviso no pedido, para o comprador. A fonte é o `CancelamentoDaRodada` e os
reembolsos dele, nunca outro comprador."""

from typing import Any

from apps.financeiro.models import (
    MotivoDoReembolso,
    ObrigacaoComComprador,
    ParcelaDeDevolucao,
    Reembolso,
)
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.pedidos.acompanhamento import situacao_dos_pedidos
from apps.pedidos.models import (
    AberturaDoPagamento,
    CancelamentoDaRodada,
    Pedido,
    SituacaoDePagamento,
)
from apps.rodadas.models import ETAPAS_ATIVAS, Etapa, Rodada

MOTIVO = MotivoDoReembolso.CANCELAMENTO_DA_RODADA


def _momento(instante: Any) -> str:
    return f"{no_fuso_da_operacao(instante):%d/%m/%Y às %H:%M}"


def _devolucoes_do_cancelamento(rodada: Rodada) -> list[dict[str, Any]]:
    obrigacoes = (
        ObrigacaoComComprador.objects.filter(motivo=MOTIVO, pedido__abertura__rodada_id=rodada.pk)
        .select_related("comprador", "pedido")
        .order_by("pk")
    )
    linhas = []
    for obrigacao in obrigacoes:
        parcela = ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).first()
        linhas.append(
            {
                "obrigacao": obrigacao.pk,
                "pedido": obrigacao.pedido_id,
                "comprador": obrigacao.comprador.nome if obrigacao.comprador else "-",
                "valor": obrigacao.devido,
                "situacao": "devida" if parcela is None else parcela.situacao,
            }
        )
    return linhas


def bloco_do_cancelamento(rodada: Rodada) -> dict[str, Any] | None:
    """O bloco da página da rodada: o formulário, se ela ainda pode ser cancelada, ou o registro
    do cancelamento, com os pedidos e as devoluções dele."""
    if rodada.etapa == Etapa.CANCELADA:
        registro = (
            CancelamentoDaRodada.objects.select_related("autor").filter(rodada=rodada).first()
        )
        if registro is None:
            return None
        abertura = (
            AberturaDoPagamento.objects.filter(rodada=rodada).order_by("-ciclo__numero").first()
        )
        return {
            "cancelada": True,
            "em": _momento(registro.cancelada_em),
            "por": registro.autor.nome,
            "com_reembolso": registro.com_reembolso,
            "mensagem": registro.mensagem,
            "pedidos": situacao_dos_pedidos(abertura) if abertura is not None else [],
            "devolucoes": _devolucoes_do_cancelamento(rodada) if registro.com_reembolso else [],
        }
    if rodada.etapa in ETAPAS_ATIVAS:
        return {"cancelavel": True}
    return None


def aviso_no_pedido(pedido: Pedido) -> dict[str, Any] | None:
    """O que o comprador lê no pedido de uma rodada cancelada, só do pedido dele."""
    registro = CancelamentoDaRodada.objects.filter(rodada_id=pedido.abertura.rodada_id).first()
    if registro is None:
        return None
    frases = []
    if pedido.estado.situacao == SituacaoDePagamento.PAGO:
        frases.append("A rodada foi cancelada pelo administrador.")
        reembolsado = Reembolso.objects.filter(pedido=pedido, motivo=MOTIVO).exists()
        if reembolsado:
            frases[0] += " O valor será devolvido integralmente."
        elif not registro.com_reembolso:
            frases.append("O cancelamento não inicia novas devoluções.")
    return {"frases": frases, "mensagem": registro.mensagem}
