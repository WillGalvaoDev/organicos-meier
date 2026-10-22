"""Obrigações com compradores: criação financiada pela regra, cobertura e liquidação (E09-06).

Cada devolução devida vira uma obrigação, financiada na criação pela regra de origem fixa (P-2),
componente por componente, até onde houver saldo na própria rodada. O que não couber fica sem
cobertura até o administrador escolher a fonte. A liquidação dá baixa uma única vez, pela chave
dada por quem executou a devolução.

Ordem das travas: as contas envolvidas, em ordem crescente de `pk`, antes de ler qualquer saldo.
"""

import logging
import uuid
from decimal import Decimal
from typing import Any, NamedTuple

from django.db.models import Sum

from apps.contas.models import Conta
from apps.financeiro.alertas import resolver_alerta
from apps.financeiro.livro import (
    EXTERIOR,
    MovimentoConflitante,
    Transferencia,
    _travar_conta,
    conta,
    lancar,
    saldo,
)
from apps.financeiro.models import (
    ApuracaoNoLivro,
    Componente,
    ContaFinanceira,
    DesignacaoDaReserva,
    Despesa,
    Destinacao,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    TipoDeDespesa,
    TipoDeMovimento,
    TransferenciaFinanceira,
)
from apps.financeiro.reserva import (
    CoberturaExcedente,
    _exigir_administrador,
    _exigir_transacao,
    _justificativa,
    _valor,
    avaliar_reserva,
    consumido_da_designacao,
    sem_cobertura_da_obrigacao,
)
from apps.nucleo.auditoria import SISTEMA
from apps.nucleo.valores import ValorInvalido, dinheiro
from apps.pedidos.models import DestinoDoPagamento, MotivoDoDestino, Pedido
from apps.rodadas.models import Ciclo, Rodada

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")
TIPO_DA_OBRIGACAO = "financeiro.obrigacaocomcomprador"
MOTIVOS_COM_ALERTA = (MotivoDoDestino.APROVADO_APOS_A_MARGEM, MotivoDoDestino.DUPLICIDADE)


class LiquidacaoRecusada(Exception):
    """A liquidação passa do que falta devolver ou do que está financiado."""


class ObrigacaoRegistrada(NamedTuple):
    obrigacao: ObrigacaoComComprador
    sem_cobertura: Decimal


def conta_da_obrigacao(obrigacao: ObrigacaoComComprador) -> ContaFinanceira:
    return conta(
        Destinacao.OBRIGACAO_COMPRADOR,
        obrigacao=obrigacao.pk,
        rodada=obrigacao.rodada_id,
        ciclo=obrigacao.ciclo_id,
        comprador=obrigacao.comprador_id,
    )


def travar_em_ordem(*contas: ContaFinanceira) -> None:
    """Trava as contas em ordem crescente de `pk`: a ordem global do livro-razão."""
    for pk in sorted({c.pk for c in contas}):
        _travar_conta(pk)


# --- criação da obrigação, financiada pela regra --------------------------------------------


def _componente(valor: object) -> Decimal:
    if not isinstance(valor, Decimal):
        raise ValueError("os componentes devem ser Decimal")
    try:
        convertido = dinheiro(valor)
    except ValorInvalido as erro:
        raise ValueError(str(erro)) from None
    if convertido < 0:
        raise ValueError("componente negativo")
    return convertido


def _fontes(
    rodada: Rodada, ciclo: Ciclo, comprador: Conta, depois_da_apuracao: bool
) -> dict[str, ContaFinanceira]:
    """A fonte de cada componente: a custódia antes da apuração; depois dela, a obrigação com o
    fornecedor (produtos), a receita de serviço e o frete da rodada."""
    if not depois_da_apuracao:
        return {
            componente: conta(
                Destinacao.CUSTODIA,
                rodada=rodada.pk,
                ciclo=ciclo.pk,
                comprador=comprador.pk,
                componente=componente,
            )
            for componente in (Componente.PRODUTOS, Componente.SERVICO, Componente.FRETE)
        }
    return {
        Componente.PRODUTOS: conta(
            Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=rodada.fornecedor_id, rodada=rodada.pk
        ),
        Componente.SERVICO: conta(Destinacao.RECEITA_SERVICO, rodada=rodada.pk),
        Componente.FRETE: conta(Destinacao.FRETE, rodada=rodada.pk),
    }


