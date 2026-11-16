"""A verificação periódica dos alertas operacionais (E15-02).

Cada verificação devolve as ocorrências atuais do seu tipo (`dict[chave, dados]`). A execução abre o
alerta de cada ocorrência que não tem um aberto e, nos tipos de condição, resolve os abertos cuja
chave não voltou. Cada verificação roda numa transação própria: se levanta exceção, nada é aberto
nem resolvido para o tipo naquela execução, e as outras continuam.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from django.db import IntegrityError, transaction

from apps.financeiro.alertas import abrir_alerta, resolver_alerta
from apps.financeiro.models import AlertaFinanceiro
from apps.nucleo.tempo import agora
from apps.operacao.catalogo import TAREFAS_MONITORADAS
from apps.operacao.models import ExecucaoDaTarefa
from apps.operacao.tipos import CLASSIFICACAO, Natureza, link_do_alerta, natureza_do_alerta

__all__ = [
    "VERIFICACOES",
    "link_do_alerta",
    "natureza_do_alerta",
    "registrar_verificacao",
    "verificar_operacao_agora",
]

logger = logging.getLogger(__name__)

MOTIVO_DA_CONDICAO_ENCERRADA = "condição encerrada"

Verificacao = Callable[[datetime], dict[str, dict[str, Any]]]
VERIFICACOES: dict[str, Verificacao] = {}


def registrar_verificacao(tipo: str, funcao: Verificacao) -> None:
    """Registra a verificação do tipo; a ordem de registro é a ordem de execução."""
    VERIFICACOES[tipo] = funcao


def _criar_registros_que_faltam(instante: datetime) -> None:
    """Uma tarefa que nunca rodou passa a atrasada depois da tolerância (E15-01, regra 4)."""
    existentes = set(ExecucaoDaTarefa.objects.values_list("nome", flat=True))
    for tarefa in TAREFAS_MONITORADAS:
        if tarefa.nome in existentes:
            continue
        try:
            with transaction.atomic():
                ExecucaoDaTarefa.objects.create(nome=tarefa.nome, monitorada_desde=instante)
        except IntegrityError:
            pass  # outra execução criou primeiro: o `UNIQUE` decidiu


def _aplicar(tipo: str, funcao: Verificacao, instante: datetime) -> tuple[int, int]:
    ocorrencias = funcao(instante)
    classificacao = CLASSIFICACAO[tipo]
    abertos = resolvidos = 0
    for chave, dados in ocorrencias.items():
        ja_aberto = AlertaFinanceiro.objects.filter(
            tipo=tipo, chave=chave, resolvido_em__isnull=True
        ).exists()
        abrir_alerta(tipo, chave, dados)
        if not ja_aberto:
            abertos += 1
    if classificacao.natureza == Natureza.CONDICAO:
        antigos = AlertaFinanceiro.objects.filter(tipo=tipo, resolvido_em__isnull=True).exclude(
            chave__in=list(ocorrencias)
        )
        for chave in list(antigos.values_list("chave", flat=True)):
            if resolver_alerta(tipo, chave, motivo=MOTIVO_DA_CONDICAO_ENCERRADA) is not None:
                resolvidos += 1
    return abertos, resolvidos


def verificar_operacao_agora() -> tuple[int, int]:
    """Roda todas as verificações com o instante lido uma vez. Devolve (abertos, resolvidos)."""
    instante = agora()
    _criar_registros_que_faltam(instante)
    abertos = resolvidos = 0
    for tipo, funcao in list(VERIFICACOES.items()):
        try:
            with transaction.atomic():
                a, r = _aplicar(tipo, funcao, instante)
        except Exception as erro:
            logger.error(
                "verificação operacional falhou: tipo=%s erro=%s", tipo, type(erro).__name__
            )
            continue
        abertos += a
        resolvidos += r
    return abertos, resolvidos
