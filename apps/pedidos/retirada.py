"""A retirada por item e o descarte manual (E14-05).

Liberada a retirada, o administrador registra o que cada comprador retirou, por item e quantidade,
em momentos diferentes. Passados os sete dias da liberação, o que restou aparece como pendente de
decisão (`vencidos`, calculado na leitura) e só uma ação do administrador registra o descarte: a
passagem do tempo nunca grava nada (cenário 23). Nenhum dos dois move dinheiro.

Travas, nesta ordem: a rodada (`FOR NO KEY UPDATE`, a trava de todas as operações da E14) e a
situação do pedido, como a ocorrência, que divide o saldo do item com a retirada e o descarte.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Sum

from apps.catalogo.quantidades import formatar_quantidade
from apps.contas.models import Conta, Papel, Situacao
from apps.financeiro.models import ItemReembolsado, MotivoDoReembolso, PedidoApurado
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao
from apps.nucleo.valores import ValorInvalido, cabe_em_quantidade, eh_multiplo, quantidade
from apps.pedidos.liberacao_da_retirada import liberacao_da_rodada
from apps.pedidos.models import (
    DescarteDeItem,
    ItemDoPedido,
    LiberacaoDaRetirada,
    Pedido,
    RetiradaDeItem,
    SituacaoDoPedido,
)
from apps.pedidos.ocorrencias import saldo_do_item
from apps.rodadas.models import Etapa, Rodada

__all__ = [
    "DescarteRegistrado",
    "ItemDaRetirada",
    "PedidoDaRetirada",
    "RetiradaRecusada",
    "RetiradaRegistrada",
    "SituacaoDaRetirada",
    "registrar_descarte",
    "registrar_retirada",
    "situacao_da_retirada",
]

ZERO = Decimal("0")
MENSAGENS = {
    "acionamento_invalido": (
        "O registro não pôde ser identificado; recarregue a página e tente de novo."
    ),
    "etapa": "A retirada só é registrada depois da liberação.",
    "item_fora_do_pedido_formal": "Este item não está entre os pedidos válidos da rodada.",
    "quantidade_invalida": "Informe uma quantidade maior que zero, no incremento do produto.",
    "passa_do_saldo_do_item": "A quantidade passa do saldo deste item ({saldo} {unidade}).",
    "antes_do_prazo": (
        "O descarte só pode ser registrado a partir de {quando} (horário de Brasília)."
    ),
}


class RetiradaRecusada(Exception):
    """A retirada ou o descarte não pode ser registrado. `codigo` diz o motivo."""

    def __init__(self, codigo: str, **valores: str) -> None:
        self.codigo = codigo
        super().__init__(MENSAGENS[codigo].format(**valores))


@dataclass(frozen=True)
class RetiradaRegistrada:
    """O registro do acionamento. `novo` é falso quando ele já tinha gerado a retirada."""

    registro: RetiradaDeItem
    novo: bool


@dataclass(frozen=True)
class DescarteRegistrado:
    """O registro do acionamento. `novo` é falso quando ele já tinha gerado o descarte."""

    registro: DescarteDeItem
    novo: bool


@dataclass(frozen=True)
class ItemDaRetirada:
    pedido: int
    comprador: str
    item: int
    produto: str
    unidade: str
    pedida: Decimal
    reembolsada_na_apuracao: Decimal
    em_ocorrencias: Decimal
    retirada: Decimal
    descartada: Decimal
    saldo: Decimal


@dataclass(frozen=True)
class PedidoDaRetirada:
    pedido: int
    comprador: str
    itens: list[ItemDaRetirada]


@dataclass(frozen=True)
class SituacaoDaRetirada:
    liberacao: LiberacaoDaRetirada
    prazo_encerrado: bool
    pedidos: list[PedidoDaRetirada]
    vencidos: list[ItemDaRetirada]


# --- o registro ---------------------------------------------------------------------------------


def _como_uuid(acionamento: object) -> uuid.UUID:
    if isinstance(acionamento, uuid.UUID):
        return acionamento
    if isinstance(acionamento, str) and acionamento:
        try:
            return uuid.UUID(acionamento)
        except ValueError:
            pass
    raise RetiradaRecusada("acionamento_invalido")


def _repeticao(
    modelo: type[RetiradaDeItem] | type[DescarteDeItem],
    chave: uuid.UUID,
    item: ItemDoPedido,
    quantidade_pedida: object,
) -> Any:
    existente = modelo.objects.filter(acionamento=chave).first()
    if existente is None:
        return None
    igual = (
        existente.item_id == item.pk
        and isinstance(quantidade_pedida, Decimal)
        and existente.quantidade == quantidade_pedida
    )
    if not igual:
        raise RetiradaRecusada("acionamento_invalido")
    return existente


def _quantidade_valida(valor: object, incremento: Decimal) -> bool:
    if not isinstance(valor, Decimal) or not valor.is_finite() or valor <= 0:
        return False
    try:
        return (
            quantidade(valor) == valor
            and cabe_em_quantidade(valor)
            and eh_multiplo(valor, incremento)
        )
    except ValorInvalido:
        return False


def _registrar(
    modelo: type[RetiradaDeItem] | type[DescarteDeItem],
    acao: str,
    autor: Conta | None,
    item: ItemDoPedido,
    quantidade_pedida: object,
    acionamento: object,
    *,
    descarte: bool,
) -> tuple[Any, bool]:
    if autor is None or autor.papel != Papel.ADMINISTRADOR or autor.situacao != Situacao.ATIVA:
        raise PermissionDenied
    chave = _como_uuid(acionamento)
    existente = _repeticao(modelo, chave, item, quantidade_pedida)
    if existente is not None:
        return existente, False
    try:
        with transaction.atomic():
            return _gravar(modelo, acao, autor, item, quantidade_pedida, chave, descarte), True
    except IntegrityError:
        existente = _repeticao(modelo, chave, item, quantidade_pedida)
        if existente is None:
            raise
        return existente, False


def _gravar(
    modelo: type[RetiradaDeItem] | type[DescarteDeItem],
    acao: str,
    autor: Conta,
    item: ItemDoPedido,
    quantidade_pedida: object,
    chave: uuid.UUID,
    descarte: bool,
) -> Any:
    atual = ItemDoPedido.objects.select_related("pedido__abertura").get(pk=item.pk)
    pedido = atual.pedido
    travada = Rodada.objects.select_for_update(no_key=True).get(pk=pedido.abertura.rodada_id)
    SituacaoDoPedido.objects.select_for_update().get(pedido=pedido)
    existente = _repeticao(modelo, chave, atual, quantidade_pedida)
    if existente is not None:
        return existente
    liberacao = liberacao_da_rodada(travada)
    if travada.etapa != Etapa.DISPONIVEL_PARA_RETIRADA or liberacao is None:
        raise RetiradaRecusada("etapa")
    valido = PedidoApurado.objects.filter(
        apuracao__ciclo_id=liberacao.ciclo_id, pedido=pedido
    ).exists()
    if not valido:
        raise RetiradaRecusada("item_fora_do_pedido_formal")
    if not isinstance(quantidade_pedida, Decimal) or not _quantidade_valida(
        quantidade_pedida, atual.incremento
    ):
        raise RetiradaRecusada("quantidade_invalida")
    saldo = saldo_do_item(atual)
    if quantidade_pedida > saldo:
        raise RetiradaRecusada(
            "passa_do_saldo_do_item", saldo=formatar_quantidade(saldo), unidade=atual.unidade
        )
    instante = agora()
    if descarte and instante < liberacao.prazo_final:
        quando = f"{no_fuso_da_operacao(liberacao.prazo_final):%d/%m/%Y %H:%M}"
        raise RetiradaRecusada("antes_do_prazo", quando=quando)
    registro = modelo.objects.create(
        item=atual,
        quantidade=quantidade_pedida,
        autor=autor,
        registrada_em=instante,
        acionamento=chave,
    )
    registrar_auditoria(
        autor,
        acao,
        registro,
        {
            "pedido": pedido.pk,
            "item": atual.pk,
            "quantidade": quantidade_pedida,
            "saldo": saldo - quantidade_pedida,
            "acionamento": str(chave),
        },
    )
    return registro


def registrar_retirada(
    autor: Conta | None, item: ItemDoPedido, quantidade_retirada: object, *, acionamento: object
) -> RetiradaRegistrada:
    """Registra a retirada de parte do item. Só o administrador ativo (`PermissionDenied`). Vale
    enquanto houver saldo, também depois do prazo (cenário 22), e não depende da situação do
    comprador (cenário 19)."""
    registro, novo = _registrar(
        RetiradaDeItem,
        "retirada.registrar",
        autor,
        item,
        quantidade_retirada,
        acionamento,
        descarte=False,
    )
    return RetiradaRegistrada(registro, novo)


def registrar_descarte(
    autor: Conta | None, item: ItemDoPedido, quantidade_descartada: object, *, acionamento: object
) -> DescarteRegistrado:
    """Registra o descarte de parte do saldo do item, a partir do `prazo_final` da liberação
    (inclusive). Nenhuma regra gera devolução a partir dele (§11)."""
    registro, novo = _registrar(
        DescarteDeItem,
        "descarte.registrar",
        autor,
        item,
        quantidade_descartada,
        acionamento,
        descarte=True,
    )
    return DescarteRegistrado(registro, novo)


# --- a leitura ----------------------------------------------------------------------------------


def _soma(modelo: type[RetiradaDeItem] | type[DescarteDeItem], item: ItemDoPedido) -> Decimal:
    total: Decimal | None = modelo.objects.filter(item=item).aggregate(total=Sum("quantidade"))[
        "total"
    ]
    return total or ZERO


def _reembolsada(item: ItemDoPedido, *, ocorrencia: bool) -> Decimal:
    ocorrencias = ItemReembolsado.objects.filter(
        item=item, reembolso__motivo=MotivoDoReembolso.OCORRENCIA_DE_ENTREGA
    )
    outros = ItemReembolsado.objects.filter(item=item).exclude(
        reembolso__motivo=MotivoDoReembolso.OCORRENCIA_DE_ENTREGA
    )
    total: Decimal | None = (ocorrencias if ocorrencia else outros).aggregate(
        total=Sum("quantidade")
    )["total"]
    return total or ZERO


def situacao_da_retirada(rodada: Rodada) -> SituacaoDaRetirada:
    """A situação da retirada da rodada liberada, por pedido válido e por item, sem trava. Os
    `vencidos` são os itens com saldo depois do prazo final: calculados na leitura, nada é
    gravado (cenário 23)."""
    liberacao = liberacao_da_rodada(rodada)
    if liberacao is None:
        raise LookupError("a retirada desta rodada não foi liberada")
    prazo_encerrado = agora() >= liberacao.prazo_final
    validos = PedidoApurado.objects.filter(apuracao__ciclo_id=liberacao.ciclo_id).values(
        "pedido_id"
    )
    pedidos: list[PedidoDaRetirada] = []
    vencidos: list[ItemDaRetirada] = []
    for pedido in Pedido.objects.filter(pk__in=validos).select_related("comprador").order_by("pk"):
        itens: list[ItemDaRetirada] = []
        for item in pedido.itens.order_by("pk"):
            linha = ItemDaRetirada(
                pedido=pedido.pk,
                comprador=pedido.comprador.nome,
                item=item.pk,
                produto=item.nome,
                unidade=item.unidade,
                pedida=item.quantidade,
                reembolsada_na_apuracao=_reembolsada(item, ocorrencia=False),
                em_ocorrencias=_reembolsada(item, ocorrencia=True),
                retirada=_soma(RetiradaDeItem, item),
                descartada=_soma(DescarteDeItem, item),
                saldo=saldo_do_item(item),
            )
            itens.append(linha)
            if prazo_encerrado and linha.saldo > 0:
                vencidos.append(linha)
        pedidos.append(PedidoDaRetirada(pedido.pk, pedido.comprador.nome, itens))
    return SituacaoDaRetirada(liberacao, prazo_encerrado, pedidos, vencidos)
