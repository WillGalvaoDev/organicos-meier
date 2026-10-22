"""Conciliação diária com o provedor (E09-07).

Compara os movimentos e o saldo do provedor com o livro-razão, um dia de cada vez (de 00:00 a
24:00 em Brasília). Cada movimento do provedor procura o seu par no livro; cada aporte ou saída
registrado no livro procura o seu movimento no provedor. Divergência vira alerta; pagamento sem
lançamento vira alerta e uma consulta agendada. A conciliação nunca altera o livro-razão: só abre
e resolve alertas e agenda consultas.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum

from apps.financeiro.alertas import abrir_alerta, resolver_alerta
from apps.financeiro.livro import saldo_total_esperado
from apps.financeiro.models import (
    AlertaFinanceiro,
    ConciliacaoDiaria,
    Despesa,
    MovimentoFinanceiro,
    TipoDeAlerta,
    TipoDeDespesa,
    TipoDeMovimento,
    TransferenciaFinanceira,
)
from apps.nucleo.tempo import FUSO_DA_OPERACAO, agora, no_fuso_da_operacao
from apps.pagamentos.chamadas import agendar_chamada
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
from apps.pagamentos.provedor import (
    MovimentoNoProvedor,
    ProvedorIndisponivel,
    RecusaDoProvedor,
    TipoDeMovimentoNoProvedor,
    obter_provedor,
)
from apps.pedidos.models import DestinoDoPagamento

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")
JANELA_DO_LIVRO = timedelta(days=3)
MICROSSEGUNDO = timedelta(microseconds=1)
TIPOS_DE_SAIDA_NO_LIVRO = (
    TipoDeMovimento.REPASSE,
    TipoDeMovimento.RETIRADA_DE_RECEITA,
    TipoDeMovimento.PAGAMENTO_DO_FRETE,
)

SEM_LANCAMENTO = "sem_lancamento"
DIVERGENTE = "divergente"


@dataclass
class _Achados:
    """O que a leitura do dia encontrou, antes de qualquer escrita."""

    sem_lancamento: list[MovimentoNoProvedor] = field(default_factory=list)
    divergentes: list[MovimentoNoProvedor] = field(default_factory=list)
    livro_sem_par: list[tuple[str, Decimal]] = field(
        default_factory=list
    )  # (identificação, ±valor)
    movimentos_do_dia: int = 0


def limites_do_dia(data: date) -> tuple[datetime, datetime]:
    """O início (inclusive) e o fim (exclusivo) do dia em Brasília, em UTC."""
    inicio = datetime.combine(data, time.min, tzinfo=FUSO_DA_OPERACAO).astimezone(UTC)
    fim = datetime.combine(data + timedelta(days=1), time.min, tzinfo=FUSO_DA_OPERACAO)
    return inicio, fim.astimezone(UTC)


def _total(chave: str, ate: datetime | None = None) -> Decimal | None:
    """A soma das transferências do movimento com essa chave; `None` se ele não existe (ou, com
    `ate`, se só foi lançado depois desse instante)."""
    movimentos = MovimentoFinanceiro.objects.filter(chave=chave)
    if ate is not None:
        movimentos = movimentos.filter(momento__lte=ate)
    if not movimentos.exists():
        return None
    total = TransferenciaFinanceira.objects.filter(movimento__chave=chave).aggregate(
        s=Sum("valor")
    )["s"]
    return Decimal(total) if total is not None else ZERO


def _classificar(movimento: MovimentoNoProvedor, ate: datetime | None = None) -> str | None:
    """`None` se o movimento tem par no livro; senão, `SEM_LANCAMENTO` (pagamento ainda sem a
    entrada) ou `DIVERGENTE`. Com `ate`, só vale o par lançado até esse instante."""
    tipo = movimento.tipo
    if tipo == TipoDeMovimentoNoProvedor.PAGAMENTO:
        destino = DestinoDoPagamento.objects.filter(
            pagamento__id_externo=movimento.id_externo
        ).first()
        entrada = _total(f"entrada:{destino.pk}", ate) if destino is not None else None
        if entrada is None:
            return SEM_LANCAMENTO
        return None if entrada == movimento.valor else DIVERGENTE
    if tipo == TipoDeMovimentoNoProvedor.TARIFA:
        despesas = Despesa.objects.filter(
            tipo=TipoDeDespesa.TARIFA,
            pagamento__id_externo=movimento.id_externo,
            valor=abs(movimento.valor),
        )
        if ate is not None:
            despesas = despesas.filter(criada_em__lte=ate)
        return None if despesas.exists() else DIVERGENTE
    if tipo == TipoDeMovimentoNoProvedor.DEPOSITO:
        total = _total(f"aporte:{movimento.id_movimento}", ate)
        return None if total == movimento.valor else DIVERGENTE
    if tipo == TipoDeMovimentoNoProvedor.SAIDA:
        total = _total(f"saida:{movimento.id_movimento}", ate)
        return None if total == abs(movimento.valor) else DIVERGENTE
    return DIVERGENTE  # ajuste, outro ou um tipo que o livro não conhece


def _identificacao(chave: str) -> str:
    return chave.split(":", 1)[1]


def _do_livro_sem_par(
    inicio: datetime,
    fim: datetime,
    ids_do_provedor: set[str],
    *,
    incluindo_o_fim: bool,
) -> list[tuple[str, Decimal]]:
    """Os aportes e as saídas do livro com `momento` em [inicio, fim) (ou [inicio, fim], no
    recorte da diferença) que não têm movimento do provedor de mesma identificação em
    `ids_do_provedor`. Devolve (identificação, valor com sinal)."""
    filtro = {"momento__gte": inicio}
    filtro["momento__lte" if incluindo_o_fim else "momento__lt"] = fim
    registrados = MovimentoFinanceiro.objects.filter(
        tipo__in=(TipoDeMovimento.APORTE, *TIPOS_DE_SAIDA_NO_LIVRO), **filtro
    ).order_by("pk")
    sem_par: list[tuple[str, Decimal]] = []
    for movimento in registrados:
        identificacao = _identificacao(movimento.chave)
        if identificacao in ids_do_provedor:
            continue
        sinal = 1 if movimento.tipo == TipoDeMovimento.APORTE else -1
        sem_par.append((identificacao, sinal * (_total(movimento.chave) or ZERO)))
    return sem_par


def _ler_o_dia(
    movimentos: list[MovimentoNoProvedor], inicio: datetime, fim: datetime, instante: datetime
) -> tuple[_Achados, Decimal]:
    """Os três recortes da conciliação (E09-R07), sobre a mesma lista do provedor. `instante` é o
    `referente_a` do saldo. Devolve os achados do dia e o ajuste da diferença de saldo."""
    achados = _Achados()
    # 1. os movimentos do dia: classificação, alertas e a contagem do resumo
    do_dia = [m for m in movimentos if inicio <= m.ocorrido_em < fim]
    achados.movimentos_do_dia = len(do_dia)
    for movimento in do_dia:
        motivo = _classificar(movimento)
        if motivo is not None:
            (achados.sem_lancamento if motivo == SEM_LANCAMENTO else achados.divergentes).append(
                movimento
            )
    # 2. o par inverso: o provedor de D - 3 dias até o fim de D, o livro só no dia D
    ids_do_par_inverso = {m.id_movimento for m in movimentos if m.ocorrido_em < fim}
    achados.livro_sem_par = _do_livro_sem_par(
        inicio, fim, ids_do_par_inverso, incluindo_o_fim=False
    )
    # 3. a diferença no instante `instante`: só o que já existia nele, de um lado e do outro
    ate_o_instante = [m for m in movimentos if inicio <= m.ocorrido_em <= instante]
    do_provedor_sem_par = sum(
        (m.valor for m in ate_o_instante if _classificar(m, instante) is not None), ZERO
    )
    ids_ate_o_instante = {m.id_movimento for m in movimentos if m.ocorrido_em <= instante}
    do_livro_sem_par = sum(
        (
            valor
            for _, valor in _do_livro_sem_par(
                inicio, instante, ids_ate_o_instante, incluindo_o_fim=True
            )
        ),
        ZERO,
    )
    return achados, do_livro_sem_par - do_provedor_sem_par


def conciliar_dia(data: date) -> ConciliacaoDiaria:
    """Concilia o dia (uma vez só: repetir devolve o registro, sem consultar o provedor). Um dia
    que ainda não terminou é recusado com `ValueError`; com o provedor indisponível, levanta
    `ConsultaAoProvedorFalhou` e não grava nada."""
    existente: ConciliacaoDiaria | None = ConciliacaoDiaria.objects.filter(data=data).first()
    if existente is not None:
        return existente
    inicio, fim = limites_do_dia(data)
    if agora() < fim:
        raise ValueError(f"o dia {data} ainda não terminou")
    provedor = obter_provedor()
    try:
        saldo_do_provedor = provedor.consultar_saldo()
        ate = max(fim, saldo_do_provedor.referente_a + MICROSSEGUNDO)
        movimentos = provedor.listar_movimentos(inicio - JANELA_DO_LIVRO, ate)
    except (ProvedorIndisponivel, RecusaDoProvedor) as erro:
        motivo = "indisponivel" if isinstance(erro, ProvedorIndisponivel) else "recusa"
        logger.warning("Conciliação de %s adiada: provedor %s", data, motivo)
        raise ConsultaAoProvedorFalhou(f"conciliacao:{data}", motivo) from erro
    achados, ajuste = _ler_o_dia(movimentos, inicio, fim, saldo_do_provedor.referente_a)
    total_do_provedor = saldo_do_provedor.liberado + saldo_do_provedor.a_liberar
    diferenca = total_do_provedor - saldo_total_esperado(ate=saldo_do_provedor.referente_a) + ajuste
    sem_par = len(achados.sem_lancamento) + len(achados.divergentes) + len(achados.livro_sem_par)
    resultado = (
        ConciliacaoDiaria.Resultado.OK
        if sem_par == 0 and diferenca == 0
        else ConciliacaoDiaria.Resultado.DIVERGENTE
    )
    try:
        with transaction.atomic():
            conciliacao = ConciliacaoDiaria.objects.create(
                data=data,
                executada_em=agora(),
                resultado=resultado,
                resumo={
                    "movimentos": achados.movimentos_do_dia,
                    "sem_par": sem_par,
                    "diferenca": diferenca,
                },
            )
            _abrir_e_resolver_alertas(data, achados, diferenca)
    except IntegrityError:
        # outra execução conciliou o mesmo dia primeiro: a restrição única decidiu
        concorrente: ConciliacaoDiaria | None = ConciliacaoDiaria.objects.filter(data=data).first()
        if concorrente is None:
            raise
        return concorrente
    return conciliacao


def _abrir_e_resolver_alertas(data: date, achados: _Achados, diferenca: Decimal) -> None:
    for movimento in achados.sem_lancamento:
        id_externo = movimento.id_externo or movimento.id_movimento
        abrir_alerta(
            TipoDeAlerta.PAGAMENTO_SEM_CONCILIACAO,
            id_externo,
            {"id_externo": id_externo, "valor": movimento.valor, "data": data.isoformat()},
        )
        agendar_chamada("consultar_pagamento", id_externo)
    for movimento in achados.divergentes:
        abrir_alerta(
            TipoDeAlerta.DIVERGENCIA_NA_CONCILIACAO,
            movimento.id_movimento,
            {
                "data": data.isoformat(),
                "id_movimento": movimento.id_movimento,
                "tipo_no_provedor": movimento.tipo.value,
                "tipo": movimento.tipo.value,
                "descricao_no_provedor": movimento.descricao_no_provedor,
                "valor": movimento.valor,
                "id_externo": movimento.id_externo,
            },
        )
    for identificacao, valor in achados.livro_sem_par:
        abrir_alerta(
            TipoDeAlerta.DIVERGENCIA_NA_CONCILIACAO,
            f"livro:{identificacao}",
            {"data": data.isoformat(), "identificacao": identificacao, "valor": valor},
        )
    if diferenca != 0:
        abrir_alerta(
            TipoDeAlerta.DIVERGENCIA_NA_CONCILIACAO,
            f"saldo:{data.isoformat()}",
            {"data": data.isoformat(), "diferenca": diferenca},
        )
        return
    abertos = AlertaFinanceiro.objects.filter(
        tipo=TipoDeAlerta.DIVERGENCIA_NA_CONCILIACAO,
        resolvido_em__isnull=True,
        chave__startswith="saldo:",
    )
    for alerta in list(abertos):
        resolver_alerta(
            TipoDeAlerta.DIVERGENCIA_NA_CONCILIACAO,
            alerta.chave,
            motivo=f"conciliação de {data.isoformat()} sem diferença",
        )


def conciliar_dias_pendentes_agora() -> int:
    """Concilia, em ordem, cada dia terminado ainda não conciliado: o primeiro é o seguinte ao
    último conciliado (na primeira vez, o dia anterior). Se o provedor falha, para ali e deixa o
    resto para a próxima hora. Devolve quantos dias concilou."""
    hoje = no_fuso_da_operacao(agora()).date()
    ultimo = ConciliacaoDiaria.objects.order_by("-data").first()
    dia = ultimo.data + timedelta(days=1) if ultimo is not None else hoje - timedelta(days=1)
    conciliados = 0
    while dia < hoje:
        try:
            conciliar_dia(dia)
        except ConsultaAoProvedorFalhou:
            break
        conciliados += 1
        dia += timedelta(days=1)
    return conciliados


__all__ = ["ConciliacaoDiaria", "conciliar_dia", "conciliar_dias_pendentes_agora", "limites_do_dia"]
