"""E08: concorrência da abertura, das tentativas, da quitação e da moderação.

E08-02: A-20 e A-21.
"""

from decimal import Decimal

import pytest

from apps.catalogo.servicos import editar_produto
from apps.notificacoes.models import Notificacao
from apps.pedidos.abertura import abrir_pagamento
from apps.pedidos.models import AberturaDoPagamento, ItemDoPedido, Pedido
from apps.rodadas.fechamento import TransicaoRecusada
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.pedidos import T0, Arranjo, administrador, montar_arranjo
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
