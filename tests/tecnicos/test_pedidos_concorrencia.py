"""E08: concorrência da abertura, das tentativas, da quitação e da moderação.

E08-02: A-20 e A-21. E08-03: A-19 e A-20 (tentativas).
"""

from decimal import Decimal
from threading import Event
from typing import Any

import pytest
from django.db import transaction

from apps.catalogo.servicos import editar_produto
from apps.notificacoes.models import Notificacao
from apps.pagamentos.chamadas import OPERACOES, Operacao, processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor
from apps.pedidos.abertura import abrir_pagamento
from apps.pedidos.models import (
    AberturaDoPagamento,
    ItemDoPedido,
    Pedido,
    SituacaoDoPedido,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import agendar_cancelamento, pedir_pagamento
from apps.rodadas.fechamento import TransicaoRecusada
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.pedidos import T0, Arranjo, administrador, montar_arranjo, pedido_aberto
from tests.apoio.trava import esperando, segurando
from tests.conftest import RelogioControlado

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]

D = Decimal


@pytest.fixture
def arranjo(relogio: RelogioControlado) -> Arranjo:
    relogio.congelar(T0)
    return montar_arranjo()


def _abrir(arranjo: Arranjo) -> object:
    return abrir_pagamento(administrador(), arranjo.rodada, D("22.00"))


def test_duas_aberturas_ao_mesmo_tempo_abrem_uma_so(arranjo: Arranjo) -> None:  # A-20
    resultados = executar_em_paralelo(
        segurando(lambda: _abrir(arranjo)),
        esperando(lambda: _abrir(arranjo)),
    )
    assert resultados[0].excecao is None, resultados[0].excecao
    assert isinstance(resultados[1].excecao, TransicaoRecusada), resultados[1].excecao
    assert resultados[1].excecao.codigo == "fora_de_fechamento_encerrado_para_pagamento"
    assert AberturaDoPagamento.objects.count() == 1
    assert Pedido.objects.count() == 2


def _precos_de_p1(arranjo: Arranjo) -> set[Decimal]:
    return set(
        ItemDoPedido.objects.filter(produto=arranjo.p1).values_list("preco_unitario", flat=True)
    )


def _preco_alterado(arranjo: Arranjo) -> list[int]:
    return [
        n.conta_id
        for n in Notificacao.objects.filter(evento="preco_alterado")
        if n.conta_id in (arranjo.a.pk, arranjo.b.pk)
    ]


def test_preco_gravado_antes_da_abertura_entra_nos_itens(arranjo: Arranjo) -> None:
    # A-21 (a): o preço vem antes
    resultados = executar_em_paralelo(
        segurando(lambda: editar_produto(administrador(), arranjo.p1, preco="11.00")),
        esperando(lambda: _abrir(arranjo)),
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert _precos_de_p1(arranjo) == {D("11.00")}
    arranjo.p1.refresh_from_db()
    assert arranjo.p1.preco == D("11.00")
    # O aviso de preço (E05-06) é devido: as parcelas ainda estavam `ativa` quando o preço mudou.
    assert sorted(_preco_alterado(arranjo)) == sorted([arranjo.a.pk, arranjo.b.pk])


def test_preco_gravado_depois_da_abertura_nao_muda_os_itens(arranjo: Arranjo) -> None:
    # A-21 (b): o preço vem depois
    resultados = executar_em_paralelo(
        segurando(lambda: _abrir(arranjo)),
        esperando(lambda: editar_produto(administrador(), arranjo.p1, preco="11.00")),
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert _precos_de_p1(arranjo) == {D("10.00")}
    arranjo.p1.refresh_from_db()
    assert arranjo.p1.preco == D("11.00")
    assert _preco_alterado(arranjo) == []


# --- E08-03: tentativas de pagamento (A-19 e A-20) -----------------------------------------


@pytest.fixture
def cenario(relogio: RelogioControlado, simulador_pagamentos: Any) -> tuple[Arranjo, Pedido]:
    return pedido_aberto(relogio)


def test_dois_cliques_em_pagar_geram_uma_tentativa(cenario: tuple[Arranjo, Pedido]) -> None:
    # A-19
    arranjo, x = cenario
    resultados = executar_em_paralelo(
        segurando(lambda: pedir_pagamento(arranjo.a, x)),
        esperando(lambda: pedir_pagamento(arranjo.a, x)),
    )
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert TentativaDePagamento.objects.filter(pedido=x).count() == 1
    assert ChamadaAoProvedor.objects.filter(operacao="criar_cobranca").count() == 1
    assert resultados[0].valor.pk == resultados[1].valor.pk


def test_cancelamento_em_execucao_nao_trava_a_moderacao(
    cenario: tuple[Arranjo, Pedido], monkeypatch: pytest.MonkeyPatch
) -> None:  # A-20
    arranjo, x = cenario
    pedir_pagamento(arranjo.a, x)
    assert processar_chamadas() == 1
    tentativa = TentativaDePagamento.objects.get(pedido=x)
    with transaction.atomic():
        agendar_cancelamento(tentativa, "prazo")
    original = OPERACOES["cancelar_cobranca"]
    entrou, liberar, primeira_terminou = Event(), Event(), Event()

    def parada(provedor: Any, chamada: ChamadaAoProvedor) -> Any:
        entrou.set()
        assert liberar.wait(20), "a segunda thread não terminou: esperou a chamada em andamento"
        return original.executar(provedor, chamada)

    monkeypatch.setitem(
        OPERACOES, "cancelar_cobranca", Operacao(parada, original.concluir, original.falhou)
    )

    def executa_a_chamada(barreira: Any) -> int:
        barreira.wait(timeout=10)
        try:
            return processar_chamadas()
        finally:
            primeira_terminou.set()

    def modera(barreira: Any) -> bool:
        barreira.wait(timeout=10)
        assert entrou.wait(10), "a chamada não entrou em execução"
        with transaction.atomic():
            SituacaoDoPedido.objects.select_for_update().get(pedido_id=x.pk)
            agendar_cancelamento(tentativa, "suspensao")
        terminou_antes = not primeira_terminou.is_set()
        liberar.set()
        return terminou_antes

    resultados = executar_em_paralelo(executa_a_chamada, modera)
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert resultados[1].valor is True
    alvos = sorted(
        ChamadaAoProvedor.objects.filter(operacao="cancelar_cobranca").values_list(
            "alvo", flat=True
        )
    )
    assert alvos == [f"t{tentativa.pk}:prazo", f"t{tentativa.pk}:suspensao"]
