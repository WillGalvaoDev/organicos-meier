"""Aviso de início do fechamento (E06-02).

Roda dentro da transação de `iniciar_fechamento`: uma falha na emissão desfaz o início. Todos os
destinatários recebem o mesmo conteúdo, então a emissão é em lote (`emitir_evento_para_varios`).
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from apps.catalogo.models import Produto, Unidade
from apps.catalogo.quantidades import formatar_quantidade
from apps.contas.models import Conta
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.notificacoes.emissao import emitir_evento, emitir_evento_para_varios
from apps.notificacoes.eventos import Evento
from apps.nucleo.tempo import no_fuso_da_operacao
from apps.rodadas.models import Ciclo, Rodada

MAIOR_TITULO = 150


def compradores_com_reserva(rodada: Rodada) -> list[Conta]:
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
    contas = compradores_com_reserva(rodada)
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


@dataclass(frozen=True)
class ExcedenteRemovido:
    """O que saiu do interesse de um comprador num produto no fim do fechamento."""

    comprador_id: int
    produto: Produto
    removida: Decimal
    mantida: Decimal
    parcela_id: int | None = None  # só nas saídas por parcela


def avisar_excedentes_removidos(
    rodada: Rodada, ciclo: Ciclo, remocoes: list[ExcedenteRemovido]
) -> None:
    """Um aviso por par (comprador, produto) com quantidade removida (E06-05). Mesma transação."""
    contas = Conta.objects.in_bulk([r.comprador_id for r in remocoes])
    fornecedor = rodada.fornecedor.nome
    for remocao in remocoes:
        produto = remocao.produto
        rotulo = Unidade(produto.unidade).label
        corpo = (
            f"No fim do fechamento da rodada de {fornecedor}, "
            f"{formatar_quantidade(remocao.removida)} {rotulo} de {produto.nome} não completaram "
            "caixa e foram removidas do seu interesse. Continuam no seu interesse: "
            f"{formatar_quantidade(remocao.mantida)} {rotulo}."
        )
        emitir_evento(
            Evento.EXCEDENTES_REMOVIDOS,
            contas[remocao.comprador_id],
            titulo=f"Excedentes removidos: {produto.nome}"[:MAIOR_TITULO],
            corpo=corpo,
            link="/carrinho/",
            chave=f"excedentes_removidos:{ciclo.pk}:{produto.pk}:{remocao.comprador_id}",
        )


def avisar_retorno_para_interesse(rodada: Rodada, ciclo: Ciclo, contas: list[Conta]) -> None:
    """Aviso `retorno_para_interesse` por mínimo não atingido (E06-06), igual para todos.

    O mínimo do fornecedor nunca aparece para o comprador. Sem destinatários, nada é emitido.
    """
    if not contas:
        return
    nome = rodada.fornecedor.nome
    corpo = (
        f"A rodada de {nome} voltou para a fase de interesse porque o mínimo do fornecedor não "
        "foi atingido no fim do fechamento. Os interesses que continuam reservados seguem na "
        "rodada, e você pode alterá-los. Nada foi cobrado neste ciclo, então não há estornos."
    )
    emitir_evento_para_varios(
        Evento.RETORNO_PARA_INTERESSE,
        contas,
        titulo=f"Rodada de volta ao interesse: {nome}"[:MAIOR_TITULO],
        corpo=corpo,
        link="/carrinho/",
        chave_base=f"retorno_para_interesse:{ciclo.pk}",
    )
