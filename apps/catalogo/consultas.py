"""Consultas do catálogo do comprador (E03-08).

Só leitura. Mostra os produtos que estão no estoque da rodada ativa do fornecedor, com o estoque
livre calculado em lote (sem consulta por produto). Nunca devolve dados de compradores nem os
campos internos do fornecedor.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Exists, OuterRef, Sum

from apps.catalogo.models import Produto
from apps.fornecedores.models import Fornecedor
from apps.interesses.consultas import SITUACOES_QUE_RESERVAM
from apps.interesses.models import ParcelaDeInteresse
from apps.rodadas.estoque import calcular_livre
from apps.rodadas.models import ETAPAS_ATIVAS, EstoqueDaRodada, Rodada

_ZERO = Decimal("0.000")


@dataclass(frozen=True)
class ItemDoCatalogo:
    produto: Produto
    estoque: EstoqueDaRodada
    livre: Decimal | None


def fornecedores_no_catalogo() -> list[Rodada]:
    """Rodadas ativas com pelo menos um produto incluído, por nome do fornecedor."""
    com_produto = EstoqueDaRodada.objects.filter(rodada_id=OuterRef("pk"))
    return list(
        Rodada.objects.filter(etapa__in=ETAPAS_ATIVAS)
        .filter(Exists(com_produto))
        .select_related("fornecedor")
        .order_by("fornecedor__nome", "fornecedor_id")
    )


def rodada_ativa_do_catalogo(fornecedor_id: int) -> Rodada | None:
    return (
        Rodada.objects.filter(fornecedor_id=fornecedor_id, etapa__in=ETAPAS_ATIVAS)
        .select_related("fornecedor")
        .first()
    )


def produtos_da_rodada(rodada: Rodada) -> list[ItemDoCatalogo]:
    estoques = list(
        EstoqueDaRodada.objects.filter(rodada_id=rodada.pk)
        .select_related("produto")
        .order_by("produto__nome", "produto_id")
    )
    reservados = dict(
        ParcelaDeInteresse.objects.filter(
            produto_id__in=[e.produto_id for e in estoques],
            situacao__in=SITUACOES_QUE_RESERVAM,
        )
        .order_by()
        .values("produto_id")
        .annotate(total=Sum("quantidade_reservada"))
        .values_list("produto_id", "total")
    )
    return [
        ItemDoCatalogo(
            produto=estoque.produto,
            estoque=estoque,
            livre=calcular_livre(estoque.limite, reservados.get(estoque.produto_id, _ZERO)),
        )
        for estoque in estoques
    ]


def produtos_do_catalogo(fornecedor: Fornecedor) -> list[ItemDoCatalogo]:
    """Produtos do estoque da rodada ativa do fornecedor; vazio se não há rodada ativa."""
    rodada = rodada_ativa_do_catalogo(fornecedor.pk)
    return [] if rodada is None else produtos_da_rodada(rodada)
