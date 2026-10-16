"""Condições registradas por ciclo (E03-07).

No instante em que a rodada sai de `interesse`, os valores vigentes de mínimo, incremento,
múltiplo e limite de estoque são gravados num ciclo que só aceita inserção. A E06 chama
`registrar_condicoes_do_ciclo` e grava `etapa = fechamento` na mesma transação, com as mesmas
travas: nenhuma alteração de condição cabe entre o registro e o congelamento.
"""

from django.db.models import Max

from apps.catalogo.models import Produto
from apps.fornecedores.models import Fornecedor
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.rodadas.condicoes import CondicoesCongeladas, travar_condicoes
from apps.rodadas.models import Ciclo, CondicaoDoProdutoNoCiclo, EstoqueDaRodada, Rodada


def registrar_condicoes_do_ciclo(rodada: Rodada) -> Ciclo:
    """Cria o próximo ciclo da rodada com as condições vigentes. Exige transação aberta.

    Só vale para a rodada ativa em `interesse` (`CondicoesCongeladas` caso contrário, inclusive
    numa segunda chamada depois do fechamento). Ordem de travas: fornecedor, rodada, produtos
    da rodada (por id) e estoques (por id).
    """
    travada = travar_condicoes(Fornecedor(pk=rodada.fornecedor_id))
    if travada.pk != rodada.pk:
        raise CondicoesCongeladas("fora_de_interesse")
    fornecedor = Fornecedor.objects.get(pk=travada.fornecedor_id)
    estoques = list(EstoqueDaRodada.objects.filter(rodada_id=travada.pk).order_by("produto_id"))
    produtos = {
        produto.pk: produto
        for produto in Produto.objects.select_for_update()
        .filter(pk__in=[e.produto_id for e in estoques])
        .order_by("pk")
    }
    estoques = list(
        EstoqueDaRodada.objects.select_for_update()
        .filter(rodada_id=travada.pk)
        .order_by("produto_id")
    )
    maior = Ciclo.objects.filter(rodada_id=travada.pk).aggregate(maior=Max("numero"))["maior"]
    ciclo = Ciclo.objects.create(
        rodada_id=travada.pk, numero=(maior or 0) + 1, minimo=fornecedor.minimo
    )
    CondicaoDoProdutoNoCiclo.objects.bulk_create(
        [
            CondicaoDoProdutoNoCiclo(
                ciclo=ciclo,
                produto_id=estoque.produto_id,
                incremento=produtos[estoque.produto_id].incremento,
                multiplo=produtos[estoque.produto_id].multiplo,
                limite_estoque=estoque.limite,
            )
            for estoque in estoques
        ]
    )
    registrar_auditoria(
        SISTEMA,
        "ciclo.registrar_condicoes",
        ciclo,
        {"rodada": travada.pk, "ciclo": ciclo.pk, "numero": ciclo.numero},
    )
    return ciclo


def ciclo_vigente(rodada: Rodada) -> Ciclo | None:
    """O ciclo de maior número da rodada, ou `None` se ela nunca entrou em fechamento."""
    return Ciclo.objects.filter(rodada_id=rodada.pk).order_by("-numero").first()
