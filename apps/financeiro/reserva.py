"""Reserva financeira: aportes, designações e utilização (E09-05).

A reserva é capital próprio do administrador (A1, P-3). O aporte entra na conta `reserva`. Para
uma obrigação com comprador, o administrador designa dinheiro da reserva: nenhum movimento, o
saldo continua o mesmo, o comprometido aumenta e o livre diminui. Para uma despesa pendente, a
utilização é imediata (um movimento da reserva para a despesa). Nada ultrapassa o livre, nada
recompõe a reserva sozinho (P-4), e com o invariante violado nem a designação nem a utilização
passam.

Ordem das travas: a conta `reserva` primeiro, para calcular o livre; depois o alvo.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import QuerySet, Sum
from django.db.transaction import TransactionManagementError

from apps.contas.models import Conta, Papel, Situacao
from apps.financeiro.alertas import abrir_alerta, resolver_alerta
from apps.financeiro.livro import (
    EXTERIOR,
    MovimentoInvalido,
    Transferencia,
    conta,
    conta_da_obrigacao,
    lancar,
    saldo,
    travar_contas,
)
from apps.financeiro.models import (
    AlertaFinanceiro,
    ContaFinanceira,
    DesignacaoDaReserva,
    DesignacaoDesfeita,
    Despesa,
    Destinacao,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    TipoDeAlerta,
    TipoDeDespesa,
    TipoDeMovimento,
    TransferenciaFinanceira,
)
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.valores import ValorInvalido, dinheiro

ZERO = Decimal("0.00")
MAIOR_IDENTIFICACAO = 64
ORIGEM_DA_DESPESA = "financeiro.despesa"
ORIGEM_DA_DESIGNACAO = "financeiro.designacaodareserva"


class ReservaInsuficiente(Exception):
    """O valor passa do saldo livre da reserva."""


class CoberturaExcedente(Exception):
    """O valor passa do que falta cobrir no alvo."""


class AporteRepetido(Exception):
    """A identificação do depósito já foi registrada."""


class DesignacaoEncerrada(Exception):
    """A designação já foi desfeita ou consumida."""


class InvarianteViolado(Exception):
    """Há um alerta de invariante violado aberto: a reserva não pode ser usada."""


@dataclass(frozen=True)
class SituacaoDaReserva:
    saldo: Decimal
    comprometido: Decimal
    livre: Decimal


@dataclass(frozen=True)
class ItemSemCobertura:
    tipo: str  # "obrigacao" ou "despesa"
    objeto_id: int
    valor: Decimal


# --- cálculos (só leitura) ---------------------------------------------------------------------


def _soma(consulta: "QuerySet[Any]") -> Decimal:
    total = consulta.aggregate(s=Sum("valor"))["s"]
    return Decimal(total) if total is not None else ZERO


def consumido_da_designacao(designacao: DesignacaoDaReserva) -> Decimal:
    """O quanto da designação a liquidação já consumiu: os movimentos que a citam."""
    return _soma(
        TransferenciaFinanceira.objects.filter(
            movimento__tipo=TipoDeMovimento.FINANCIAMENTO_DE_OBRIGACAO,
            movimento__origem_tipo=ORIGEM_DA_DESIGNACAO,
            movimento__origem_id=str(designacao.pk),
        )
    )


def _restante_das_designacoes(designacoes: "QuerySet[DesignacaoDaReserva]") -> Decimal:
    """O que ainda está designado: o valor de cada designação menos o que já foi consumido."""
    return sum((Decimal(d.valor) - consumido_da_designacao(d) for d in designacoes), ZERO)


def situacao_da_reserva() -> SituacaoDaReserva:
    """Saldo da reserva, o que está comprometido em designações ativas e o que sobra (livre)."""
    em_caixa = saldo(conta(Destinacao.RESERVA))
    comprometido = _restante_das_designacoes(
        DesignacaoDaReserva.objects.filter(desfeita__isnull=True)
    )
    return SituacaoDaReserva(em_caixa, comprometido, em_caixa - comprometido)


def _financiado(obrigacao: ObrigacaoComComprador) -> Decimal:
    """Tudo o que já entrou na conta da obrigação (o saldo mais o que já foi devolvido)."""
    destino = ContaFinanceira.objects.filter(
        destinacao=Destinacao.OBRIGACAO_COMPRADOR, chave=f"o{obrigacao.pk}"
    ).first()
    if destino is None:
        return ZERO
    return _soma(TransferenciaFinanceira.objects.filter(para=destino))


def _designado(obrigacao: ObrigacaoComComprador) -> Decimal:
    return _restante_das_designacoes(
        DesignacaoDaReserva.objects.filter(obrigacao=obrigacao, desfeita__isnull=True)
    )


def sem_cobertura_da_obrigacao(obrigacao: ObrigacaoComComprador) -> Decimal:
    """O devido menos o financiado menos o designado, nunca abaixo de zero."""
    return max(ZERO, obrigacao.devido - _financiado(obrigacao) - _designado(obrigacao))


def pendente_da_despesa(despesa: Despesa) -> Decimal:
    """O valor da despesa menos o que os movimentos de cobertura dela já cobriram."""
    coberto = _soma(
        TransferenciaFinanceira.objects.filter(
            movimento__tipo=TipoDeMovimento.COBERTURA_DE_DESPESA,
            movimento__origem_tipo=ORIGEM_DA_DESPESA,
            movimento__origem_id=str(despesa.pk),
        )
    )
    return max(ZERO, Decimal(despesa.valor) - coberto)


def itens_sem_cobertura() -> list[ItemSemCobertura]:
    """As obrigações com comprador sem cobertura e as despesas pendentes, em ordem de criação."""
    itens: list[ItemSemCobertura] = []
    for obrigacao in ObrigacaoComComprador.objects.order_by("pk"):
        falta = sem_cobertura_da_obrigacao(obrigacao)
        if falta > 0:
            itens.append(ItemSemCobertura("obrigacao", obrigacao.pk, falta))
    for despesa in Despesa.objects.order_by("pk"):
        falta = pendente_da_despesa(despesa)
        if falta > 0:
            itens.append(ItemSemCobertura("despesa", despesa.pk, falta))
    return itens


def obrigacoes_sem_cobertura() -> Decimal:
    return sum((item.valor for item in itens_sem_cobertura()), ZERO)


def avaliar_reserva() -> None:
    """Abre o alerta `reserva_insuficiente` enquanto as obrigações sem cobertura passam do saldo
    livre, e o resolve quando deixam de passar. Roda no fim de cada operação, na mesma transação."""
    sem_cobertura = obrigacoes_sem_cobertura()
    livre = situacao_da_reserva().livre
    if sem_cobertura > livre:
        abrir_alerta(
            TipoDeAlerta.RESERVA_INSUFICIENTE,
            "geral",
            {"sem_cobertura": sem_cobertura, "livre": livre},
        )
    else:
        resolver_alerta(TipoDeAlerta.RESERVA_INSUFICIENTE, "geral", motivo="cobertura")


# --- validações ----------------------------------------------------------------------------------


def _exigir_transacao(operacao: str) -> None:
    if not connection.in_atomic_block:
        raise TransactionManagementError(f"{operacao} exige uma transação aberta.")


def _exigir_administrador(autor: object) -> Conta:
    if (
        not isinstance(autor, Conta)
        or autor.pk is None
        or autor.papel != Papel.ADMINISTRADOR
        or autor.situacao != Situacao.ATIVA
    ):
        raise PermissionDenied("só o administrador mexe na reserva")
    return autor


def _valor(valor: object) -> Decimal:
    if not isinstance(valor, Decimal):
        raise MovimentoInvalido("valor")
    try:
        convertido = dinheiro(valor)
    except ValorInvalido:
        raise MovimentoInvalido("valor") from None
    if convertido <= 0:
        raise MovimentoInvalido("valor")
    return convertido


def _justificativa(texto: str) -> str:
    if not isinstance(texto, str) or not texto.strip():
        raise MovimentoInvalido("justificativa")
    return texto


def _sem_invariante_violado() -> None:
    if AlertaFinanceiro.objects.filter(
        tipo=TipoDeAlerta.INVARIANTE_VIOLADO, resolvido_em__isnull=True
    ).exists():
        raise InvarianteViolado("invariante violado: a reserva não pode ser usada")


def _travar_a_reserva(*outras: ContaFinanceira) -> ContaFinanceira:
    """Trava a reserva e as `outras` contas de que a decisão depende, de uma vez e em ordem
    crescente de `pk` (regra única de travas). Calcula-se o livre e decide-se só depois disso."""
    caixa = conta(Destinacao.RESERVA)
    travar_contas(caixa, *outras)
    return caixa


def _destino_da_despesa(despesa: Despesa) -> ContaFinanceira:
    """A conta que todas as fontes da cobertura travam: `despesas_a_cobrir` para a tarifa e
    `frete(r)` para o déficit de frete."""
    if despesa.tipo == TipoDeDespesa.TARIFA:
        return conta(Destinacao.DESPESAS_A_COBRIR)
    return conta(Destinacao.FRETE, rodada=despesa.rodada_id)


def _exigir_livre(valor: Decimal) -> None:
    livre = situacao_da_reserva().livre
    if valor > livre:
        raise ReservaInsuficiente(f"o valor passa do saldo livre da reserva ({livre})")


# --- operações ---------------------------------------------------------------------------------


def registrar_aporte(
    autor: Conta, valor: Decimal, identificacao: str, justificativa: str
) -> MovimentoFinanceiro:
    """O administrador depositou na conta do provedor e informa a identificação do depósito. O
    registro não consulta o provedor (L-9): a conciliação confere. O mesmo depósito nunca entra
    duas vezes."""
    _exigir_transacao("registrar_aporte")
    _exigir_administrador(autor)
    valor = _valor(valor)
    if not isinstance(identificacao, str) or not 1 <= len(identificacao) <= MAIOR_IDENTIFICACAO:
        raise MovimentoInvalido("identificacao")
    justificativa = _justificativa(justificativa)
    caixa = _travar_a_reserva()
    chave = f"aporte:{identificacao}"
    if MovimentoFinanceiro.objects.filter(chave=chave).exists():
        raise AporteRepetido(identificacao)
    movimento = lancar(
        tipo=TipoDeMovimento.APORTE,
        transferencias=[Transferencia(EXTERIOR, caixa, valor)],
        autor=autor,
        justificativa=justificativa,
        origem=caixa,
        chave=chave,
    )
    resolver_alerta(
        TipoDeAlerta.DIVERGENCIA_NA_CONCILIACAO, identificacao, motivo="aporte registrado no livro"
    )
    avaliar_reserva()
    return movimento


def designar_reserva(
    autor: Conta, obrigacao: ObrigacaoComComprador, valor: Decimal, justificativa: str
) -> DesignacaoDaReserva:
    """Separa dinheiro da reserva para uma obrigação com comprador, sem mover nada."""
    _exigir_transacao("designar_reserva")
    _exigir_administrador(autor)
    valor = _valor(valor)
    justificativa = _justificativa(justificativa)
    _travar_a_reserva(conta_da_obrigacao(obrigacao))
    _sem_invariante_violado()
    _exigir_livre(valor)
    if valor > sem_cobertura_da_obrigacao(obrigacao):
        raise CoberturaExcedente("o valor passa do que falta cobrir na obrigação")
    designacao = DesignacaoDaReserva.objects.create(
        obrigacao=obrigacao, valor=valor, autor_id=str(autor.pk), justificativa=justificativa
    )
    registrar_auditoria(
        autor,
        "financeiro.designacao",
        designacao,
        {"obrigacao": obrigacao.pk, "valor": valor},
        motivo=justificativa,
    )
    avaliar_reserva()
    return designacao


def desfazer_designacao(autor: Conta, designacao: DesignacaoDaReserva, justificativa: str) -> None:
    """Devolve o dinheiro designado ao livre. Uma designação só se desfaz uma vez."""
    _exigir_transacao("desfazer_designacao")
    _exigir_administrador(autor)
    justificativa = _justificativa(justificativa)
    _travar_a_reserva()
    if (
        DesignacaoDesfeita.objects.filter(designacao=designacao).exists()
        or consumido_da_designacao(designacao) >= designacao.valor
    ):
        raise DesignacaoEncerrada(f"a designação {designacao.pk} já foi desfeita ou consumida")
    DesignacaoDesfeita.objects.create(
        designacao=designacao, autor_id=str(autor.pk), justificativa=justificativa
    )
    registrar_auditoria(
        autor,
        "financeiro.designacao_desfeita",
        designacao,
        {"obrigacao": designacao.obrigacao_id, "valor": designacao.valor},
        motivo=justificativa,
    )
    avaliar_reserva()


def utilizar_reserva(
    autor: Conta, despesa: Despesa, valor: Decimal, justificativa: str
) -> MovimentoFinanceiro:
    """Cobre uma despesa pendente com a reserva, de imediato: tarifa para `despesas_a_cobrir` e
    déficit de frete para o `frete` da rodada."""
    _exigir_transacao("utilizar_reserva")
    _exigir_administrador(autor)
    valor = _valor(valor)
    justificativa = _justificativa(justificativa)
    destino = _destino_da_despesa(despesa)
    caixa = _travar_a_reserva(destino)
    _sem_invariante_violado()
    _exigir_livre(valor)
    if valor > pendente_da_despesa(despesa):
        raise CoberturaExcedente("o valor passa do que falta cobrir na despesa")
    movimento = lancar(
        tipo=TipoDeMovimento.COBERTURA_DE_DESPESA,
        transferencias=[Transferencia(caixa, destino, valor)],
        autor=autor,
        justificativa=justificativa,
        origem=despesa,
        chave=f"cobertura:{despesa.pk}:{uuid.uuid4().hex}",
    )
    avaliar_reserva()
    return movimento


__all__ = [
    "AporteRepetido",
    "CoberturaExcedente",
    "DesignacaoEncerrada",
    "InvarianteViolado",
    "ItemSemCobertura",
    "ReservaInsuficiente",
    "SituacaoDaReserva",
    "avaliar_reserva",
    "consumido_da_designacao",
    "desfazer_designacao",
    "designar_reserva",
    "itens_sem_cobertura",
    "obrigacoes_sem_cobertura",
    "pendente_da_despesa",
    "registrar_aporte",
    "sem_cobertura_da_obrigacao",
    "situacao_da_reserva",
    "utilizar_reserva",
]
