"""Estoque por rodada (E03-05).

Só o administrador inclui produtos e altera o limite, e só na fase de interesse da rodada ativa.
Ordem de travas (a mesma da reserva, na E05): fornecedor, rodada, produto, estoque, parcelas
(por sequência). O limite nunca fica abaixo do total reservado.
"""

from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.transaction import TransactionManagementError

from apps.catalogo.models import Produto
from apps.catalogo.quantidades import formatar_quantidade
from apps.contas.models import Conta, Papel
from apps.interesses.consultas import total_reservado
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.valores import (
    MENSAGEM_CAPACIDADE_QUANTIDADE,
    ValorInvalido,
    cabe_em_quantidade,
    quantidade,
)
from apps.rodadas.condicoes import CondicoesCongeladas, travar_condicoes
from apps.rodadas.models import EstoqueDaRodada, Rodada
from apps.rodadas.sinais import estoque_alterado

_ZERO = Decimal("0.000")


class EstoqueAbaixoDoReservado(Exception):
    """O novo limite ficaria abaixo da quantidade já reservada."""


def _exigir_administrador(autor: Conta | None) -> None:
    if getattr(autor, "papel", None) != Papel.ADMINISTRADOR:
        raise PermissionDenied


def _limite(valor: Any) -> Decimal | None:
    """Vazio significa sem limite; zero é aceito; negativo e `float` são recusados."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    try:
        limite = quantidade(valor)
    except ValorInvalido:
        raise ValidationError(
            "Informe o limite com até três casas decimais, ou deixe vazio para sem limite."
        ) from None
    if limite < 0:
        raise ValidationError("O limite do estoque não pode ser negativo.")
    if not cabe_em_quantidade(limite):
        raise ValidationError(MENSAGEM_CAPACIDADE_QUANTIDADE)
    return limite


def _texto(limite: Decimal | None) -> str | None:
    return None if limite is None else str(limite)


def travar_estoque(rodada: Rodada, produto: Produto) -> EstoqueDaRodada:
    """Trava o produto e depois o estoque dele na rodada (continuação da ordem de travas).

    Quem chama já travou fornecedor e rodada (`travar_condicoes`). Exige transação aberta.
    """
    if not connection.in_atomic_block:
        raise TransactionManagementError("travar_estoque exige uma transação aberta.")
    Produto.objects.select_for_update().get(pk=produto.pk)
    return EstoqueDaRodada.objects.select_for_update().get(
        rodada_id=rodada.pk, produto_id=produto.pk
    )


def calcular_livre(limite: Decimal | None, reservado: Decimal) -> Decimal | None:
    """Limite menos o reservado, com piso 0; `None` quando não há limite."""
    if limite is None:
        return None
    livre: Decimal = limite - reservado
    return max(livre, _ZERO)


def estoque_livre(estoque: EstoqueDaRodada) -> Decimal | None:
    """Limite menos o total reservado, com piso 0; `None` quando não há limite."""
    return calcular_livre(estoque.limite, total_reservado(estoque.produto))


def incluir_produto_na_rodada(
    autor: Conta, rodada: Rodada, produto: Produto, limite: Any
) -> EstoqueDaRodada:
    """Inclui o produto na rodada ativa, em interesse, com o limite (vazio = sem limite)."""
    _exigir_administrador(autor)
    if produto.fornecedor_id != rodada.fornecedor_id:
        raise ValidationError("O produto é de outro fornecedor.")
    with transaction.atomic():
        travada = travar_condicoes(produto.fornecedor)
        if travada.pk != rodada.pk:
            raise CondicoesCongeladas("fora_de_interesse")
        Produto.objects.select_for_update().get(pk=produto.pk)
        valor = _limite(limite)
        if EstoqueDaRodada.objects.filter(rodada_id=rodada.pk, produto_id=produto.pk).exists():
            raise ValidationError("Este produto já está na rodada.")
        estoque = EstoqueDaRodada.objects.create(
            rodada_id=rodada.pk, produto_id=produto.pk, limite=valor
        )
        registrar_auditoria(
            autor,
            "estoque.incluir",
            estoque,
            {"rodada": rodada.pk, "produto": produto.pk, "limite": _texto(valor)},
        )
        estoque_alterado.send(
            sender=EstoqueDaRodada, estoque=estoque, anterior=Decimal("0"), novo=valor
        )
    return estoque


def alterar_estoque(autor: Conta, estoque: EstoqueDaRodada, novo_limite: Any) -> EstoqueDaRodada:
    """Altera o limite (vazio = sem limite), sem ficar abaixo do total reservado.

    Recusa se a rodada do estoque não for a rodada ativa em interesse. Valor igual ao atual não
    grava, não audita e não envia o sinal.
    """
    _exigir_administrador(autor)
    with transaction.atomic():
        produto = estoque.produto
        travada = travar_condicoes(produto.fornecedor)
        if travada.pk != estoque.rodada_id:
            raise CondicoesCongeladas("fora_de_interesse")
        atual = travar_estoque(travada, produto)
        novo = _limite(novo_limite)
        if atual.limite == novo:
            return atual
        reservado = total_reservado(produto, travar=True)
        if novo is not None and novo < reservado:
            raise EstoqueAbaixoDoReservado(
                "O estoque não pode ficar abaixo da quantidade já reservada "
                f"({formatar_quantidade(reservado)})."
            )
        anterior = atual.limite
        atual.limite = novo
        atual.save(update_fields=["limite"])
        registrar_auditoria(
            autor,
            "estoque.alterar",
            atual,
            {
                "estoque": atual.pk,
                "rodada": atual.rodada_id,
                "produto": atual.produto_id,
                "anterior": _texto(anterior),
                "novo": _texto(novo),
            },
        )
        estoque_alterado.send(sender=EstoqueDaRodada, estoque=atual, anterior=anterior, novo=novo)
    return atual
