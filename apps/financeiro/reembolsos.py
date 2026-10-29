"""Cálculo do reembolso (E10-02): parcial por item, serviço e frete proporcionais, integral.

Todo reembolso de parte de um pedido pago passa por aqui. Os valores vêm do que ficou registrado no
pedido congelado (nunca do catálogo), em `Decimal` exato, com `ROUND_HALF_UP` nos centavos. O
acumulado de cada item e do pedido é lido dos registros `Reembolso` e `ItemReembolsado`, que só
aceitam inserção: não há campo de acumulado que possa divergir. Cada reembolso com valor gera, na
mesma transação, a obrigação com o comprador (E09-06).
"""

from decimal import Decimal
from typing import NamedTuple

from django.db.models import Sum

from apps.contas.models import Conta
from apps.financeiro.models import (
    ItemReembolsado,
    MotivoDoReembolso,
    ObrigacaoComComprador,
    Reembolso,
)
from apps.financeiro.obrigacoes import registrar_obrigacao_com_comprador
from apps.financeiro.reserva import _exigir_transacao, sem_cobertura_da_obrigacao
from apps.nucleo.auditoria import SISTEMA, _Sistema
from apps.nucleo.valores import arredondar_centavos, eh_multiplo
from apps.pedidos.models import ItemDoPedido, Pedido, SituacaoDePagamento, SituacaoDoPedido

ZERO = Decimal("0.00")
ZERO_QUANTIDADE = Decimal("0.000")
MAIOR_CHAVE = 64


class ReembolsoRecusado(Exception):
    """O reembolso não pode ser calculado; a mensagem diz o motivo."""


class ReembolsoConflitante(Exception):
    """A chave já existe com outro conteúdo."""


class ReembolsoRegistrado(NamedTuple):
    reembolso: Reembolso
    obrigacao: ObrigacaoComComprador | None
    sem_cobertura: Decimal


Linha = tuple[ItemDoPedido, Decimal, Decimal]  # (item, quantidade, valor)


# --- acumulados, lidos dos registros ---------------------------------------------------------


def acumulado_do_item(item: ItemDoPedido) -> tuple[Decimal, Decimal]:
    """A quantidade e o valor já reembolsados do item, somando todos os reembolsos registrados."""
    soma = ItemReembolsado.objects.filter(item=item).aggregate(q=Sum("quantidade"), v=Sum("valor"))
    return Decimal(soma["q"] or ZERO_QUANTIDADE), Decimal(soma["v"] or ZERO)


def acumulado_do_pedido(pedido: Pedido) -> tuple[Decimal, Decimal, Decimal]:
    """Os produtos, o serviço e o frete já reembolsados do pedido."""
    soma = Reembolso.objects.filter(pedido=pedido).aggregate(
        p=Sum("produtos"), s=Sum("servico"), f=Sum("frete")
    )
    return Decimal(soma["p"] or ZERO), Decimal(soma["s"] or ZERO), Decimal(soma["f"] or ZERO)


# --- validação e idempotência ----------------------------------------------------------------


def _validar(chave: str, motivo: str, autor: Conta | _Sistema) -> Conta | None:
    if not isinstance(chave, str) or not chave.strip() or len(chave) > MAIOR_CHAVE:
        raise ValueError(f"a chave deve ter de 1 a {MAIOR_CHAVE} caracteres")
    if motivo not in MotivoDoReembolso.values:
        raise ValueError(f"motivo de reembolso desconhecido: {motivo!r}")
    if autor is SISTEMA:
        return None
    if isinstance(autor, Conta) and autor.pk is not None:
        return autor
    raise ValueError("autor inválido: informe uma conta salva ou SISTEMA")


def _exigir_pedido_pago(pedido: Pedido) -> None:
    estado = SituacaoDoPedido.objects.get(pedido=pedido)
    if estado.situacao != SituacaoDePagamento.PAGO:
        raise ReembolsoRecusado("o pedido não está pago")


def _existente(
    chave: str, pedido: Pedido, motivo: str, linhas: set[tuple[int, Decimal]] | None
) -> ReembolsoRegistrado | None:
    """O reembolso já gravado com essa chave, se o conteúdo é o mesmo; conteúdo diferente é
    conflito. `linhas` (item, quantidade) só é conferido no parcial: a integral recalcula o
    restante, que depois de feita é vazio."""
    reembolso = Reembolso.objects.filter(chave=chave).first()
    if reembolso is None:
        return None
    mesmas = linhas is None or linhas == {
        (linha.item_id, linha.quantidade) for linha in reembolso.itens.all()
    }
    if reembolso.pedido_id != pedido.pk or reembolso.motivo != motivo or not mesmas:
        raise ReembolsoConflitante(f"a chave {chave!r} já existe com outro conteúdo")
    obrigacao = ObrigacaoComComprador.objects.filter(
        origem_tipo=Reembolso._meta.label_lower, origem_id=str(reembolso.pk)
    ).first()
    sem_cobertura = sem_cobertura_da_obrigacao(obrigacao) if obrigacao is not None else ZERO
    return ReembolsoRegistrado(reembolso, obrigacao, sem_cobertura)


