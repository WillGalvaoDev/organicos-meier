"""Serviços de produto (E03-03).

Só o administrador cria e edita, também em chamada direta. Preço muda em qualquer etapa; o
múltiplo só na fase de interesse. Unidade, fornecedor e incremento não são editáveis aqui
(o incremento muda por `alterar_incremento`, E03-06).
"""

from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.catalogo.models import Produto, Unidade
from apps.catalogo.quantidades import validar_incremento, validar_multiplo
from apps.catalogo.sinais import preco_alterado
from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.interesses.consultas import quantidades_em_uso
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.valores import (
    MENSAGEM_CAPACIDADE_DINHEIRO,
    ValorInvalido,
    cabe_em_dinheiro,
    dinheiro,
    eh_multiplo,
    ler_decimal_digitado,
)
from apps.rodadas.condicoes import travar_condicoes

PRECO_MINIMO = Decimal("0.01")
CAMPOS_EDITAVEIS = ("nome", "descricao", "preco", "disponivel")


def _exigir_administrador(autor: Conta | None) -> None:
    if getattr(autor, "papel", None) != Papel.ADMINISTRADOR:
        raise PermissionDenied


def _nome(valor: Any) -> str:
    if not isinstance(valor, str) or not (1 <= len(valor.strip()) <= 150):
        raise ValidationError("Informe um nome de 1 a 150 caracteres.")
    return valor.strip()


def _descricao(valor: Any) -> str:
    if valor is None:
        return ""
    if not isinstance(valor, str) or len(valor.strip()) > 2000:
        raise ValidationError("A descrição aceita até 2000 caracteres.")
    return valor.strip()


def _unidade(valor: Any) -> str:
    if valor not in Unidade.values:
        raise ValidationError("Escolha uma unidade de medida válida.")
    return str(valor)


def _preco(valor: Any) -> Decimal:
    try:
        preco = ler_decimal_digitado(valor, 2) if isinstance(valor, str) else dinheiro(valor)
    except ValorInvalido:
        raise ValidationError("Informe um preço em reais, como 7,99.") from None
    if preco < PRECO_MINIMO:
        raise ValidationError("O preço deve ser de pelo menos R$ 0,01.")
    if not cabe_em_dinheiro(preco):
        raise ValidationError(MENSAGEM_CAPACIDADE_DINHEIRO)
    return preco


def _disponivel(valor: Any) -> bool:
    if not isinstance(valor, bool):
        raise ValidationError("Informe se o produto está disponível.")
    return valor


_LIMPEZA = {
    "nome": _nome,
    "descricao": _descricao,
    "unidade": _unidade,
    "preco": _preco,
    "disponivel": _disponivel,
}


def _limpar(campos: dict[str, Any]) -> dict[str, Any]:
    limpos: dict[str, Any] = {}
    erros: dict[str, list[str]] = {}
    for nome, valor in campos.items():
        try:
            limpos[nome] = _LIMPEZA[nome](valor)
        except ValidationError as erro:
            erros[nome] = list(erro.messages)
    if erros:
        raise ValidationError(erros)
    return limpos


def criar_produto(
    autor: Conta,
    fornecedor: Fornecedor,
    *,
    nome: str,
    descricao: str = "",
    unidade: str,
    incremento: Any,
    preco: str | Decimal,
    multiplo: Any = None,
    disponivel: bool = True,
) -> Produto:
    """Cria o produto (em qualquer etapa da rodada) e audita `produto.criar`.

    Recusa de incremento ou múltiplo levanta `IncrementoInvalido`/`MultiploInvalido`; os demais
    campos, `ValidationError` com mensagens por campo.
    """
    _exigir_administrador(autor)
    incremento_valido = validar_incremento(incremento)
    multiplo_valido = validar_multiplo(multiplo, incremento_valido)
    dados = _limpar(
        {
            "nome": nome,
            "descricao": descricao,
            "unidade": unidade,
            "preco": preco,
            "disponivel": disponivel,
        }
    )
    with transaction.atomic():
        produto = Produto.objects.create(
            fornecedor_id=fornecedor.pk,
            incremento=incremento_valido,
            multiplo=multiplo_valido,
            **dados,
        )
        registrar_auditoria(
            autor,
            "produto.criar",
            produto,
            {"produto": produto.pk, "fornecedor": fornecedor.pk},
        )
    return produto


