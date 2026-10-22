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
    soma_do_provedor_sem_par: Decimal = ZERO
    movimentos_do_dia: int = 0


def limites_do_dia(data: date) -> tuple[datetime, datetime]:
    """O início (inclusive) e o fim (exclusivo) do dia em Brasília, em UTC."""
    inicio = datetime.combine(data, time.min, tzinfo=FUSO_DA_OPERACAO).astimezone(UTC)
    fim = datetime.combine(data + timedelta(days=1), time.min, tzinfo=FUSO_DA_OPERACAO)
    return inicio, fim.astimezone(UTC)


def _total(chave: str) -> Decimal | None:
    """A soma das transferências do movimento com essa chave; `None` se ele não existe."""
    if not MovimentoFinanceiro.objects.filter(chave=chave).exists():
        return None
    total = TransferenciaFinanceira.objects.filter(movimento__chave=chave).aggregate(
        s=Sum("valor")
    )["s"]
    return Decimal(total) if total is not None else ZERO


def _classificar(movimento: MovimentoNoProvedor) -> str | None:
    """`None` se o movimento tem par no livro; senão, `SEM_LANCAMENTO` (pagamento ainda sem a
    entrada) ou `DIVERGENTE`."""
    tipo = movimento.tipo
    if tipo == TipoDeMovimentoNoProvedor.PAGAMENTO:
        destino = DestinoDoPagamento.objects.filter(
            pagamento__id_externo=movimento.id_externo
        ).first()
        entrada = _total(f"entrada:{destino.pk}") if destino is not None else None
        if entrada is None:
            return SEM_LANCAMENTO
        return None if entrada == movimento.valor else DIVERGENTE
    if tipo == TipoDeMovimentoNoProvedor.TARIFA:
        casa = Despesa.objects.filter(
            tipo=TipoDeDespesa.TARIFA,
            pagamento__id_externo=movimento.id_externo,
            valor=abs(movimento.valor),
        ).exists()
        return None if casa else DIVERGENTE
    if tipo == TipoDeMovimentoNoProvedor.DEPOSITO:
        total = _total(f"aporte:{movimento.id_movimento}")
        return None if total == movimento.valor else DIVERGENTE
    if tipo == TipoDeMovimentoNoProvedor.SAIDA:
        total = _total(f"saida:{movimento.id_movimento}")
        return None if total == abs(movimento.valor) else DIVERGENTE
    return DIVERGENTE  # ajuste, outro ou um tipo que o livro não conhece


def _identificacao(chave: str) -> str:
    return chave.split(":", 1)[1]


def _ler_o_dia(movimentos: list[MovimentoNoProvedor], inicio: datetime, fim: datetime) -> _Achados:
    achados = _Achados()
    ids_do_provedor = {m.id_movimento for m in movimentos}
    for movimento in movimentos:
        if movimento.ocorrido_em < inicio:
            continue  # só entra na janela do livro (ids)
        if movimento.ocorrido_em < fim:
            achados.movimentos_do_dia += 1
        motivo = _classificar(movimento)
        if motivo is None:
            continue
        achados.soma_do_provedor_sem_par += movimento.valor
        if movimento.ocorrido_em < fim:
            (achados.sem_lancamento if motivo == SEM_LANCAMENTO else achados.divergentes).append(
                movimento
            )
    no_dia = MovimentoFinanceiro.objects.filter(momento__gte=inicio, momento__lt=fim)
    registrados = list(
        no_dia.filter(tipo=TipoDeMovimento.APORTE).values_list("chave", flat=True).order_by("pk")
    ) + list(no_dia.filter(tipo__in=TIPOS_DE_SAIDA_NO_LIVRO).values_list("chave", flat=True))
    for chave in registrados:
        identificacao = _identificacao(chave)
        if identificacao in ids_do_provedor:
            continue
        total = _total(chave) or ZERO
        sinal = 1 if chave.startswith("aporte:") else -1
        achados.livro_sem_par.append((identificacao, sinal * total))
    return achados


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
    achados = _ler_o_dia(movimentos, inicio, fim)
    total_do_provedor = saldo_do_provedor.liberado + saldo_do_provedor.a_liberar
    diferenca = (
        total_do_provedor
        - saldo_total_esperado(ate=saldo_do_provedor.referente_a)
        - achados.soma_do_provedor_sem_par
        + sum((valor for _, valor in achados.livro_sem_par), ZERO)
    )
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