# --- gravação ----------------------------------------------------------------------------------


def _gravar(
    pedido: Pedido,
    *,
    chave: str,
    motivo: str,
    autor: Conta | None,
    linhas: list[Linha],
    servico: Decimal,
    frete: Decimal,
) -> ReembolsoRegistrado:
    produtos = sum((valor for _, _, valor in linhas), ZERO)
    reembolso = Reembolso.objects.create(
        pedido=pedido,
        chave=chave,
        motivo=motivo,
        produtos=produtos,
        servico=servico,
        frete=frete,
        autor=autor,
    )
    for item, quantidade, valor in linhas:
        ItemReembolsado.objects.create(
            reembolso=reembolso, item=item, quantidade=quantidade, valor=valor
        )
    if produtos + servico + frete <= 0:
        return ReembolsoRegistrado(reembolso, None, ZERO)
    registrada = registrar_obrigacao_com_comprador(
        origem=reembolso,
        rodada=pedido.abertura.rodada,
        ciclo=pedido.abertura.ciclo,
        comprador=pedido.comprador,
        pedido=pedido,
        motivo=motivo,
        produtos=produtos,
        servico=servico,
        frete=frete,
    )
    return ReembolsoRegistrado(reembolso, registrada.obrigacao, registrada.sem_cobertura)


# --- as duas operações ------------------------------------------------------------------------


def reembolso_parcial(
    item: ItemDoPedido, quantidade: Decimal, *, chave: str, motivo: str, autor: Conta | _Sistema
) -> ReembolsoRegistrado:
    """Devolve `quantidade` do item: produtos proporcionais ao subtotal, serviço e frete
    proporcionais aos produtos devolvidos. A última parcela de cada componente é o saldo exato."""
    _exigir_transacao("reembolso_parcial")
    autor_conta = _validar(chave, motivo, autor)
    pedido = item.pedido
    existente = _existente(chave, pedido, motivo, {(item.pk, quantidade)})
    if existente is not None:
        return existente
    _exigir_pedido_pago(pedido)
    if (
        not isinstance(quantidade, Decimal)
        or not quantidade.is_finite()
        or quantidade <= 0
        or quantidade.as_tuple().exponent < -3  # type: ignore[operator]
        or not eh_multiplo(quantidade, item.incremento)
    ):
        raise ReembolsoRecusado("quantidade inválida")
    ja_quantidade, ja_valor = acumulado_do_item(item)
    if ja_quantidade + quantidade > item.quantidade:
        raise ReembolsoRecusado("passa da quantidade paga")
    if ja_quantidade + quantidade == item.quantidade:
        valor = item.subtotal - ja_valor
    else:
        valor = min(
            arredondar_centavos(item.subtotal * quantidade / item.quantidade),
            item.subtotal - ja_valor,
        )
    ja_produtos, ja_servico, ja_frete = acumulado_do_pedido(pedido)
    if ja_produtos + valor == pedido.produtos:
        servico = pedido.servico - ja_servico
        frete = pedido.frete - ja_frete
    else:
        servico = min(
            arredondar_centavos(pedido.servico * valor / pedido.produtos),
            pedido.servico - ja_servico,
        )
        frete = min(
            arredondar_centavos(pedido.frete * valor / pedido.produtos), pedido.frete - ja_frete
        )
    return _gravar(
        pedido,
        chave=chave,
        motivo=motivo,
        autor=autor_conta,
        linhas=[(item, quantidade, valor)],
        servico=servico,
        frete=frete,
    )


def reembolso_integral_do_pedido(
    pedido: Pedido, *, chave: str, motivo: str, autor: Conta | _Sistema
) -> ReembolsoRegistrado | None:
    """Devolve tudo o que ainda não foi devolvido do pedido, item por item e componente por
    componente. Sem nada restante, não grava nada e devolve `None`."""
    _exigir_transacao("reembolso_integral_do_pedido")
    autor_conta = _validar(chave, motivo, autor)
    existente = _existente(chave, pedido, motivo, None)
    if existente is not None:
        return existente
    _exigir_pedido_pago(pedido)
    linhas: list[Linha] = []
    for item in pedido.itens.order_by("pk"):
        ja_quantidade, ja_valor = acumulado_do_item(item)
        if ja_quantidade < item.quantidade:
            linhas.append((item, item.quantidade - ja_quantidade, item.subtotal - ja_valor))
    _, ja_servico, ja_frete = acumulado_do_pedido(pedido)
    servico = pedido.servico - ja_servico
    frete = pedido.frete - ja_frete
    if not linhas and servico + frete <= 0:
        return None
    return _gravar(
        pedido,
        chave=chave,
        motivo=motivo,
        autor=autor_conta,
        linhas=linhas,
        servico=servico,
        frete=frete,
    )
