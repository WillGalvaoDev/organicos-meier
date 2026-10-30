"""T-8: a devolução é idempotente. Falha temporária e resposta perdida usam a mesma chave e
produzem um estorno e uma liquidação só (E10-04, A-9 e A-10)."""

from datetime import timedelta
from typing import Any

import pytest

from apps.financeiro.devolucoes import autorizar_devolucao
from apps.financeiro.models import MovimentoFinanceiro
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor
from apps.simulador_pagamentos.models import EstornoSimulado
from tests.apoio.devolucoes import arranjo_da_devolucao
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db


def test_resposta_perdida_depois_de_executar_nao_devolve_duas_vezes(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    simulador_pagamentos.falhar_proximas(2, operacao="estornar", depois_de_executar=True)
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    for _ in range(3):
        processar_chamadas()
        relogio.avancar(timedelta(minutes=61))
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert EstornoSimulado.objects.count() == 1
    assert MovimentoFinanceiro.objects.filter(tipo="devolucao").count() == 1
    assert ChamadaAoProvedor.objects.filter(operacao="estornar").count() == 1


def test_falhas_antes_de_executar_repetem_a_mesma_chave(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    simulador_pagamentos.falhar_proximas(3, operacao="estornar")
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    chave = parcela.chave_idempotencia
    for _ in range(4):
        processar_chamadas()
        relogio.avancar(timedelta(minutes=61))
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert ChamadaAoProvedor.objects.get(operacao="estornar").chave_idempotencia == chave
    assert EstornoSimulado.objects.count() == 1
