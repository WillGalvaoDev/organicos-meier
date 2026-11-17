"""O envoltório que registra cada execução das tarefas periódicas e a situação delas (E15-01).

O envoltório nunca engole a exceção do corpo nem muda o retorno dele. A gravação acontece depois
do corpo, numa transação própria: se uma transação do corpo for desfeita o registro não se perde,
e se a gravação falhar o resultado do corpo não muda (a falha vai para o log, sem dados pessoais).
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction

from apps.nucleo.tempo import agora
from apps.operacao.catalogo import POR_NOME, TAREFAS_MONITORADAS
from apps.operacao.models import ExecucaoDaTarefa

logger = logging.getLogger(__name__)

EM_DIA = "em_dia"
ATRASADA = "atrasada"
SEM_REGISTRO = "sem_registro"


@dataclass(frozen=True)
class SituacaoDaTarefa:
    nome: str
    descricao: str
    intervalo: timedelta
    tolerancia: timedelta
    estado: str
    monitorada_desde: datetime | None
    ultima_conclusao_em: datetime | None
    ultima_falha_em: datetime | None
    ultimo_erro: str
    falhas_seguidas: int
    atrasada_desde: datetime | None


def _criar(nome: str, instante: datetime) -> ExecucaoDaTarefa:
    return ExecucaoDaTarefa.objects.create(nome=nome, monitorada_desde=instante)


def _travar_ou_criar(nome: str, instante: datetime) -> ExecucaoDaTarefa:
    """O registro da tarefa, travado. Duas primeiras execuções simultâneas criam um só: o `UNIQUE`
    decide, e quem perde relê o registro."""
    registro = ExecucaoDaTarefa.objects.select_for_update().filter(nome=nome).first()
    if registro is not None:
        return registro
    try:
        with transaction.atomic():
            return _criar(nome, instante)
    except IntegrityError:
        return ExecucaoDaTarefa.objects.select_for_update().get(nome=nome)


def _gravar(nome: str, instante: datetime, erro: str | None) -> None:
    with transaction.atomic():
        registro = _travar_ou_criar(nome, instante)
        if erro is None:
            if registro.ultima_conclusao_em is None or instante > registro.ultima_conclusao_em:
                registro.ultima_conclusao_em = instante
            registro.falhas_seguidas = 0
        else:
            if registro.ultima_falha_em is None or instante > registro.ultima_falha_em:
                registro.ultima_falha_em = instante
                registro.ultimo_erro = erro
            registro.falhas_seguidas += 1
        registro.save()


def _gravar_sem_falhar(nome: str, erro: str | None) -> None:
    try:
        _gravar(nome, agora(), erro)
    except Exception as falha:
        logger.error(
            "falha ao registrar a execução da tarefa: tarefa=%s erro=%s", nome, type(falha).__name__
        )


@contextmanager
def execucao_monitorada(nome: str) -> Iterator[None]:
    """Envolve o corpo de uma tarefa periódica do catálogo e registra como ele terminou."""
    if nome not in POR_NOME:
        raise ValueError(f"tarefa fora do catálogo: {nome!r}")
    try:
        yield
    except Exception as excecao:
        _gravar_sem_falhar(nome, type(excecao).__name__)
        raise
    _gravar_sem_falhar(nome, None)


def situacao_das_tarefas(instante: datetime) -> list[SituacaoDaTarefa]:
    """A situação de cada tarefa do catálogo, na ordem dele."""
    registros = {r.nome: r for r in ExecucaoDaTarefa.objects.all()}
    situacoes = []
    for tarefa in TAREFAS_MONITORADAS:
        registro = registros.get(tarefa.nome)
        estado = SEM_REGISTRO
        atrasada_desde = None
        if registro is not None:
            referencia = registro.ultima_conclusao_em or registro.monitorada_desde
            if instante - referencia > tarefa.tolerancia:
                estado = ATRASADA
                atrasada_desde = referencia + tarefa.tolerancia
            else:
                estado = EM_DIA
        situacoes.append(
            SituacaoDaTarefa(
                nome=tarefa.nome,
                descricao=tarefa.descricao,
                intervalo=tarefa.intervalo,
                tolerancia=tarefa.tolerancia,
                estado=estado,
                monitorada_desde=registro.monitorada_desde if registro else None,
                ultima_conclusao_em=registro.ultima_conclusao_em if registro else None,
                ultima_falha_em=registro.ultima_falha_em if registro else None,
                ultimo_erro=registro.ultimo_erro if registro else "",
                falhas_seguidas=registro.falhas_seguidas if registro else 0,
                atrasada_desde=atrasada_desde,
            )
        )
    return situacoes
