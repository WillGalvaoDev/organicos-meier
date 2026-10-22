"""Liquidez por destinação e saídas da conta do provedor (E09-07).

O dinheiro no provedor não fica todo disponível ao mesmo tempo, e o saldo da conta é um só. A
liquidez de uma obrigação com fornecedor (ou da receita de serviço) é a parte que vem de
pagamentos já liberados. O repasse e a retirada ficam limitados a essa parte, então o dinheiro
liberado de um fornecedor nunca paga outro (T-11).

    liberado(D)  = max(0, min(saldo(D), E_lib(D) - S(D)))
    a_liberar(D) = saldo(D) - liberado(D)

`E_lib(D)` é o que a apuração transferiu para `D` a partir de pedidos cujo pagamento que quitou
está liberado (`liberado_no_provedor_em` até agora; sem a data, conta como a liberar), e `S(D)` é
tudo que já saiu de `D` por qualquer fluxo.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db.models import Sum

from apps.catalogo.templatetags.catalogo import reais
from apps.contas.models import Conta
from apps.financeiro.alertas import resolver_alerta
from apps.financeiro.livro import (
    EXTERIOR,
    MovimentoInvalido,
    MovimentoProibido,
    Transferencia,
    _travar_conta,
    lancar,
    saldo,
)
from apps.financeiro.models import (
    ContaFinanceira,
    Destinacao,
    MovimentoFinanceiro,
    TipoDeAlerta,
    TipoDeMovimento,
    TransferenciaFinanceira,
)
from apps.financeiro.reserva import (
    _exigir_administrador,
    _exigir_transacao,
    _justificativa,
    _sem_invariante_violado,
    _valor,
)
from apps.nucleo.tempo import agora
from apps.pedidos.models import DestinoDaDecisao, DestinoDoPagamento, Pedido

ZERO = Decimal("0.00")
MAIOR_IDENTIFICACAO = 64


class LiquidezInsuficiente(Exception):
    """O valor passa da parte liberada da conta."""


class SaidaRepetida(Exception):
    """A identificação da saída já foi registrada."""


@dataclass(frozen=True)
class Liquidez:
    liberado: Decimal
    a_liberar: Decimal


# tipo da saída: o movimento, a conta de onde sai e se o limite é o liberado (e não o saldo)
SAIDAS: dict[str, tuple[TipoDeMovimento, Destinacao, bool, bool]] = {
    "repasse": (TipoDeMovimento.REPASSE, Destinacao.OBRIGACAO_FORNECEDOR, True, False),
    "retirada_de_receita": (
        TipoDeMovimento.RETIRADA_DE_RECEITA,
        Destinacao.RECEITA_SERVICO,
        True,
        True,
    ),
    "pagamento_do_frete": (TipoDeMovimento.PAGAMENTO_DO_FRETE, Destinacao.FRETE, False, False),
}


def _liberado_em(custodia: ContaFinanceira) -> datetime | None:
    """Quando o pagamento que quitou o pedido dessa custódia fica liberado; `None` se o
    provedor não informou (ou se o pedido não tem pagamento que quitou)."""
    if custodia.ciclo_id is None or custodia.comprador_id is None:
        return None
    pedido = Pedido.objects.filter(
        abertura__ciclo_id=custodia.ciclo_id, comprador_id=custodia.comprador_id
    ).first()
    if pedido is None:
        return None
    destino = (
        DestinoDoPagamento.objects.filter(pedido=pedido, destino=DestinoDaDecisao.QUITA)
        .select_related("pagamento")
        .first()
    )
    liberado: datetime | None = destino.pagamento.liberado_no_provedor_em if destino else None
    return liberado


def liquidez(conta: ContaFinanceira) -> Liquidez:
    """A parte liberada e a parte a liberar da obrigação com um fornecedor ou da receita."""
    if conta.destinacao not in (Destinacao.OBRIGACAO_FORNECEDOR, Destinacao.RECEITA_SERVICO):
        raise ValueError("só a obrigação com fornecedor e a receita de serviço têm liquidez")
    instante = agora()
    entradas = TransferenciaFinanceira.objects.filter(
        para=conta, movimento__tipo=TipoDeMovimento.APURACAO
    ).select_related("de")
    liberado_pelos_pagamentos = ZERO
    for transferencia in entradas:
        quando = _liberado_em(transferencia.de) if transferencia.de is not None else None
        if quando is not None and quando <= instante:
            liberado_pelos_pagamentos += transferencia.valor
    saiu = TransferenciaFinanceira.objects.filter(de=conta).aggregate(s=Sum("valor"))["s"]
    pode_sair = liberado_pelos_pagamentos - (Decimal(saiu) if saiu is not None else ZERO)
    em_conta = saldo(conta)
    liberado = max(ZERO, min(em_conta, pode_sair))
    return Liquidez(liberado, em_conta - liberado)


def registrar_saida(
    autor: Conta,
    *,
    tipo: str,
    conta: ContaFinanceira,
    valor: Decimal,
    identificacao: str,
    justificativa: str,
) -> MovimentoFinanceiro:
    """Registra uma saída feita fora do sistema (Pix ou transferência a partir da conta do
    provedor): repasse, retirada de receita ou pagamento do frete. O registro não consulta o
    provedor; a conciliação confere. A mesma saída nunca entra duas vezes."""
    _exigir_transacao("registrar_saida")
    _exigir_administrador(autor)
    if tipo not in SAIDAS:
        raise ValueError(f"tipo de saída desconhecido: {tipo!r}")
    movimento_tipo, destinacao, limita_no_liberado, bloqueada = SAIDAS[tipo]
    if conta.destinacao != destinacao:
        raise MovimentoProibido(f"fluxo_nao_permitido: {tipo} não sai de {conta.destinacao}")
    valor = _valor(valor)
    if not isinstance(identificacao, str) or not 1 <= len(identificacao) <= MAIOR_IDENTIFICACAO:
        raise MovimentoInvalido("identificacao")
    justificativa = _justificativa(justificativa)
    if bloqueada:
        _sem_invariante_violado()
    chave = f"saida:{identificacao}"
    _travar_conta(conta.pk)  # o limite é calculado sob a trava: duas saídas não passam juntas
    if MovimentoFinanceiro.objects.filter(chave=chave).exists():
        raise SaidaRepetida(identificacao)
    if limita_no_liberado:
        parte = liquidez(conta)
        if valor > parte.liberado:
            raise LiquidezInsuficiente(
                f"só {reais(parte.liberado)} estão liberados no provedor "
                f"({reais(parte.a_liberar)} a liberar)"
            )
    movimento = lancar(
        tipo=movimento_tipo,
        transferencias=[Transferencia(conta, EXTERIOR, valor)],
        autor=autor,
        justificativa=justificativa,
        origem=conta,
        chave=chave,
    )
    resolver_alerta(
        TipoDeAlerta.DIVERGENCIA_NA_CONCILIACAO, identificacao, motivo="saída registrada no livro"
    )
    return movimento