def editar_produto(autor: Conta, produto: Produto, **campos: Any) -> Produto:
    """Edita nome, descrição, preço e disponibilidade, em qualquer etapa.

    A linha é travada e só as colunas alteradas são gravadas. A auditoria lista os nomes dos
    campos; mudança de preço grava também `produto.alterar_preco` e envia `preco_alterado`
    dentro da transação (receptor que falha desfaz a edição).
    """
    _exigir_administrador(autor)
    nao_editaveis = {
        nome: ["Este campo não pode ser editado aqui."]
        for nome in campos
        if nome not in CAMPOS_EDITAVEIS
    }
    if nao_editaveis:
        raise ValidationError(nao_editaveis)
    novos = _limpar(campos)
    with transaction.atomic():
        atual = Produto.objects.select_for_update().get(pk=produto.pk)
        alterados = [
            nome
            for nome in CAMPOS_EDITAVEIS
            if nome in novos and getattr(atual, nome) != novos[nome]
        ]
        if alterados:
            preco_anterior = atual.preco
            for nome in alterados:
                setattr(atual, nome, novos[nome])
            atual.save(update_fields=alterados)
            registrar_auditoria(
                autor, "produto.editar", atual, {"produto": atual.pk, "campos": alterados}
            )
            if "preco" in alterados:
                alteracao = registrar_auditoria(
                    autor,
                    "produto.alterar_preco",
                    atual,
                    {
                        "produto": atual.pk,
                        "anterior": str(preco_anterior),
                        "novo": str(atual.preco),
                    },
                )
                preco_alterado.send(
                    sender=Produto,
                    produto=atual,
                    anterior=preco_anterior,
                    novo=atual.preco,
                    alteracao=alteracao,
                )
    return atual


def alterar_multiplo(autor: Conta, produto: Produto, novo: Any) -> Produto:
    """Altera ou remove (vazio) o múltiplo, só na fase de interesse da rodada do fornecedor.

    Ordem de travas: fornecedor e rodada (`travar_condicoes`), depois o produto. Valor igual ao
    atual não grava nem audita.
    """
    _exigir_administrador(autor)
    with transaction.atomic():
        travar_condicoes(produto.fornecedor)
        atual = Produto.objects.select_for_update().get(pk=produto.pk)
        multiplo = validar_multiplo(novo, atual.incremento)
        if atual.multiplo != multiplo:
            anterior = atual.multiplo
            atual.multiplo = multiplo
            atual.save(update_fields=["multiplo"])
            registrar_auditoria(
                autor,
                "produto.alterar_multiplo",
                atual,
                {
                    "produto": atual.pk,
                    "anterior": None if anterior is None else str(anterior),
                    "novo": None if multiplo is None else str(multiplo),
                },
            )
    return atual


_MENSAGENS_INCOMPATIVEL = {
    "quantidade": (
        "O novo incremento não é compatível com quantidades já registradas deste produto."
    ),
    "multiplo": "O múltiplo do produto não é divisível pelo novo incremento.",
}


class IncrementoIncompativel(Exception):
    """O novo incremento não combina com o que já está registrado.

    `codigo`: `quantidade` (alguma reserva ou pendência deixaria de ser múltipla) ou `multiplo`.
    A mensagem não identifica compradores.
    """

    def __init__(self, codigo: str) -> None:
        super().__init__(_MENSAGENS_INCOMPATIVEL[codigo])
        self.codigo = codigo


def alterar_incremento(autor: Conta, produto: Produto, novo: Any) -> Produto:
    """Altera o incremento, só na fase de interesse e se tudo continuar divisível por ele.

    Ordem de travas: fornecedor e rodada (`travar_condicoes`), produto e parcelas (por
    sequência). As recusas, nesta ordem: fase, valor inválido, quantidades em uso (reservadas e
    pendentes, inclusive as da fila) e múltiplo. Qualquer recusa desfaz a transação inteira.
    """
    _exigir_administrador(autor)
    with transaction.atomic():
        travar_condicoes(produto.fornecedor)
        atual = Produto.objects.select_for_update().get(pk=produto.pk)
        incremento = validar_incremento(novo)
        if atual.incremento == incremento:
            return atual
        em_uso = quantidades_em_uso(atual, travar=True)
        if not all(eh_multiplo(quantidade, incremento) for quantidade in em_uso):
            raise IncrementoIncompativel("quantidade")
        if atual.multiplo is not None and not eh_multiplo(atual.multiplo, incremento):
            raise IncrementoIncompativel("multiplo")
        anterior = atual.incremento
        atual.incremento = incremento
        atual.save(update_fields=["incremento"])
        registrar_auditoria(
            autor,
            "produto.alterar_incremento",
            atual,
            {"produto": atual.pk, "anterior": str(anterior), "novo": str(incremento)},
        )
    return atual
