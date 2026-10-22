"""Apuração no livro-razão, frete do ciclo e cobertura de despesas (E09-06).

Depois da apuração final (E11), a custódia dos pedidos válidos vai para as obrigações com o
fornecedor, a receita de serviço e o frete. O frete efetivo e o déficit ficam registrados
separadamente, e as tarifas pendentes da rodada são cobertas pela receita dela (P-1). Quando a
apuração acontece e quais pedidos são válidos é da E11; aqui está só o efeito no livro.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Sum

from apps.contas.models import Conta
from apps.financeiro.livro import (
    MovimentoConflitante,
    Transferencia,
    conta,
    lancar,
    saldo,
    travar_contas,
)
from apps.financeiro.models import (
    ApuracaoNoLivro,
    Componente,
    ContaFinanceira,
    Despesa,
    Destinacao,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    PedidoApurado,
    TipoDeDespesa,
    TipoDeMovimento,
)
from apps.financeiro.reserva import (
    CoberturaExcedente,
    _exigir_administrador,
    _exigir_transacao,
    _justificativa,
    _valor,
    avaliar_reserva,
    pendente_da_despesa,
    utilizar_reserva,
)
from apps.nucleo.auditoria import SISTEMA
from apps.pedidos.models import AberturaDoPagamento, DestinoDaDecisao, DestinoDoPagamento, Pedido
from apps.rodadas.models import Ciclo, Rodada

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class FreteDoCiclo:
    """O frete efetivo (o `F` da abertura), o arrecadado, o devolvido depois da apuração, o
    déficit (efetivo menos o arrecadado líquido) e o quanto dele já foi coberto. Antes da
    apuração não há frete efetivo, e todos os campos são `None`."""

    efetivo: Decimal | None
    arrecadado: Decimal | None
    devolvido: Decimal | None
    deficit: Decimal | None
    deficit_coberto: Decimal | None


def _validar_pedidos(ciclo: Ciclo, pedidos: list[Pedido]) -> AberturaDoPagamento:
    abertura: AberturaDoPagamento | None = AberturaDoPagamento.objects.filter(ciclo=ciclo).first()
    if abertura is None:
        raise ValueError("o ciclo não tem abertura de pagamento")
    if len({p.pk for p in pedidos}) != len(pedidos):
        raise ValueError("a lista de pedidos tem repetição")
    for pedido in pedidos:
        if pedido.abertura.ciclo_id != ciclo.pk:
            raise ValueError(f"o pedido {pedido.pk} não é do ciclo")
        quitado = DestinoDoPagamento.objects.filter(
            pedido=pedido, destino=DestinoDaDecisao.QUITA
        ).exists()
        if not quitado:
            raise ValueError(f"o pedido {pedido.pk} não tem pagamento que quita")
    return abertura


def _repetir(existente: ApuracaoNoLivro, conjunto: set[int], ciclo: Ciclo) -> ApuracaoNoLivro:
    gravado = set(existente.pedidos_validos.values_list("pedido_id", flat=True))
    if gravado != conjunto:
        raise MovimentoConflitante(f"o ciclo {ciclo.pk} já foi apurado com outros pedidos")
    return existente


def registrar_apuracao_no_livro(
    ciclo: Ciclo, pedidos_validos: list[Pedido], *, autor: Any
) -> ApuracaoNoLivro:
    """Leva a custódia dos pedidos válidos às obrigações com o fornecedor, à receita de serviço e
    ao frete, num movimento só; registra o frete efetivo e o arrecadado; abre a despesa de déficit
    e cobre as tarifas pendentes da rodada. Repetir com o mesmo conjunto devolve a existente."""
    _exigir_transacao("registrar_apuracao_no_livro")
    abertura = _validar_pedidos(ciclo, pedidos_validos)
    existente: ApuracaoNoLivro | None = ApuracaoNoLivro.objects.filter(ciclo=ciclo).first()
    conjunto = {p.pk for p in pedidos_validos}
    if existente is not None:
        return _repetir(existente, conjunto, ciclo)
    rodada = ciclo.rodada
    destinos = {
        Componente.PRODUTOS: conta(
            Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=rodada.fornecedor_id, rodada=rodada.pk
        ),
        Componente.SERVICO: conta(Destinacao.RECEITA_SERVICO, rodada=rodada.pk),
        Componente.FRETE: conta(Destinacao.FRETE, rodada=rodada.pk),
    }
    pedidos = sorted(pedidos_validos, key=lambda p: p.pk)
    origens: list[tuple[Componente, ContaFinanceira]] = [
        (
            componente,
            conta(
                Destinacao.CUSTODIA,
                rodada=rodada.pk,
                ciclo=ciclo.pk,
                comprador=pedido.comprador_id,
                componente=componente,
            ),
        )
        for pedido in pedidos
        for componente in (Componente.PRODUTOS, Componente.SERVICO, Componente.FRETE)
    ]
    # regra única de travas: as custódias, os três destinos e `despesas_a_cobrir` (que a
    # cobertura automática das tarifas usa) de uma vez; só depois se confere o ciclo e se leem
    # os saldos
    travar_contas(
        *destinos.values(),
        conta(Destinacao.DESPESAS_A_COBRIR),
        *(origem for _, origem in origens),
    )
    existente = ApuracaoNoLivro.objects.filter(ciclo=ciclo).first()
    if existente is not None:
        return _repetir(existente, conjunto, ciclo)
    transferencias: list[Transferencia] = []
    arrecadado = ZERO
    for componente, origem in origens:
        movido = saldo(origem)  # o saldo atual, sob a trava: o pago menos o que já financiou
        if movido > 0:
            transferencias.append(Transferencia(origem, destinos[componente], movido))
            if componente == Componente.FRETE:
                arrecadado += movido
    movimento = None
    if transferencias:
        movimento = lancar(
            tipo=TipoDeMovimento.APURACAO,
            transferencias=transferencias,
            autor=autor,
            justificativa="Apuração final aprovada (infraestrutura 3.2)",
            origem=ciclo,
            chave=f"apuracao:{ciclo.pk}",
        )
    apuracao = ApuracaoNoLivro.objects.create(
        ciclo=ciclo,
        movimento=movimento,
        frete_efetivo=abertura.frete,
        frete_arrecadado=arrecadado,
    )
    PedidoApurado.objects.bulk_create(
        [PedidoApurado(apuracao=apuracao, pedido=pedido) for pedido in pedidos]
    )
    deficit = Decimal(abertura.frete) - arrecadado
    if deficit > 0:
        Despesa.objects.create(
            tipo=TipoDeDespesa.DEFICIT_DE_FRETE, valor=deficit, rodada=rodada, ciclo=ciclo
        )
    cobrir_tarifas_pendentes_da_rodada(rodada)
    avaliar_reserva()
    return apuracao


def cobrir_tarifas_pendentes_da_rodada(rodada: Rodada) -> int:
    """Cobre com a receita de serviço da rodada as tarifas dela, na ordem de criação, inteiras ou
    nada (P-1). A que não cabe fica pendente para o administrador. Devolve quantas cobriu."""
    receita = conta(Destinacao.RECEITA_SERVICO, rodada=rodada.pk)
    a_cobrir = conta(Destinacao.DESPESAS_A_COBRIR)  # o destino de toda tarifa
    travar_contas(receita, a_cobrir)
    cobertas = 0
    tarifas = Despesa.objects.filter(tipo=TipoDeDespesa.TARIFA, rodada=rodada).order_by("pk")
    for despesa in tarifas:
        pendente = pendente_da_despesa(despesa)
        if pendente <= 0 or saldo(receita) < pendente:
            continue
        lancar(
            tipo=TipoDeMovimento.COBERTURA_DE_DESPESA,
            transferencias=[Transferencia(receita, a_cobrir, pendente)],
            autor=SISTEMA,
            justificativa="Tarifa coberta pela receita de serviço da rodada (P-1)",
            origem=despesa,
            chave=f"cobertura:{despesa.pk}:p1",
        )
        cobertas += 1
    return cobertas


def rodada_apurada(rodada: Rodada) -> bool:
    return ApuracaoNoLivro.objects.filter(ciclo__rodada=rodada).exists()


def frete_do_ciclo(ciclo: Ciclo) -> FreteDoCiclo:
    """O relatório do frete do ciclo; antes da apuração, todos os campos são `None`."""
    apuracao = ApuracaoNoLivro.objects.filter(ciclo=ciclo).first()
    if apuracao is None:
        return FreteDoCiclo(None, None, None, None, None)
    devolvido = ObrigacaoComComprador.objects.filter(
        ciclo=ciclo, depois_da_apuracao=True
    ).aggregate(s=Sum("frete"))["s"]
    devolvido = Decimal(devolvido) if devolvido is not None else ZERO
    efetivo, arrecadado = Decimal(apuracao.frete_efetivo), Decimal(apuracao.frete_arrecadado)
    coberto = sum(
        (
            Decimal(d.valor) - pendente_da_despesa(d)
            for d in Despesa.objects.filter(tipo=TipoDeDespesa.DEFICIT_DE_FRETE, ciclo=ciclo)
        ),
        ZERO,
    )
    return FreteDoCiclo(
        efetivo=efetivo,
        arrecadado=arrecadado,
        devolvido=devolvido,
        deficit=efetivo - (arrecadado - devolvido),
        deficit_coberto=coberto,
    )


def cobrir_despesa(
    autor: Conta,
    despesa: Despesa,
    *,
    fonte: tuple[str, Rodada] | str,
    valor: Decimal,
    justificativa: str,
) -> MovimentoFinanceiro:
    """O administrador cobre uma despesa pendente com a receita de uma rodada (`("receita",
    rodada)`) ou com a reserva (`"reserva"`)."""
    _exigir_transacao("cobrir_despesa")
    if fonte == "reserva":
        return utilizar_reserva(autor, despesa, valor, justificativa)
    if not (isinstance(fonte, tuple) and len(fonte) == 2 and fonte[0] == "receita"):
        raise ValueError("a fonte é a reserva ou a receita de uma rodada")
    _exigir_administrador(autor)
    valor = _valor(valor)
    justificativa = _justificativa(justificativa)
    receita = conta(Destinacao.RECEITA_SERVICO, rodada=fonte[1].pk)
    if despesa.tipo == TipoDeDespesa.TARIFA:
        destino = conta(Destinacao.DESPESAS_A_COBRIR)
    else:
        destino = conta(Destinacao.FRETE, rodada=despesa.rodada_id)
    travar_contas(receita, destino)
    if valor > pendente_da_despesa(despesa):
        raise CoberturaExcedente("o valor passa do que falta cobrir na despesa")
    movimento = lancar(
        tipo=TipoDeMovimento.COBERTURA_DE_DESPESA,
        transferencias=[Transferencia(receita, destino, valor)],
        autor=autor,
        justificativa=justificativa,
        origem=despesa,
        chave=f"cobertura:{despesa.pk}:{uuid.uuid4().hex}",
    )
    avaliar_reserva()
    return movimento
