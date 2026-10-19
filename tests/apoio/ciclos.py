"""Transições de teste que antecipam o que a E06 fará (E03-07).

`simular_inicio_do_fechamento` faz o contrato da E06: nas mesmas travas e na mesma transação,
registra as condições do ciclo e grava `fechamento`. `simular_volta_para_interesse` trava
fornecedor e rodada, nessa ordem, e grava `interesse`. A E06 substitui os dois pelas transições
reais, que devem passar nos mesmos testes.
"""

from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Max

from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.nucleo.tempo import agora
from apps.rodadas.fechamento import iniciar_fechamento
from apps.rodadas.models import Ciclo, Etapa, PrazoDoFechamento, Rodada


def simular_inicio_do_fechamento(rodada: Rodada) -> Ciclo:
    """Usa a transição real da E06-01 (o administrador é o que a fábrica já cria)."""
    administrador = Conta.objects.get(papel=Papel.ADMINISTRADOR)
    ciclo = iniciar_fechamento(administrador, rodada)
    rodada.refresh_from_db()
    return ciclo


def simular_volta_para_interesse(rodada: Rodada) -> None:
    with transaction.atomic():
        Fornecedor.objects.select_for_update().get(pk=rodada.fornecedor_id)
        travada = Rodada.objects.select_for_update().get(pk=rodada.pk)
        travada.etapa = Etapa.INTERESSE
        travada.save(update_fields=["etapa"])
    rodada.refresh_from_db()


def dar_prazo_de_teste(rodada: Rodada, termina_em: datetime | None = None) -> PrazoDoFechamento:
    """Dá um ciclo e uma linha de prazo `inicio` a uma rodada posta em `fechamento` pela fábrica
    ou por `update()` (E06-03). Só para preparação: o serviço real é `iniciar_fechamento`.

    Padrão de `termina_em`: daqui a 24 h em `fechamento` e um minuto atrás em
    `fechamento_encerrado`.
    """
    administrador = Conta.objects.get(papel=Papel.ADMINISTRADOR)
    fornecedor = Fornecedor.objects.get(pk=rodada.fornecedor_id)
    maior = Ciclo.objects.filter(rodada_id=rodada.pk).aggregate(maior=Max("numero"))["maior"]
    ciclo = Ciclo.objects.create(
        rodada_id=rodada.pk, numero=(maior or 0) + 1, minimo=fornecedor.minimo
    )
    if termina_em is None:
        encerrado = rodada.etapa == Etapa.FECHAMENTO_ENCERRADO
        termina_em = agora() - timedelta(minutes=1) if encerrado else agora() + timedelta(hours=24)
    return PrazoDoFechamento.objects.create(
        ciclo=ciclo, termina_em=termina_em, origem="inicio", autor=administrador
    )
