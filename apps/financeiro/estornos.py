"""O que o comprador vê e recebe sobre os estornos (E10-07): os textos do motivo e do estado, o
aviso `estorno` e a lista de estornos de um pedido.

O comprador nunca vê código de falha, evidência, identificação da transferência nem comprovante.
"""

from decimal import Decimal
from typing import Any

from django.urls import reverse

from apps.catalogo.templatetags.catalogo import reais
from apps.financeiro.models import ObrigacaoComComprador, ParcelaDeDevolucao, SituacaoDaParcela
from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento

TEXTO_DO_MOTIVO = {
    "minimo_nao_atingido": "Mínimo não atingido",
    "caixa_invalidada": "Caixa incompleta",
    "ocorrencia_de_entrega": "Ocorrência na entrega",
    "cancelamento_da_rodada": "Cancelamento da rodada",
    "aprovado_apos_a_margem": "Pagamento aprovado depois do prazo",
    "duplicidade": "Pagamento em duplicidade",
    "iniciado_fora_do_prazo": "Pagamento iniciado fora do prazo",
    "pedido_cancelado": "Pedido cancelado",
    "valor_divergente": "Valor diferente do pedido",
}

S = SituacaoDaParcela
FALHOU = "A plataforma não conseguiu devolver; o administrador fará a devolução diretamente"
TEXTO_DO_ESTADO = {
    "devida": "Estorno registrado, aguardando processamento",
    S.SOLICITADA: "Estorno solicitado à plataforma de pagamento",
    S.FALHA_TEMPORARIA: "Estorno solicitado à plataforma de pagamento",
    S.EM_PROCESSAMENTO: "Estorno em processamento na plataforma de pagamento",
    S.FALHA_DEFINITIVA: FALHOU,
    S.ELEGIVEL_EXCEPCIONAL: FALHOU,
    S.CONCLUIDA: "Estorno concluído pela plataforma de pagamento",
    S.CONCLUIDA_FORA_DA_PLATAFORMA: "Devolução feita pelo administrador por Pix ou transferência",
}
MEIOS = {"pix": "Pix", "transferencia": "transferência"}


def texto_do_motivo(motivo: str) -> str:
    return TEXTO_DO_MOTIVO.get(motivo, "Devolução")


def texto_do_estado(situacao: str) -> str:
    return TEXTO_DO_ESTADO.get(situacao, "Estorno registrado, aguardando processamento")


def _texto_do_aviso(
    parcela: ParcelaDeDevolucao, situacao: str, meio: str | None
) -> tuple[str, str]:
    valor = reais(Decimal(parcela.valor))
    motivo = texto_do_motivo(parcela.obrigacao.motivo)
    if situacao == S.SOLICITADA:
        return (
            "Estorno solicitado",
            f"Solicitamos à plataforma de pagamento a devolução de {valor} ({motivo}).",
        )
    if situacao == S.CONCLUIDA:
        return (
            "Estorno concluído",
            f"A plataforma de pagamento concluiu a devolução de {valor} ({motivo}).",
        )
    if situacao == S.ELEGIVEL_EXCEPCIONAL:
        return (
            "Estorno em andamento",
            f"A plataforma de pagamento não conseguiu devolver {valor} ({motivo}). "
            "O administrador fará a devolução diretamente por Pix ou transferência.",
        )
    return (
        "Devolução realizada",
        f"O administrador devolveu {valor} ({motivo}) por {MEIOS.get(meio or '', 'Pix')}.",
    )


def avisar_o_comprador(
    parcela: ParcelaDeDevolucao, situacao: str, *, meio: str | None = None
) -> None:
    """Emite o aviso `estorno` ao comprador, na transação do fato. Sem comprador (pagamento sem
    pedido), não há aviso. A chave deriva do fato, então a repetição não duplica."""
    obrigacao = parcela.obrigacao
    comprador = obrigacao.comprador
    if comprador is None or obrigacao.pedido_id is None:
        return
    titulo, corpo = _texto_do_aviso(parcela, situacao, meio)
    emitir_evento(
        Evento.ESTORNO,
        comprador,
        titulo=titulo,
        corpo=corpo,
        link=reverse("pedidos_detalhe", kwargs={"pk": obrigacao.pedido_id}),
        chave=f"estorno:{parcela.pk}:{situacao}:{comprador.pk}",
    )


def estornos_do_pedido(pedido: Any) -> list[dict[str, Any]]:
    """Uma linha por obrigação do pedido (inclusive as dos pagamentos que não quitaram), com o
    valor, o motivo e o estado real em texto para o comprador."""
    linhas = []
    obrigacoes = ObrigacaoComComprador.objects.filter(
        pedido=pedido, comprador=pedido.comprador
    ).order_by("pk")
    for obrigacao in obrigacoes:
        parcela = ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).first()
        situacao = "devida" if parcela is None else parcela.situacao
        linhas.append(
            {
                "valor": obrigacao.devido,
                "motivo": texto_do_motivo(obrigacao.motivo),
                "estado": texto_do_estado(situacao),
            }
        )
    return linhas
