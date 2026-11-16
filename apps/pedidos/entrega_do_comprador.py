"""O que o comprador vê, na página do seu pedido, da entrega e da retirada (E14-07).

As seções vêm de `situacao_da_retirada` (E14-05), das ocorrências do pedido (E14-02) e da situação
da devolução (E10). A página só lê: nenhum formulário de falta, troca, substituição, retirada ou
descarte (cenário 50). O nome do administrador não aparece.
"""

from typing import Any

from apps.financeiro.devolucoes import situacao_da_devolucao
from apps.financeiro.models import (
    ObrigacaoComComprador,
    PedidoApurado,
    Reembolso,
    SituacaoDaParcela,
)
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.pedidos.liberacao_da_retirada import liberacao_da_rodada
from apps.pedidos.models import OcorrenciaDeEntrega, Pedido
from apps.pedidos.retirada import situacao_da_retirada
from apps.rodadas.models import Etapa

SEM_VALOR = "Sem valor a devolver"


def _data_hora(instante: Any) -> str:
    return f"{no_fuso_da_operacao(instante):%d/%m/%Y %H:%M}"


def _situacao_da_devolucao(reembolso: Reembolso) -> str:
    """O texto da devolução para o comprador: `Devida` ou o rótulo da parcela; sem obrigação (valor
    zero), "Sem valor a devolver"."""
    obrigacao = ObrigacaoComComprador.objects.filter(
        origem_tipo=Reembolso._meta.label_lower, origem_id=str(reembolso.pk)
    ).first()
    if obrigacao is None:
        return SEM_VALOR
    situacao = situacao_da_devolucao(obrigacao)
    return "Devida" if situacao == "devida" else str(SituacaoDaParcela(situacao).label)


def ocorrencias_do_pedido(pedido: Pedido) -> list[dict[str, Any]]:
    """Uma linha por ocorrência do pedido, da mais antiga para a mais nova."""
    linhas = []
    registros = (
        OcorrenciaDeEntrega.objects.filter(item__pedido=pedido)
        .select_related("item", "reembolso")
        .order_by("pk")
    )
    for ocorrencia in registros:
        situacao = _situacao_da_devolucao(ocorrencia.reembolso)
        linhas.append(
            {
                "quando": _data_hora(ocorrencia.registrada_em),
                "produto": ocorrencia.item.nome,
                "tipo": ocorrencia.get_tipo_display(),
                "quantidade": ocorrencia.quantidade,
                "unidade": ocorrencia.item.unidade,
                "reembolso": None if situacao == SEM_VALOR else ocorrencia.reembolso.total,
                "situacao": situacao,
            }
        )
    return linhas


def retirada_do_pedido(pedido: Pedido) -> dict[str, Any] | None:
    """A seção de retirada: só no pedido válido de rodada `disponivel_para_retirada`."""
    rodada = pedido.abertura.rodada
    if rodada.etapa != Etapa.DISPONIVEL_PARA_RETIRADA:
        return None
    liberacao = liberacao_da_rodada(rodada)
    if liberacao is None:
        return None
    valido = PedidoApurado.objects.filter(
        apuracao__ciclo_id=liberacao.ciclo_id, pedido=pedido
    ).exists()
    if not valido:
        return None
    situacao = situacao_da_retirada(rodada)
    do_pedido = next((p for p in situacao.pedidos if p.pedido == pedido.pk), None)
    if do_pedido is None:
        return None
    itens = [
        {
            "produto": i.produto,
            "pedida": i.pedida,
            "reembolsada": i.reembolsada_na_apuracao + i.em_ocorrencias,
            "retirada": i.retirada,
            "descartada": i.descartada,
            "saldo": i.saldo,
        }
        for i in do_pedido.itens
    ]
    return {
        "liberada_em": _data_hora(liberacao.liberada_em),
        "prazo_final": _data_hora(liberacao.prazo_final),
        "endereco": liberacao.endereco.texto,
        "itens": itens,
        "prazo_encerrado": situacao.prazo_encerrado and any(i.saldo > 0 for i in do_pedido.itens),
    }
