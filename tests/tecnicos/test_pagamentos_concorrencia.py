"""E07-01: criação concorrente da mesma cobrança (acceptance A-15)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.nucleo.tempo import agora
from apps.pagamentos.provedor import NovaCobranca, obter_provedor
from apps.simulador_pagamentos.models import CobrancaSimulada
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.trava import esperando, segurando

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]


def test_a_mesma_chave_em_duas_conexoes_cria_uma_cobranca_so(simulador_pagamentos: object) -> None:
    # A-15
    nova = NovaCobranca(
        chave_idempotencia="k1",
        referencia_externa="ref-1",
        valor=Decimal("45.90"),
        descricao="Pedido de teste",
        expira_em=agora() + timedelta(days=1),
    )
    resultados = executar_em_paralelo(
        segurando(lambda: obter_provedor().criar_cobranca(nova)),
        esperando(lambda: obter_provedor().criar_cobranca(nova)),
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    ids = {r.valor.pagamento.id_externo for r in resultados}
    assert len(ids) == 1
    assert CobrancaSimulada.objects.count() == 1
