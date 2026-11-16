"""Apoio dos testes da E15: o arranjo AO (administrador, comprador, fornecedor e tarefas em dia).

A especificação pede dois administradores ativos e um suspenso, mas o banco só admite um
administrador, sempre ativo (`conta_administrador_unico` e `conta_administrador_ativo`; funcional
§1: "há um único administrador"). O arranjo tem só ADM1; o desvio está no review.md da E15-02.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from apps.contas.models import Conta, Papel
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

INSTANTE = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
MIN = timedelta(minutes=1)


@dataclass
class Ao:
    adm1: Any
    c: Any
    f: Any


def concluir(nome: str, instante: datetime) -> None:
    """Grava a última conclusão da tarefa no instante dado (o registro nasce se faltar)."""
    from apps.operacao.models import ExecucaoDaTarefa

    registro, _ = ExecucaoDaTarefa.objects.get_or_create(
        nome=nome, defaults={"monitorada_desde": instante}
    )
    registro.ultima_conclusao_em = instante
    registro.falhas_seguidas = 0
    registro.save()


def concluir_todas(instante: datetime, *, exceto: tuple[str, ...] = ()) -> None:
    from apps.operacao.catalogo import TAREFAS_MONITORADAS

    for tarefa in TAREFAS_MONITORADAS:
        if tarefa.nome not in exceto:
            concluir(tarefa.nome, instante)


def arranjo_ao(relogio: RelogioControlado) -> Ao:
    """O administrador, um comprador e um fornecedor, o relógio em `INSTANTE` e todas as tarefas
    do catálogo concluídas nele."""
    relogio.congelar(INSTANTE)
    adm1 = Conta.objects.filter(papel=Papel.ADMINISTRADOR).first() or ContaFactory.create(
        nome="ADM1", administrador=True
    )
    c = ContaFactory.create(nome="C")
    f = ContaFactory.create(nome="F", fornecedor=True)
    concluir_todas(INSTANTE)
    return Ao(adm1, c, f)


def verificar(relogio: RelogioControlado, instante: datetime) -> tuple[int, int]:
    """Congela o relógio no instante e roda a verificação operacional."""
    from apps.operacao.verificacao import verificar_operacao_agora

    relogio.congelar(instante)
    return verificar_operacao_agora()


def alertas(tipo: str | None = None, *, abertos: bool = False) -> list[Any]:
    from apps.financeiro.models import AlertaFinanceiro

    consulta = AlertaFinanceiro.objects.all()
    if tipo is not None:
        consulta = consulta.filter(tipo=tipo)
    if abertos:
        consulta = consulta.filter(resolvido_em__isnull=True)
    return list(consulta.order_by("pk"))


def notificacoes(conta: Any, evento: str = "alerta_operacional") -> list[Any]:
    from apps.notificacoes.models import Notificacao

    return list(Notificacao.objects.filter(conta=conta, evento=evento).order_by("pk"))
