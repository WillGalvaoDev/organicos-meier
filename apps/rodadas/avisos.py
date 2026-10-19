"""Aviso de início do fechamento (E06-02).

Roda dentro da transação de `iniciar_fechamento`: uma falha na emissão desfaz o início. Todos os
destinatários recebem o mesmo conteúdo, então a emissão é em lote (`emitir_evento_para_varios`).
"""

from datetime import datetime

from apps.contas.models import Conta
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.notificacoes.emissao import emitir_evento_para_varios
from apps.notificacoes.eventos import Evento
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.rodadas.models import Ciclo, Rodada

MAIOR_TITULO = 150


def _compradores_com_reserva(rodada: Rodada) -> list[Conta]:
    """Compradores com parcela `ativa` e reserva num produto do estoque da rodada, por id."""
    ids = (
        ParcelaDeInteresse.objects.filter(
            produto__in=rodada.estoques.values("produto_id"),
            situacao=SituacaoParcela.ATIVA,
            quantidade_reservada__gt=0,
        )
        .order_by("comprador_id")
        .values_list("comprador_id", flat=True)
        .distinct()
    )
    return list(Conta.objects.filter(pk__in=list(ids)).order_by("pk"))


def avisar_fechamento_iniciado(rodada: Rodada, ciclo: Ciclo, termina_em: datetime) -> None:
    contas = _compradores_com_reserva(rodada)
    if not contas:
        return
    nome = rodada.fornecedor.nome
    prazo = no_fuso_da_operacao(termina_em)
    corpo = (
        f"A rodada de {nome} entrou na etapa de fechamento. O prazo termina em "
        f"{prazo:%d/%m/%Y} às {prazo:%H:%M} (horário de Brasília). Até lá, você ainda pode "
        "alterar seus interesses, sem precisar confirmar nada. No fim do prazo, as unidades "
        "que não completarem caixa serão removidas."
    )
    emitir_evento_para_varios(
        Evento.FECHAMENTO_INICIADO,
        contas,
        titulo=f"Fechamento iniciado: {nome}"[:MAIOR_TITULO],
        corpo=corpo,
        link="/carrinho/",
        chave_base=f"fechamento_iniciado:{ciclo.pk}",
    )
