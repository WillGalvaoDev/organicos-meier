"""Cadastro e edição de fornecedores (E03-01).

Só o administrador cria e edita, também em chamada direta aos serviços. As mensagens de erro vêm
por campo (`ValidationError` com dicionário). O mínimo monetário é informado no cadastro; a
alteração dele depois só vale na fase de interesse da rodada (`alterar_minimo`, E03-02).
"""

from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.contas.emails import EmailInvalido, normalizar_email
from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.valores import ValorInvalido, dinheiro, ler_decimal_digitado
from apps.rodadas.condicoes import travar_condicoes

MINIMO_DO_MINIMO = Decimal("0.01")
CAMPOS_EDITAVEIS = ("nome", "email_pedido", "prazo_entrega_dias", "informacoes_frete")


def _exigir_administrador(autor: Conta | None) -> None:
    if getattr(autor, "papel", None) != Papel.ADMINISTRADOR:
        raise PermissionDenied


def _nome(valor: Any) -> str:
    if not isinstance(valor, str) or not (1 <= len(valor.strip()) <= 150):
        raise ValidationError("Informe um nome de 1 a 150 caracteres.")
    return valor.strip()


def _email_pedido(valor: Any) -> str:
    try:
        return normalizar_email(valor)
    except EmailInvalido:
        raise ValidationError("Informe um e-mail válido.") from None


def _minimo(valor: Any) -> Decimal:
    try:
        minimo = ler_decimal_digitado(valor, 2) if isinstance(valor, str) else dinheiro(valor)
    except ValorInvalido:
        raise ValidationError("Informe um valor em reais, como 150,00.") from None
    if minimo < MINIMO_DO_MINIMO:
        raise ValidationError("O mínimo deve ser de pelo menos R$ 0,01.")
    return minimo


def _prazo(valor: Any) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or not (1 <= valor <= 365):
        raise ValidationError("Informe um prazo de 1 a 365 dias.")
    return int(valor)


def _frete(valor: Any) -> str:
    if valor is None:
        return ""
    if not isinstance(valor, str) or len(valor.strip()) > 1000:
        raise ValidationError("As informações de frete aceitam até 1000 caracteres.")
    return valor.strip()


_LIMPEZA = {
    "nome": _nome,
    "email_pedido": _email_pedido,
    "minimo": _minimo,
    "prazo_entrega_dias": _prazo,
    "informacoes_frete": _frete,
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


def criar_fornecedor(
    autor: Conta,
    *,
    nome: str,
    email_pedido: str,
    minimo: str | Decimal,
    prazo_entrega_dias: int,
    informacoes_frete: str = "",
) -> Fornecedor:
    """Cria o fornecedor e audita (`fornecedor.criar`, sem dados de contato)."""
    _exigir_administrador(autor)
    dados = _limpar(
        {
            "nome": nome,
            "email_pedido": email_pedido,
            "minimo": minimo,
            "prazo_entrega_dias": prazo_entrega_dias,
            "informacoes_frete": informacoes_frete,
        }
    )
    with transaction.atomic():
        fornecedor = Fornecedor.objects.create(**dados)
        registrar_auditoria(autor, "fornecedor.criar", fornecedor, {"fornecedor": fornecedor.pk})
    return fornecedor


def editar_fornecedor(autor: Conta, fornecedor: Fornecedor, **campos: Any) -> Fornecedor:
    """Edita nome, e-mail do pedido, prazo e frete; o mínimo não é editável aqui (E03-02).

    A linha é relida com `select_for_update` e só as colunas alteradas são gravadas. Edição sem
    mudança não grava auditoria; a auditoria lista os nomes dos campos, nunca os valores.
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
        atual = Fornecedor.objects.select_for_update().get(pk=fornecedor.pk)
        alterados = [
            nome
            for nome in CAMPOS_EDITAVEIS
            if nome in novos and getattr(atual, nome) != novos[nome]
        ]
        if alterados:
            for nome in alterados:
                setattr(atual, nome, novos[nome])
            atual.save(update_fields=alterados)
            registrar_auditoria(
                autor,
                "fornecedor.editar",
                atual,
                {"fornecedor": atual.pk, "campos": alterados},
            )
    return atual


def alterar_minimo(autor: Conta, fornecedor: Fornecedor, novo: str | Decimal) -> Fornecedor:
    """Altera o mínimo do fornecedor, só enquanto a rodada ativa está em `interesse`.

    Valida o valor como no cadastro e, dentro da transação, trava fornecedor e rodada
    (`travar_condicoes`) antes de reler e gravar, então uma mudança de etapa confirmada antes
    é sempre vista. Valor igual ao atual não grava nem audita.
    """
    _exigir_administrador(autor)
    minimo = _limpar({"minimo": novo})["minimo"]
    with transaction.atomic():
        travar_condicoes(fornecedor)
        atual = Fornecedor.objects.select_for_update().get(pk=fornecedor.pk)
        if atual.minimo != minimo:
            anterior = atual.minimo
            atual.minimo = minimo
            atual.save(update_fields=["minimo"])
            registrar_auditoria(
                autor,
                "fornecedor.alterar_minimo",
                atual,
                {"fornecedor": atual.pk, "anterior": str(anterior), "novo": str(minimo)},
            )
    return atual