def registrar_obrigacao_com_comprador(
    *,
    origem: Any,
    rodada: Rodada,
    ciclo: Ciclo,
    comprador: Conta,
    pedido: Pedido,
    motivo: str,
    produtos: Decimal,
    servico: Decimal,
    frete: Decimal,
) -> ObrigacaoRegistrada:
    """Cria a obrigação e a financia pela tabela das fontes, no mesmo movimento. Devolve a
    obrigação e o que ficou sem cobertura. Valores inválidos ou incoerentes: `ValueError`."""
    _exigir_transacao("registrar_obrigacao_com_comprador")
    valores = {
        Componente.PRODUTOS: _componente(produtos),
        Componente.SERVICO: _componente(servico),
        Componente.FRETE: _componente(frete),
    }
    if sum(valores.values(), ZERO) <= 0:
        raise ValueError("a soma dos componentes deve ser maior que zero")
    if pedido.comprador_id != comprador.pk:
        raise ValueError("o pedido não é do comprador")
    if pedido.abertura.ciclo_id != ciclo.pk or ciclo.rodada_id != rodada.pk:
        raise ValueError("o pedido, o ciclo e a rodada não conferem")
    origem_tipo, origem_id = origem._meta.label_lower, str(origem.pk)
    if ObrigacaoComComprador.objects.filter(origem_tipo=origem_tipo, origem_id=origem_id).exists():
        raise ValueError("a origem já gerou uma obrigação")
    apurado = ApuracaoNoLivro.objects.filter(ciclo=ciclo).exists()
    obrigacao = ObrigacaoComComprador.objects.create(
        rodada=rodada,
        ciclo=ciclo,
        pedido=pedido,
        comprador=comprador,
        origem_tipo=origem_tipo,
        origem_id=origem_id,
        motivo=motivo,
        produtos=valores[Componente.PRODUTOS],
        servico=valores[Componente.SERVICO],
        frete=valores[Componente.FRETE],
        depois_da_apuracao=apurado,
    )
    destino = conta_da_obrigacao(obrigacao)
    fontes = _fontes(rodada, ciclo, comprador, apurado)
    travar_em_ordem(destino, *fontes.values())
    transferencias: list[Transferencia] = []
    do_frete = ZERO
    for componente, valor in valores.items():
        disponivel = max(ZERO, saldo(fontes[componente]))
        tirado = min(valor, disponivel)
        if tirado > 0:
            transferencias.append(Transferencia(fontes[componente], destino, tirado))
            if componente == Componente.FRETE:
                do_frete = tirado
    if transferencias:
        lancar(
            tipo=TipoDeMovimento.FINANCIAMENTO_DE_OBRIGACAO,
            transferencias=transferencias,
            autor=SISTEMA,
            justificativa="Devolução devida (P-2): recursos da própria rodada",
            origem=obrigacao,
            chave=f"financiamento:{obrigacao.pk}",
        )
    if apurado and do_frete > 0:
        # devolver frete de frete(r) reduz o frete arrecadado líquido: nasce o déficit
        Despesa.objects.create(
            tipo=TipoDeDespesa.DEFICIT_DE_FRETE, valor=do_frete, rodada=rodada, ciclo=ciclo
        )
    avaliar_reserva()
    return ObrigacaoRegistrada(obrigacao, sem_cobertura_da_obrigacao(obrigacao))


# --- cobertura pelo administrador -------------------------------------------------------------


def cobrir_obrigacao_com_receita(
    autor: Conta,
    obrigacao: ObrigacaoComComprador,
    rodada_fonte: Rodada,
    valor: Decimal,
    justificativa: str,
) -> MovimentoFinanceiro:
    """O administrador cobre o que falta da obrigação com a receita de serviço de uma rodada."""
    _exigir_transacao("cobrir_obrigacao_com_receita")
    _exigir_administrador(autor)
    valor = _valor(valor)
    justificativa = _justificativa(justificativa)
    destino = conta_da_obrigacao(obrigacao)
    receita = conta(Destinacao.RECEITA_SERVICO, rodada=rodada_fonte.pk)
    travar_em_ordem(destino, receita)
    if valor > sem_cobertura_da_obrigacao(obrigacao):
        raise CoberturaExcedente("o valor passa do que falta cobrir na obrigação")
    movimento = lancar(
        tipo=TipoDeMovimento.FINANCIAMENTO_DE_OBRIGACAO,
        transferencias=[Transferencia(receita, destino, valor)],
        autor=autor,
        justificativa=justificativa,
        origem=obrigacao,
        chave=f"cobertura-receita:{obrigacao.pk}:{uuid.uuid4().hex}",
    )
    avaliar_reserva()
    return movimento


