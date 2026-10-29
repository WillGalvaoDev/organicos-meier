"""E10-02: cálculo do reembolso (acceptance A-1 a A-14 e A-17)."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction

from apps.financeiro.livro import conta_da_obrigacao, saldo
from apps.financeiro.models import ItemReembolsado, ObrigacaoComComprador, Reembolso
from apps.financeiro.reembolsos import (
    ReembolsoConflitante,
    ReembolsoRecusado,
    acumulado_do_item,
    acumulado_do_pedido,
    reembolso_parcial,
)
from apps.pedidos.models import ItemDoPedido, Pedido
from tests.apoio.devolucoes import (
    Item,
    K,
    M,
    N,
    componentes,
    integral,
    itens_do_pedido,
    parcial,
    pedido_pago_com_itens,
)
from tests.apoio.financeiro import chave_nova, pedido_composto
from tests.apoio.pedidos import administrador, cancelar_direto, sincronizar, tentativa_criada
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
OC = "ocorrencia_de_entrega"


_parcial = parcial
_integral = integral
_componentes = componentes


def _total_de_registros() -> tuple[int, int, int]:
    return (
        Reembolso.objects.count(),
        ItemReembolsado.objects.count(),
        ObrigacaoComComprador.objects.count(),
    )


def test_o_valor_vem_do_registrado_e_nao_do_catalogo(relogio: RelogioControlado) -> None:  # A-1
    _, (item,) = pedido_pago_com_itens(K)
    item.produto.preco = D("9.99")
    item.produto.save()
    registrado = _parcial(item, "0.25")
    assert registrado.reembolso.produtos == D("2.00")
    (linha,) = registrado.reembolso.itens.all()
    assert (linha.item_id, linha.quantidade, linha.valor) == (item.pk, D("0.250"), D("2.00"))


def test_quatro_parciais_completam_o_pedido_exatamente(relogio: RelogioControlado) -> None:  # A-2
    _, (item,) = pedido_pago_com_itens(K)
    feitos = [_componentes(_parcial(item, "0.25")) for _ in range(4)]
    assert [p for p, _, _ in feitos] == [D("2.00"), D("2.00"), D("2.00"), D("1.99")]
    assert sum((p for p, _, _ in feitos), D("0.00")) == D("7.99")
    assert sum((s for _, s, _ in feitos), D("0.00")) == D("0.40")
    assert sum((f for _, _, f in feitos), D("0.00")) == D("1.60")
    assert feitos[3][1:] == (D("0.10"), D("0.40"))


def test_integral_depois_de_parcial_devolve_o_saldo_exato(
    relogio: RelogioControlado,
) -> None:  # A-3
    pedido, (item,) = pedido_pago_com_itens(K)
    _parcial(item, "0.25")
    registrado = _integral(pedido)
    (linha,) = registrado.reembolso.itens.all()
    assert (linha.quantidade, linha.valor) == (D("0.750"), D("5.99"))
    assert _componentes(registrado) == (D("5.99"), D("0.30"), D("1.20"))
    assert acumulado_do_pedido(pedido) == (D("7.99"), D("0.40"), D("1.60"))


def test_centavos_que_nao_fecham_o_ultimo_leva_o_saldo(relogio: RelogioControlado) -> None:  # A-4
    _, (item,) = pedido_pago_com_itens(M)
    valores = [_parcial(item, "0.1").reembolso.produtos for _ in range(5)]
    sexto = _parcial(item, "0.1")
    assert [*valores, sexto.reembolso.produtos] == [
        D("0.02"),
        D("0.02"),
        D("0.02"),
        D("0.02"),
        D("0.01"),
        D("0.00"),
    ]
    assert sexto.obrigacao is None
    assert sexto.sem_cobertura == D("0.00")
    assert acumulado_do_item(item) == (D("0.600"), D("0.09"))
    antes = _total_de_registros()
    with pytest.raises(ReembolsoRecusado, match="passa da quantidade paga"):
        _parcial(item, "0.1")
    assert _total_de_registros() == antes


def test_servico_e_frete_proporcionais_aos_produtos(relogio: RelogioControlado) -> None:  # A-5
    pedido, (i1, i2) = pedido_pago_com_itens(N)
    primeiro = _parcial(i2, "1")
    assert _componentes(primeiro) == (D("25.00"), D("1.25"), D("5.00"))
    assert sum(_componentes(primeiro), D("0.00")) == D("31.25")
    segundo = _parcial(i1, "1")
    assert _componentes(segundo) == (D("25.00"), D("1.25"), D("5.00"))
    assert acumulado_do_pedido(pedido) == (D("50.00"), D("2.50"), D("10.00"))


def test_item_de_muitas_unidades_gera_parcela_pequena(relogio: RelogioControlado) -> None:  # A-6
    _, (item,) = pedido_pago_com_itens(("100.00", "5.00", "20.00", [Item("100.00", "50", "1")]))
    registrado = _parcial(item, "1")
    assert _componentes(registrado) == (D("2.00"), D("0.10"), D("0.40"))


def test_integral_devolve_o_restante_de_cada_item_e_componente(
    relogio: RelogioControlado,
) -> None:  # A-7
    pedido, (i1, i2) = pedido_pago_com_itens(N)
    _parcial(i2, "1")
    registrado = _integral(pedido)
    linhas = {
        linha.item_id: (linha.quantidade, linha.valor) for linha in registrado.reembolso.itens.all()
    }
    assert linhas == {i1.pk: (D("1.000"), D("25.00")), i2.pk: (D("2.000"), D("50.00"))}
    assert _componentes(registrado) == (D("75.00"), D("3.75"), D("15.00"))
    assert acumulado_do_pedido(pedido) == (D("100.00"), D("5.00"), D("20.00"))


@pytest.mark.parametrize("quantidade", ["0.3", "0", "-0.25", "0.2501"])
def test_quantidade_invalida_e_recusada(relogio: RelogioControlado, quantidade: str) -> None:  # A-8
    _, (item,) = pedido_pago_com_itens(K)
    antes = _total_de_registros()
    with pytest.raises(ReembolsoRecusado, match="quantidade inválida"):
        _parcial(item, quantidade)
    assert _total_de_registros() == antes


def test_cada_devolucao_e_um_registro_separado_e_o_pedido_nao_muda(
    relogio: RelogioControlado,
) -> None:  # A-9
    pedido, (item,) = pedido_pago_com_itens(K)
    antes_do_pedido = Pedido.objects.values().get(pk=pedido.pk)
    antes_do_item = ItemDoPedido.objects.values().get(pk=item.pk)
    for _ in range(4):
        _parcial(item, "0.25")
    reembolsos = list(Reembolso.objects.filter(pedido=pedido).order_by("pk"))
    assert len(reembolsos) == 4
    for reembolso in reembolsos:
        (linha,) = reembolso.itens.all()
        assert (linha.item_id, linha.quantidade) == (item.pk, D("0.250"))
    assert Pedido.objects.values().get(pk=pedido.pk) == antes_do_pedido
    assert ItemDoPedido.objects.values().get(pk=item.pk) == antes_do_item
    assert Pedido.objects.count() == 1
    assert ItemDoPedido.objects.count() == 1


def test_o_reembolso_gera_a_obrigacao_financiada_pela_custodia(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-10
    pedido = pedido_composto(ContaFactory.create())  # 100,00 + 5,00 + 20,00
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    simulador_pagamentos.aprovar(id_externo)
    sincronizar(id_externo)
    _, i2 = _itens_de_n(pedido)
    registrado = _parcial(i2, "1")
    obrigacao = registrado.obrigacao
    assert obrigacao is not None
    assert (obrigacao.origem_tipo, obrigacao.origem_id) == (
        "financeiro.reembolso",
        str(registrado.reembolso.pk),
    )
    assert obrigacao.motivo == OC
    assert (obrigacao.produtos, obrigacao.servico, obrigacao.frete) == (
        D("25.00"),
        D("1.25"),
        D("5.00"),
    )
    assert registrado.sem_cobertura == D("0.00")
    assert saldo(conta_da_obrigacao(obrigacao)) == D("31.25")
    assert obrigacao.depois_da_apuracao is False


def _itens_de_n(pedido: Pedido) -> list[ItemDoPedido]:
    return itens_do_pedido(pedido, N[3])


def test_mesma_chave_e_mesmo_conteudo_devolve_o_mesmo_reembolso(
    relogio: RelogioControlado,
) -> None:  # A-11
    _, (item,) = pedido_pago_com_itens(K)
    primeira = _parcial(item, "0.25", chave="oc-1")
    antes = _total_de_registros()
    segunda = _parcial(item, "0.25", chave="oc-1")
    assert segunda.reembolso.pk == primeira.reembolso.pk
    assert segunda.obrigacao is not None
    assert primeira.obrigacao is not None
    assert segunda.obrigacao.pk == primeira.obrigacao.pk
    assert _total_de_registros() == antes
    with pytest.raises(ReembolsoConflitante):
        _parcial(item, "0.50", chave="oc-1")
    assert _total_de_registros() == antes


def test_so_pedido_pago_recebe_reembolso(relogio: RelogioControlado) -> None:  # A-12
    aguardando = pedido_composto(ContaFactory.create(), *K[:3])
    (item_a,) = itens_do_pedido(aguardando, K[3])
    cancelado = pedido_composto(ContaFactory.create(), *K[:3])
    (item_c,) = itens_do_pedido(cancelado, K[3])
    cancelar_direto(cancelado)
    antes = _total_de_registros()
    for pedido, item in ((aguardando, item_a), (cancelado, item_c)):
        with pytest.raises(ReembolsoRecusado, match="o pedido não está pago"):
            _parcial(item, "0.25")
        with pytest.raises(ReembolsoRecusado, match="o pedido não está pago"):
            _integral(pedido)
    assert _total_de_registros() == antes


def test_integral_sem_nada_a_devolver_devolve_none(relogio: RelogioControlado) -> None:  # A-13
    pedido, (item,) = pedido_pago_com_itens(K)
    for _ in range(4):
        _parcial(item, "0.25")
    antes = _total_de_registros()
    assert _integral(pedido) is None
    assert _total_de_registros() == antes


def test_motivo_fora_da_lista_e_recusado(relogio: RelogioControlado) -> None:  # A-14
    _, (item,) = pedido_pago_com_itens(K)
    antes = _total_de_registros()
    with pytest.raises(ValueError, match="motivo"), transaction.atomic():
        reembolso_parcial(
            item, D("0.25"), chave=chave_nova(), motivo="porque_sim", autor=administrador()
        )
    assert _total_de_registros() == antes


def test_pedido_sem_frete_nunca_devolve_frete(relogio: RelogioControlado) -> None:  # A-17
    pedido, (item,) = pedido_pago_com_itens(("10.00", "0.50", "0.00", [Item("10.00", "2", "1")]))
    primeiro = _parcial(item, "1")
    segundo = _integral(pedido)
    assert primeiro.reembolso.frete == D("0.00")
    assert segundo.reembolso.frete == D("0.00")
    assert primeiro.obrigacao is not None
    assert segundo.obrigacao is not None
    assert primeiro.obrigacao.frete == D("0.00")
    assert segundo.obrigacao.frete == D("0.00")
