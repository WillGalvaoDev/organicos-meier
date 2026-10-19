"""Transições de teste que antecipam o que a E06 fará (E03-07).

`simular_inicio_do_fechamento` faz o contrato da E06: nas mesmas travas e na mesma transação,
registra as condições do ciclo e grava `fechamento`. `simular_volta_para_interesse` trava
fornecedor e rodada, nessa ordem, e grava `interesse`. A E06 substitui os dois pelas transições
reais, que devem passar nos mesmos testes.
"""

from django.db import transaction

from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.rodadas.fechamento import iniciar_fechamento
from apps.rodadas.models import Ciclo, Etapa, Rodada


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
