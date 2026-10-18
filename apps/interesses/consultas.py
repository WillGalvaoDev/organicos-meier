"""Leituras das parcelas de um produto (E03-04).

Com `travar=True` (dentro de `transaction.atomic()`), as linhas lidas são travadas com
`FOR UPDATE`, em ordem de `sequencia`: é a forma de a E03-05 e a E03-06 decidirem sobre o
estoque e o incremento sem corrida com as operações de interesse.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import QuerySet, Sum

from apps.catalogo.models import Produto
from apps.catalogo.quantidades import calcular_subtotal
from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.interesses.progresso import ProgressoDoProduto, progresso_da_rodada
from apps.rodadas.models import ETAPAS_ATIVAS, Etapa, Rodada

_ZERO = Decimal("0.000")
SITUACOES_QUE_RESERVAM = (SituacaoParcela.ATIVA, SituacaoParcela.EM_PEDIDO)


def _parcelas(produto: Produto, travar: bool) -> QuerySet[ParcelaDeInteresse]:
    parcelas = ParcelaDeInteresse.objects.filter(produto_id=produto.pk).order_by("sequencia")
    return parcelas.select_for_update() if travar else parcelas


def total_reservado(produto: Produto, *, travar: bool = False) -> Decimal:
    """Soma da reserva das parcelas `ativa` ou `em_pedido` do produto (a que o estoque cobre)."""
    parcelas = _parcelas(produto, travar).filter(situacao__in=SITUACOES_QUE_RESERVAM)
    if travar:
        total = sum(parcelas.values_list("quantidade_reservada", flat=True), _ZERO)
    else:
        total = parcelas.order_by().aggregate(total=Sum("quantidade_reservada"))["total"] or _ZERO
    return total.quantize(_ZERO)


def quantidades_em_uso(produto: Produto, *, travar: bool = False) -> list[Decimal]:
    """Reservas e pendências maiores que zero das parcelas do produto que não foram removidas."""
    parcelas = _parcelas(produto, travar).exclude(situacao=SituacaoParcela.REMOVIDA)
    em_uso: list[Decimal] = []
    for reservada, pendente in parcelas.values_list("quantidade_reservada", "quantidade_pendente"):
        em_uso.extend(quantidade for quantidade in (reservada, pendente) if quantidade > 0)
    return em_uso


def travar_parcelas(produto: Produto) -> list[ParcelaDeInteresse]:
    """Trava, por sequência, todas as parcelas do produto que não foram removidas.

    Cobre as `ativa`, `em_pedido` e `pendente`: toda parcela que uma operação de interesse lê
    para decidir ou altera. Exige transação aberta (o `FOR UPDATE` do Django já a exige).
    """
    return list(_parcelas(produto, True).exclude(situacao=SituacaoParcela.REMOVIDA))


@dataclass(frozen=True)
class LinhaDoCarrinho:
    """Uma linha por produto em que o comprador tem reservado ou pendente (E05-05)."""

    produto: Produto
    reservado: Decimal
    pendente: Decimal
    subtotal: Decimal
    no_estoque: bool
    caixas: ProgressoDoProduto | None


@dataclass(frozen=True)
class GrupoDoCarrinho:
    fornecedor: Fornecedor
    rodada: Rodada | None
    percentual: int
    atingido: bool
    editavel: bool
    linhas: list[LinhaDoCarrinho]
    total_reservado: Decimal


def carrinho_do_comprador(comprador: Conta) -> list[GrupoDoCarrinho]:
    """Grupos por fornecedor com as parcelas `ativa` e `pendente` do comprador.

    Número de leituras: fixo mais uma constante por fornecedor (o progresso da rodada dele).
    Nunca devolve dados de outros compradores nem o mínimo ou os valores elegíveis em reais.
    """
    parcelas = list(
        ParcelaDeInteresse.objects.filter(
            comprador_id=comprador.pk,
            situacao__in=(SituacaoParcela.ATIVA, SituacaoParcela.PENDENTE),
        ).select_related("produto__fornecedor")
    )
    por_produto: dict[int, list[ParcelaDeInteresse]] = {}
    for parcela in parcelas:
        por_produto.setdefault(parcela.produto_id, []).append(parcela)
    fornecedores: dict[int, Fornecedor] = {}
    produtos_por_fornecedor: dict[int, list[Produto]] = {}
    for lista in por_produto.values():
        produto = lista[0].produto
        fornecedores[produto.fornecedor_id] = produto.fornecedor
        produtos_por_fornecedor.setdefault(produto.fornecedor_id, []).append(produto)
    rodadas = {
        r.fornecedor_id: r
        for r in Rodada.objects.filter(
            fornecedor_id__in=list(fornecedores), etapa__in=ETAPAS_ATIVAS
        ).select_related("fornecedor")
    }
    grupos: list[GrupoDoCarrinho] = []
    for fornecedor_id in sorted(fornecedores, key=lambda i: (fornecedores[i].nome, i)):
        rodada = rodadas.get(fornecedor_id)
        progresso = progresso_da_rodada(rodada, comprador) if rodada is not None else None
        caixas = {p.produto.pk: p for p in progresso.produtos} if progresso else {}
        linhas = []
        for produto in sorted(produtos_por_fornecedor[fornecedor_id], key=lambda p: (p.nome, p.pk)):
            lista = por_produto[produto.pk]
            reservado = sum(
                (p.quantidade_reservada for p in lista if p.situacao == SituacaoParcela.ATIVA),
                _ZERO,
            ).quantize(_ZERO)
            pendente = sum((p.quantidade_pendente for p in lista), _ZERO).quantize(_ZERO)
            if reservado == 0 and pendente == 0:
                continue
            no_estoque = produto.pk in caixas
            linhas.append(
                LinhaDoCarrinho(
                    produto=produto,
                    reservado=reservado,
                    pendente=pendente,
                    subtotal=calcular_subtotal(produto.preco, reservado),
                    no_estoque=no_estoque,
                    caixas=caixas.get(produto.pk) if produto.multiplo is not None else None,
                )
            )
        grupos.append(
            GrupoDoCarrinho(
                fornecedor=fornecedores[fornecedor_id],
                rodada=rodada,
                percentual=progresso.percentual if progresso else 0,
                atingido=progresso.atingido if progresso else False,
                editavel=rodada is not None and rodada.etapa in (Etapa.INTERESSE, Etapa.FECHAMENTO),
                linhas=linhas,
                total_reservado=sum((x.subtotal for x in linhas), Decimal("0.00")),
            )
        )
    return [g for g in grupos if g.linhas]