# --- liquidação --------------------------------------------------------------------------------


def _liquidado(destino: ContaFinanceira) -> Decimal:
    saiu = TransferenciaFinanceira.objects.filter(de=destino, para__isnull=True).aggregate(
        s=Sum("valor")
    )["s"]
    return Decimal(saiu) if saiu is not None else ZERO


def _designacoes_ativas(
    obrigacao: ObrigacaoComComprador,
) -> list[tuple[DesignacaoDaReserva, Decimal]]:
    """As designações não desfeitas da obrigação, em ordem de criação, com o que resta de cada."""
    ativas = DesignacaoDaReserva.objects.filter(obrigacao=obrigacao, desfeita__isnull=True)
    restantes = [(d, Decimal(d.valor) - consumido_da_designacao(d)) for d in ativas.order_by("pk")]
    return [(d, resto) for d, resto in restantes if resto > 0]


def _ja_liquidada(
    chave: str, obrigacao: ObrigacaoComComprador, valor: Decimal
) -> MovimentoFinanceiro | None:
    existente: MovimentoFinanceiro | None = MovimentoFinanceiro.objects.filter(chave=chave).first()
    if existente is None:
        return None
    total = TransferenciaFinanceira.objects.filter(movimento=existente).aggregate(s=Sum("valor"))[
        "s"
    ]
    if (
        existente.tipo != TipoDeMovimento.DEVOLUCAO
        or (existente.origem_tipo, existente.origem_id) != (TIPO_DA_OBRIGACAO, str(obrigacao.pk))
        or total != valor
    ):
        raise MovimentoConflitante(f"a referência {chave!r} já existe com outro conteúdo")
    return existente


def liquidar_obrigacao(
    obrigacao: ObrigacaoComComprador, valor: Decimal, *, referencia: str
) -> MovimentoFinanceiro:
    """Dá baixa na obrigação quando a devolução é feita (chamada pela E10). Usa primeiro o saldo
    financiado da conta e depois as designações ativas, em ordem de criação; depois vem a saída."""
    _exigir_transacao("liquidar_obrigacao")
    if not isinstance(valor, Decimal) or valor <= 0:
        raise LiquidacaoRecusada("o valor deve ser maior que zero")
    chave = f"devolucao:{referencia}"
    existente = _ja_liquidada(chave, obrigacao, valor)
    if existente is not None:
        return existente
    destino = conta_da_obrigacao(obrigacao)
    caixa = conta(Destinacao.RESERVA)
    travar_em_ordem(destino, caixa)
    liquidado = _liquidado(destino)
    ativas = _designacoes_ativas(obrigacao)
    disponivel = max(ZERO, saldo(destino)) + sum((resto for _, resto in ativas), ZERO)
    if valor > obrigacao.devido - liquidado:
        raise LiquidacaoRecusada("o valor passa do que falta devolver")
    if valor > disponivel:
        raise LiquidacaoRecusada("o valor passa do que está financiado")
    falta_financiar = max(ZERO, valor - max(ZERO, saldo(destino)))
    for designacao, resto in ativas:
        if falta_financiar <= 0:
            break
        usado = min(resto, falta_financiar)
        lancar(
            tipo=TipoDeMovimento.FINANCIAMENTO_DE_OBRIGACAO,
            transferencias=[Transferencia(caixa, destino, usado)],
            autor=SISTEMA,
            justificativa="Devolução devida (P-3): consumo da designação da reserva",
            origem=designacao,
            chave=f"consumo:{designacao.pk}:{referencia}",
        )
        falta_financiar -= usado
    movimento = lancar(
        tipo=TipoDeMovimento.DEVOLUCAO,
        transferencias=[Transferencia(destino, EXTERIOR, valor)],
        autor=SISTEMA,
        justificativa="Devolução ao comprador concluída",
        origem=obrigacao,
        chave=chave,
    )
    if (
        liquidado + valor == obrigacao.devido
        and obrigacao.origem_tipo == "pedidos.destinodopagamento"
        and obrigacao.motivo in MOTIVOS_COM_ALERTA
    ):
        id_externo = DestinoDoPagamento.objects.get(
            pk=int(obrigacao.origem_id)
        ).pagamento.id_externo
        resolver_alerta(obrigacao.motivo, id_externo, motivo="devolução concluída")
    avaliar_reserva()
    return movimento
