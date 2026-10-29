"""Chamadas pendentes ao provedor (E07-04).

Uma chamada ao provedor não fica presa à requisição do usuário nem se perde se o processo cair:
é registrada na mesma transação que muda o estado do sistema, com a chave de idempotência
gravada antes, e uma tarefa a executa e repete as falhas temporárias com a mesma chave. A tarefa
nunca decide regra de negócio: o que a resposta significa fica no `concluir` de cada operação.
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.transaction import TransactionManagementError

from apps.nucleo.tempo import agora, prazo_encerrado, somar_horas
from apps.pagamentos.models import ChamadaAoProvedor, SituacaoDaChamada
from apps.pagamentos.provedor import (
    PagamentoConsultado,
    PagamentoNaoEncontrado,
    Provedor,
    ProvedorIndisponivel,
    RecusaDoProvedor,
    obter_provedor,
)
from apps.pagamentos.sincronizacao import sincronizar_pagamento

logger = logging.getLogger(__name__)

# Depois de uma falha temporária: 1, 5, 15 e 60 minutos, e depois a cada 60 minutos. Não há limite
# de tentativas: desistir de uma consulta poderia deixar dinheiro recebido sem registro (§8.3).
INTERVALOS_EM_MINUTOS = (1, 5, 15, 60)
HORAS_PARA_DESISTIR_DA_CONSULTA = 24


class FalhaTemporaria(Exception):
    """A operação não terminou, mas pode ser repetida com a mesma chave. `codigo` é curto."""

    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo


class FalhaDefinitiva(Exception):
    """A operação recusa antes de chamar o provedor (E08-03): é tratada como uma
    `RecusaDoProvedor`, com a chamada em `falhou` e o `codigo` curto como último erro.

    `encontrados` leva os pagamentos que a operação achou no provedor ao recusar (a busca pela
    referência): o `falhou` da operação os sincroniza e cancela o que ficou sem dono."""

    def __init__(self, codigo: str, *, encontrados: tuple[PagamentoConsultado, ...] = ()) -> None:
        super().__init__(codigo)
        self.codigo = codigo
        self.encontrados = encontrados


@dataclass(frozen=True)
class Operacao:
    """`executar` fala com o provedor; `concluir` aplica o resultado no banco, na mesma
    transação; `falhou` (opcional) trata a falha definitiva."""

    executar: Callable[[Provedor, ChamadaAoProvedor], Any]
    concluir: Callable[[ChamadaAoProvedor, Any], None]
    falhou: Callable[[ChamadaAoProvedor, Exception], None] | None = None
    # Junta os parâmetros de um novo agendamento aos da chamada pendente que o absorve (R02).
    combinar: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None
    # Gancho da falha temporária (E10-04): roda depois de gravar `tentativas`, `ultimo_erro` e
    # `proxima_em`, na mesma transação, com o código da falha.
    adiada: Callable[[ChamadaAoProvedor, str], None] | None = None


OPERACOES: dict[str, Operacao] = {}


def registrar_operacao(nome: str, operacao: Operacao) -> None:
    OPERACOES[nome] = operacao


def _pendente(operacao: str, alvo: str) -> ChamadaAoProvedor | None:
    """A chamada pendente do par, travada até o fim da transação de quem agenda (E07-R01).

    Sem `skip_locked` e sem `nowait`: se uma execução da tarefa está com a linha, o agendamento
    espera, e o Postgres reavalia `situacao = 'pendente'` na versão nova da linha. Concluída ou
    falhou, não há pendente e o agendamento cria outra, que consultará depois dele. Continuando
    pendente, a execução da tarefa a pula (`skip_locked`) até esta transação terminar, então
    a consulta sempre acontece depois do agendamento.
    """
    return (
        ChamadaAoProvedor.objects.select_for_update()
        .filter(operacao=operacao, alvo=alvo, situacao=SituacaoDaChamada.PENDENTE)
        .first()
    )


def _absorver(existente: ChamadaAoProvedor, parametros: dict[str, Any] | None) -> ChamadaAoProvedor:
    """Devolve a pendente, combinando os parâmetros novos se a operação souber (R02). Só os
    `parametros` mudam: chave, `proxima_em`, tentativas e criação ficam como estavam."""
    combinar = OPERACOES[existente.operacao].combinar
    if parametros and combinar is not None:
        combinados = combinar(existente.parametros, parametros)
        if combinados != existente.parametros:
            existente.parametros = combinados
            existente.save(update_fields=["parametros"])
    return existente


def agendar_chamada(
    operacao: str,
    alvo: str,
    *,
    parametros: dict[str, Any] | None = None,
    chave_idempotencia: str | None = None,
) -> ChamadaAoProvedor:
    """Registra a chamada na transação corrente; já havendo uma pendente do mesmo par
    (operação, alvo), devolve essa (combinando os parâmetros, se a operação souber)."""
    if not connection.in_atomic_block:
        raise TransactionManagementError("agendar_chamada exige uma transação aberta.")
    if operacao not in OPERACOES:
        raise ValueError(f"operação desconhecida: {operacao!r}")
    existente = _pendente(operacao, alvo)
    if existente is not None:
        return _absorver(existente, parametros)
    instante = agora()
    try:
        with transaction.atomic():
            return ChamadaAoProvedor.objects.create(
                operacao=operacao,
                alvo=alvo,
                parametros=parametros or {},
                chave_idempotencia=chave_idempotencia or uuid.uuid4().hex,
                provedor=obter_provedor().nome,
                ambiente=settings.AMBIENTE,
                proxima_em=instante,
                criada_em=instante,
            )
    except IntegrityError:
        # outra transação agendou o mesmo par primeiro: a restrição parcial decidiu
        existente = _pendente(operacao, alvo)
        if existente is None:
            raise
        return _absorver(existente, parametros)


def _intervalo(tentativas: int) -> timedelta:
    indice = min(tentativas, len(INTERVALOS_EM_MINUTOS)) - 1
    return timedelta(minutes=INTERVALOS_EM_MINUTOS[indice])


def _tentar(chamada: ChamadaAoProvedor) -> None:
    """Executa a chamada com a linha travada e grava o resultado, na transação corrente."""
    operacao = OPERACOES[chamada.operacao]
    instante = agora()  # lido depois da trava
    try:
        # O que o provedor guardou é dele e não se desfaz com a nossa transação (o simulador
        # confirma o que grava na conexão própria, E07-R03); o que `concluir` grava vale tudo
        # ou nada.
        resultado = operacao.executar(obter_provedor(), chamada)
        with transaction.atomic():
            operacao.concluir(chamada, resultado)
    except (ProvedorIndisponivel, FalhaTemporaria) as erro:
        codigo = erro.codigo if isinstance(erro, FalhaTemporaria) else "indisponivel"
        chamada.tentativas += 1
        chamada.ultimo_erro = codigo
        chamada.proxima_em = instante + _intervalo(chamada.tentativas)
        chamada.save(update_fields=["tentativas", "ultimo_erro", "proxima_em"])
        if operacao.adiada is not None:
            operacao.adiada(chamada, codigo)
        logger.info(
            "Chamada ao provedor %s: %s nova tentativa em %s",
            chamada.pk,
            chamada.operacao,
            chamada.proxima_em.isoformat(),
        )
        return
    except (RecusaDoProvedor, FalhaDefinitiva) as erro:
        chamada.tentativas += 1
        chamada.situacao = SituacaoDaChamada.FALHOU
        chamada.ultimo_erro = erro.codigo
        chamada.concluida_em = instante
        chamada.save(update_fields=["tentativas", "situacao", "ultimo_erro", "concluida_em"])
        if operacao.falhou is not None:
            operacao.falhou(chamada, erro)
        logger.info(
            "Chamada ao provedor %s: %s falhou %s", chamada.pk, chamada.operacao, erro.codigo
        )
        return
    chamada.tentativas += 1
    chamada.situacao = SituacaoDaChamada.CONCLUIDA
    chamada.concluida_em = instante
    chamada.save(update_fields=["tentativas", "situacao", "concluida_em"])
    logger.info("Chamada ao provedor %s: %s concluida", chamada.pk, chamada.operacao)


def processar_chamadas(*, limite: int = 100) -> int:
    """Tenta as chamadas pendentes já vencidas, uma transação por chamada, e devolve quantas
    foram tentadas. Uma chamada travada por outra execução é pulada; uma exceção inesperada
    desfaz só aquela chamada, que fica como estava para a próxima execução."""
    tentadas = 0
    vistas: list[int] = []
    while tentadas < limite:
        with transaction.atomic():
            chamada = (
                ChamadaAoProvedor.objects.select_for_update(skip_locked=True)
                .filter(situacao=SituacaoDaChamada.PENDENTE, proxima_em__lte=agora())
                .exclude(pk__in=vistas)
                .order_by("proxima_em", "id")
                .first()
            )
            if chamada is None:
                break
            vistas.append(chamada.pk)
            tentadas += 1
            try:
                with transaction.atomic():
                    _tentar(chamada)
            except Exception as erro:
                logger.error(
                    "Chamada ao provedor %s: %s erro inesperado %s",
                    chamada.pk,
                    chamada.operacao,
                    type(erro).__name__,
                )
    return tentadas


def nao_encontrado(chamada: ChamadaAoProvedor) -> Exception:
    """O pagamento não existe no provedor ainda: pode ser atraso de consistência (L-6), e só
    depois de 24 horas a chamada desiste. Devolve a exceção que a operação deve levantar."""
    limite = somar_horas(chamada.criada_em, HORAS_PARA_DESISTIR_DA_CONSULTA)
    if prazo_encerrado(agora(), limite):
        return RecusaDoProvedor("nao_encontrado")
    return FalhaTemporaria("nao_encontrado")


def _consultar(provedor: Provedor, chamada: ChamadaAoProvedor) -> Any:
    try:
        return provedor.consultar_pagamento(chamada.alvo)
    except PagamentoNaoEncontrado:
        raise nao_encontrado(chamada) from None


def _concluir_consulta(chamada: ChamadaAoProvedor, resultado: Any) -> None:
    aviso = chamada.parametros.get("aviso_recebido_em")
    sincronizar_pagamento(
        resultado,
        origem=chamada.parametros.get("origem", "tarefa"),
        aviso_recebido_em=datetime.fromisoformat(aviso) if aviso else None,
    )


def _combinar_consulta(atuais: dict[str, Any], novos: dict[str, Any]) -> dict[str, Any]:
    """O horário do aviso fica com o mais antigo dos dois (em ISO 8601 UTC) e a origem vira
    `aviso` se qualquer um dos dois for aviso."""
    resultado = dict(atuais)
    horarios = [
        datetime.fromisoformat(p["aviso_recebido_em"])
        for p in (atuais, novos)
        if p.get("aviso_recebido_em")
    ]
    if horarios:
        resultado["aviso_recebido_em"] = min(horarios).astimezone(UTC).isoformat()
    if "aviso" in (atuais.get("origem"), novos.get("origem")):
        resultado["origem"] = "aviso"
    return resultado


registrar_operacao(
    "consultar_pagamento", Operacao(_consultar, _concluir_consulta, combinar=_combinar_consulta)
)
