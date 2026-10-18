"""Atendimento da fila de pendentes (E05-02).

Pendentes são unidades de um comprador que esperam estoque, sem reserva. A rotina é uma só e roda
sempre que há estoque a alocar: antes de uma reserva nova, depois de uma liberação e quando o
estoque aumenta. A fila é atendida pela sequência original da parcela (FIFO), por produto, e só
com o estoque da rodada ativa do próprio fornecedor.
"""

from decimal import Decimal

from django.db import connection
from django.db.transaction import TransactionManagementError

from apps.catalogo.models import Produto
from apps.fornecedores.models import Fornecedor
from apps.interesses.consultas import SITUACOES_QUE_RESERVAM, travar_parcelas
from apps.interesses.models import SituacaoParcela
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria
from apps.rodadas.condicoes import InteressesBloqueados, travar_rodada_para_interesses
from apps.rodadas.estoque import calcular_livre, travar_estoque
from apps.rodadas.models import EstoqueDaRodada, Rodada

_ZERO = Decimal("0.000")
SITUACOES_NA_FILA = (SituacaoParcela.ATIVA, SituacaoParcela.PENDENTE)


def alocar_pendentes(fornecedor: Fornecedor) -> Decimal:
    """Atende a fila de todos os produtos da rodada ativa e devolve o total alocado.

    Exige transação aberta. Fora de `interesse` e `fechamento`, ou sem rodada ativa, não faz nada
    e devolve zero: a recusa não é erro de quem chamou.
    """
    if not connection.in_atomic_block:
        raise TransactionManagementError("alocar_pendentes exige uma transação aberta.")
    try:
        rodada = travar_rodada_para_interesses(fornecedor)
    except InteressesBloqueados:
        return _ZERO
    total = _ZERO
    estoques = EstoqueDaRodada.objects.filter(rodada_id=rodada.pk).order_by("produto_id")
    for estoque in estoques.select_related("produto"):
        total += _alocar_produto(rodada, estoque.produto)
    return total


def _alocar_produto(rodada: Rodada, produto: Produto) -> Decimal:
    """Atende a fila de um produto. Quem chama já travou o fornecedor e a rodada, e a rodada
    aceita reservas. O produto precisa ter estoque nela."""
    estoque = travar_estoque(rodada, produto)
    atual = Produto.objects.get(pk=produto.pk)
    parcelas = travar_parcelas(atual)
    reservado = sum(
        (p.quantidade_reservada for p in parcelas if p.situacao in SITUACOES_QUE_RESERVAM), _ZERO
    )
    livre = calcular_livre(estoque.limite, reservado)
    alocadas: list[list[object]] = []
    total = _ZERO
    for parcela in parcelas:
        if parcela.situacao not in SITUACOES_NA_FILA or parcela.quantidade_pendente <= 0:
            continue
        if livre is None:
            quantidade = parcela.quantidade_pendente
        else:
            cabe = (livre // atual.incremento) * atual.incremento
            quantidade = min(parcela.quantidade_pendente, cabe)
        if quantidade <= 0:
            if livre is not None and livre <= 0:
                break
            continue
        parcela.quantidade_reservada += quantidade
        parcela.quantidade_pendente -= quantidade
        parcela.situacao = SituacaoParcela.ATIVA
        parcela.save(update_fields=["quantidade_reservada", "quantidade_pendente", "situacao"])
        alocadas.append([parcela.pk, str(quantidade)])
        total += quantidade
        if livre is not None:
            livre -= quantidade
    if alocadas:
        registrar_auditoria(
            SISTEMA,
            "interesse.alocar_pendentes",
            atual,
            {"produto": atual.pk, "rodada": rodada.pk, "parcelas": alocadas},
        )
    return total.quantize(_ZERO)
