"""E11-03: caixas invalidadas e o resultado da apuração (acceptance A-1 a A-9)."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction

from apps.catalogo.models import Unidade
from apps.financeiro.reembolsos import reembolso_parcial
from apps.nucleo.auditoria import SISTEMA, EntradaAuditoria
from apps.pedidos.models import (
    AberturaDoPagamento,
    ItemDoPedido,
    ParcelaNoPedido,
    SituacaoDePagamento,
    SituacaoDoPedido,
)
from apps.rodadas.models import Etapa
from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.ciclos import dar_prazo_de_teste
from tests.apoio.pedidos import T0, Arranjo, abrir, administrador, pedido_de
from tests.conftest import RelogioControlado
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ParcelaFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _iniciar(a: Any) -> Any:
    from apps.pedidos.apuracao import iniciar_apuracao

    return iniciar_apuracao(a.admin, a.rodada)


def _caixas() -> list[tuple[int, int]]:
    from apps.pedidos.models import CaixaInvalidada

    return list(
        CaixaInvalidada.objects.order_by("produto_id", "numero").values_list("produto_id", "numero")
    )


def _composicao() -> tuple[Any, ...]:
    return (
        list(ItemDoPedido.objects.order_by("pk").values()),
        list(ParcelaNoPedido.objects.order_by("pk").values()),
    )


def test_caixas_com_inadimplente_sao_invalidadas_sem_reorganizar(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    antes = _composicao()
    _iniciar(a)
    assert _caixas() == [(a.p2.pk, 1), (a.p2.pk, 2)]
    assert _composicao() == antes


def test_valor_valido_minimo_e_resultado_valida(relogio: RelogioControlado, sim: Any) -> None:
    # A-2
    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert apuracao.valor_valido == D("60.00")
    assert apuracao.minimo == D("50.00")
    assert apuracao.resultado == "valida"


def test_valor_abaixo_do_minimo_e_retorno_para_interesse(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-3
    a, x, _y = arranjo_ap(relogio, minimo="100.00")
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert (apuracao.valor_valido, apuracao.minimo) == (D("60.00"), D("100.00"))
    assert apuracao.resultado == "retorno_para_interesse"


def test_todos_pagaram_nenhuma_caixa_e_o_valor_inteiro(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    a, x, y = arranjo_ap(relogio, minimo="100.00")
    pagar(relogio, sim, x)
    pagar(relogio, sim, y)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert _caixas() == []
    assert apuracao.valor_valido == D("170.00")
    assert apuracao.resultado == "valida"


def test_ninguem_pagou_invalida_tudo_e_volta_para_interesse(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    a, _x, _y = arranjo_ap(relogio)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert _caixas() == [(a.p2.pk, 1), (a.p2.pk, 2)]
    assert apuracao.valor_valido == D("0.00")
    assert apuracao.resultado == "retorno_para_interesse"


def test_parcela_que_cruza_caixas_so_perde_a_parte_da_caixa_invalidada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    from apps.pedidos import apuracao as modulo

    a, x, _y = arranjo_ap(relogio, parcelas_de_p2=(("a", 4), ("c", 2), ("a", 2), ("b", 4)))
    assert a.c is not None
    z = pedido_de(a.c)
    pagar(relogio, sim, x)
    pagar(relogio, sim, z)
    relogio.congelar(PRAZO)
    resultado = _iniciar(a)
    assert _caixas() == [(a.p2.pk, 2)]
    abertura = AberturaDoPagamento.objects.get()
    nao_pagos = {
        s.pedido_id
        for s in SituacaoDoPedido.objects.all()
        if s.situacao != SituacaoDePagamento.PAGO
    }
    calculo = modulo._calcular_o_resultado(abertura, nao_pagos)
    item_a = ItemDoPedido.objects.get(pedido=x, produto=a.p2)
    item_c = ItemDoPedido.objects.get(pedido=z, produto=a.p2)
    assert calculo.unidades_invalidadas == {item_a.pk: D("2.000")}
    assert item_c.pk not in calculo.unidades_invalidadas
    assert ParcelaNoPedido.objects.filter(item=item_a, caixa=1).get().quantidade == D("4.000")
    assert resultado.valor_valido == D("90.00")


def test_valor_proporcional_arredondado_como_o_reembolso_parcial(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    relogio.congelar(T0)
    fornecedor = FornecedorFactory.create(nome="F", minimo=D("1.00"))
    rodada = RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.FECHAMENTO_ENCERRADO)
    ciclo = dar_prazo_de_teste(rodada).ciclo
    p4 = ProdutoFactory.create(
        fornecedor=fornecedor,
        nome="P4",
        unidade=Unidade.KG,
        preco=D("7.99"),
        incremento=D("0.250"),
        multiplo=D("0.500"),
    )
    EstoqueDaRodadaFactory.create(rodada=rodada, produto=p4, limite=None)
    comprador_a = ContaFactory.create(nome="Comprador A")
    comprador_b = ContaFactory.create(nome="Comprador B")
    for dono, quantidade in ((comprador_a, "0.750"), (comprador_b, "0.250")):
        ParcelaFactory.create(
            comprador=dono,
            produto=p4,
            quantidade_original=D(quantidade),
            quantidade_reservada=D(quantidade),
        )
    a = Arranjo(fornecedor, rodada, ciclo, p4, p4, comprador_a, comprador_b, administrador())
    abrir(a, "5.00")
    x = pedido_de(comprador_a)
    relogio.congelar(T0 + H)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    item = ItemDoPedido.objects.get(pedido=x)
    assert item.subtotal == D("5.99")
    with transaction.atomic():  # o que o reembolso parcial gravaria para esse item
        registrado = reembolso_parcial(
            item, D("0.250"), chave="prova", motivo="caixa_invalidada", autor=SISTEMA
        )
        produtos_do_reembolso = registrado.reembolso.produtos
        transaction.set_rollback(True)
    assert produtos_do_reembolso == D("2.00")
    resultado = _iniciar(a)
    assert _caixas() == [(p4.pk, 2)]
    assert resultado.valor_valido == D("5.99") - produtos_do_reembolso == D("3.99")


def test_recalcular_da_o_mesmo_resultado(relogio: RelogioControlado, sim: Any) -> None:  # A-8
    from apps.pedidos import apuracao as modulo

    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    resultado = _iniciar(a)
    abertura = AberturaDoPagamento.objects.get()
    nao_pagos = {
        s.pedido_id
        for s in SituacaoDoPedido.objects.all()
        if s.situacao != SituacaoDePagamento.PAGO
    }
    primeiro = modulo._calcular_o_resultado(abertura, nao_pagos)
    segundo = modulo._calcular_o_resultado(abertura, nao_pagos)
    assert primeiro == segundo
    assert primeiro.caixas == [(a.p2.pk, 1), (a.p2.pk, 2)]
    assert (primeiro.valor_valido, primeiro.resultado) == (
        resultado.valor_valido,
        resultado.resultado,
    )


def test_auditoria_leva_as_caixas_o_valor_o_minimo_e_o_resultado(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    _iniciar(a)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.apuracao_final")
    dados = auditoria.alteracoes
    assert dados["caixas"] == [[a.p2.pk, 1], [a.p2.pk, 2]]
    assert dados["valor_valido"] == "60.00"
    assert dados["minimo"] == "50.00"
    assert dados["resultado"] == "valida"
