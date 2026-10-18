"""Aviso de alteração de preço aos compradores afetados (E05-06).

Roda dentro da transação de `editar_produto`: uma falha na emissão desfaz a alteração do preço.
Os totais e o progresso não são gravados; são calculados na leitura com o preço vigente.
"""

from decimal import Decimal
from typing import Any

from django.db.models import Sum

from apps.catalogo.models import Produto, Unidade
from apps.catalogo.quantidades import calcular_subtotal, formatar_quantidade
from apps.catalogo.templatetags.catalogo import reais
from apps.contas.models import Conta
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento
from apps.nucleo.auditoria import EntradaAuditoria

MAIOR_TITULO = 150


def avisar_preco_alterado(
    sender: Any,
    produto: Produto,
    anterior: Decimal,
    novo: Decimal,
    alteracao: EntradaAuditoria,
    **kwargs: Any,
) -> None:
    """Um aviso por comprador com reserva (parcela `ativa`) do produto, com o impacto dele."""
    afetados = list(
        ParcelaDeInteresse.objects.filter(
            produto_id=produto.pk,
            situacao=SituacaoParcela.ATIVA,
            quantidade_reservada__gt=0,
        )
        .order_by("comprador_id")
        .values("comprador_id")
        .annotate(reservado=Sum("quantidade_reservada"))
    )
    contas = Conta.objects.in_bulk([linha["comprador_id"] for linha in afetados])
    rotulo = Unidade(produto.unidade).label
    for linha in afetados:
        conta = contas[linha["comprador_id"]]
        reservado: Decimal = linha["reservado"]
        corpo = (
            f"O preço de {produto.nome} mudou de {reais(anterior)} para {reais(novo)} "
            f"por {rotulo}. Seu interesse reservado de {formatar_quantidade(reservado)} "
            f"{rotulo} passa de {reais(calcular_subtotal(anterior, reservado))} "
            f"para {reais(calcular_subtotal(novo, reservado))}."
        )
        emitir_evento(
            Evento.PRECO_ALTERADO,
            conta,
            titulo=f"Preço alterado: {produto.nome}"[:MAIOR_TITULO],
            corpo=corpo,
            link="/carrinho/",
            chave=f"preco_alterado:{alteracao.pk}:{conta.pk}",
        )
