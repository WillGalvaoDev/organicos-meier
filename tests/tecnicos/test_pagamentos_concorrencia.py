"""E07-01: criação concorrente da mesma cobrança (acceptance A-15)."""

import threading
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction

from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.tempo import agora
from apps.pagamentos.chamadas import OPERACOES, Operacao, agendar_chamada, processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor, ConsultaDoPagamento, PagamentoNoProvedor
from apps.pagamentos.provedor import NovaCobranca, SituacaoNoProvedor, obter_provedor
from apps.pagamentos.sinais import situacao_do_pagamento_mudou
from apps.pagamentos.sincronizacao import sincronizar_pagamento
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


class _Sinais:
    def __init__(self) -> None:
        self.recebidos: list[tuple[Any, Any]] = []

    def __call__(self, sender: Any, anterior: Any, atual: Any, **kwargs: Any) -> None:
        self.recebidos.append((anterior, atual))


@pytest.fixture
def sinais() -> Iterator[_Sinais]:
    receptor = _Sinais()
    situacao_do_pagamento_mudou.connect(receptor, weak=False, dispatch_uid="concorrencia")
    yield receptor
    situacao_do_pagamento_mudou.disconnect(dispatch_uid="concorrencia")


def _cobranca_pendente() -> str:
    nova = NovaCobranca(
        chave_idempotencia="k-sync",
        referencia_externa="ref-1",
        valor=Decimal("45.90"),
        descricao="Pedido de teste",
        expira_em=agora() + timedelta(days=1),
    )
    return obter_provedor().criar_cobranca(nova).pagamento.id_externo


def _sincronizar(id_externo: str) -> Any:
    with transaction.atomic():
        resposta = obter_provedor().consultar_pagamento(id_externo)
        return sincronizar_pagamento(resposta, origem="aviso")


def test_cinco_sincronizacoes_do_mesmo_pagamento_aprovado(
    simulador_pagamentos: Any, sinais: _Sinais
) -> None:  # A-13
    id_externo = _cobranca_pendente()
    _sincronizar(id_externo)
    simulador_pagamentos.aprovar(id_externo)
    resultados = executar_em_paralelo(
        segurando(lambda: _sincronizar(id_externo)),
        *[esperando(lambda: _sincronizar(id_externo)) for _ in range(4)],
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    pagamentos = list(PagamentoNoProvedor.objects.all())
    assert len(pagamentos) == 1
    assert pagamentos[0].situacao == "aprovado"
    assert EntradaAuditoria.objects.filter(acao="pagamento.situacao").count() == 1
    assert sinais.recebidos == [(SituacaoNoProvedor.PENDENTE, SituacaoNoProvedor.APROVADO)]
    assert ConsultaDoPagamento.objects.count() == 6


def test_primeira_consulta_concorrente_cria_um_registro_so(
    simulador_pagamentos: Any, sinais: _Sinais
) -> None:  # A-14
    id_externo = _cobranca_pendente()
    simulador_pagamentos.aprovar(id_externo)
    resultados = executar_em_paralelo(
        segurando(lambda: _sincronizar(id_externo)),
        esperando(lambda: _sincronizar(id_externo)),
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert PagamentoNoProvedor.objects.count() == 1
    entradas = list(EntradaAuditoria.objects.filter(acao="pagamento.situacao"))
    assert len(entradas) == 1
    assert entradas[0].alteracoes["anterior"] is None
    assert sinais.recebidos == [(None, SituacaoNoProvedor.APROVADO)]
    assert ConsultaDoPagamento.objects.count() == 2


def test_duas_execucoes_nao_tentam_a_mesma_chamada(
    simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-14
    id_externo = _cobranca_pendente()
    with transaction.atomic():
        agendar_chamada("consultar_pagamento", id_externo)
    entrou, terminou = threading.Event(), threading.Event()
    consultas: list[str] = []
    original = OPERACOES["consultar_pagamento"]

    def lenta(provedor: Any, chamada: Any) -> Any:
        entrou.set()
        assert terminou.wait(20), "a segunda execução não terminou"
        consultas.append(chamada.alvo)
        return original.executar(provedor, chamada)

    monkeypatch.setitem(OPERACOES, "consultar_pagamento", Operacao(lenta, original.concluir))

    def segunda(barreira: Any) -> int:
        assert entrou.wait(20), "a primeira execução não chegou a chamar o provedor"
        try:
            return processar_chamadas()
        finally:
            terminou.set()

    resultados = executar_em_paralelo(lambda barreira: processar_chamadas(), segunda)
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert [r.valor for r in resultados] == [1, 0]
    assert consultas == [id_externo]
    assert ChamadaAoProvedor.objects.get().situacao == "concluida"


def test_agendamentos_concorrentes_do_mesmo_alvo(simulador_pagamentos: Any) -> None:  # A-15
    id_externo = _cobranca_pendente()

    def agendar() -> Any:
        with transaction.atomic():
            return agendar_chamada("consultar_pagamento", id_externo)

    resultados = executar_em_paralelo(segurando(agendar), esperando(agendar))
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert ChamadaAoProvedor.objects.filter(situacao="pendente").count() == 1
    assert len({r.valor.pk for r in resultados}) == 1
