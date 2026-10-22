"""E08-01: cálculo dos valores da cobrança (acceptance A-1 a A-10 e A-12)."""

import random
from decimal import Decimal
from typing import Any

import pytest

from apps.pedidos.calculo import (
    TAXA_DE_SERVICO,
    CobrancaDoComprador,
    CompradorACobrar,
    ItemACobrar,
    calcular_cobranca,
)

D = Decimal


def _item(produto: int, preco: str, quantidade: str = "1") -> ItemACobrar:
    return ItemACobrar(produto, D(preco), D(quantidade))


def _comprador(comprador: int, *itens: ItemACobrar) -> CompradorACobrar:
    return CompradorACobrar(comprador, tuple(itens))


def _por_comprador(resultado: list[CobrancaDoComprador]) -> dict[int, CobrancaDoComprador]:
    return {c.comprador_id: c for c in resultado}


def _arranjo_a1() -> list[CompradorACobrar]:
    return [_comprador(1, _item(10, "100.00")), _comprador(2, _item(10, "300.00"))]


@pytest.mark.acceptance
def test_cobranca_rateia_o_frete_pelos_produtos() -> None:  # A-1, cenário 10
    c1, c2 = calcular_cobranca(_arranjo_a1(), D("40.00"))
    assert (c1.comprador_id, c1.produtos, c1.servico, c1.frete, c1.total) == (
        1,
        D("100.00"),
        D("5.00"),
        D("10.00"),
        D("115.00"),
    )
    assert (c2.comprador_id, c2.produtos, c2.servico, c2.frete, c2.total) == (
        2,
        D("300.00"),
        D("15.00"),
        D("30.00"),
        D("345.00"),
    )


@pytest.mark.acceptance
def test_subtotal_arredondado_por_item() -> None:  # A-2, T-39, cenários 88 e 89
    (cobranca,) = calcular_cobranca(
        [
            _comprador(
                1,
                _item(1, "7.99", "0.250"),
                _item(2, "2.50", "0.250"),
                _item(3, "12.99", "0.350"),
            )
        ],
        D("0.00"),
    )
    assert [i.subtotal for i in cobranca.itens] == [D("2.00"), D("0.63"), D("4.55")]


def test_produtos_soma_os_subtotais_ja_arredondados() -> None:  # A-3
    (cobranca,) = calcular_cobranca(
        [_comprador(1, _item(1, "2.50", "0.250"), _item(2, "2.50", "0.250"))], D("0.00")
    )
    assert cobranca.produtos == D("1.26")


def test_subtotal_e_arredondado_uma_vez_so() -> None:  # A-4, cenário 64
    (cobranca,) = calcular_cobranca([_comprador(1, _item(1, "12.99", "0.350"))], D("0.00"))
    assert cobranca.itens[0].subtotal == D("4.55")  # a partir de 4,5465
    assert cobranca.itens[0].preco_unitario == D("12.99")
    assert cobranca.itens[0].quantidade == D("0.350")


def test_centavo_do_frete_vai_ao_menor_comprador_no_empate() -> None:  # A-5
    compradores = [_comprador(i, _item(1, "10.00")) for i in (1, 2, 3)]
    resultado = calcular_cobranca(compradores, D("10.00"))
    assert [c.frete for c in resultado] == [D("3.34"), D("3.33"), D("3.33")]
    assert sum(c.frete for c in resultado) == D("10.00")


def test_frete_pelo_maior_resto() -> None:  # A-6
    compradores = [
        _comprador(1, _item(1, "0.01")),
        _comprador(2, _item(1, "0.01")),
        _comprador(3, _item(1, "99.98")),
    ]
    resultado = calcular_cobranca(compradores, D("0.05"))
    # truncado: 0,00 / 0,00 / 0,04; falta 0,01, que vai ao de maior resto (o terceiro)
    assert [c.frete for c in resultado] == [D("0.00"), D("0.00"), D("0.05")]
    assert sum(c.frete for c in resultado) == D("0.05")


def test_resultado_nao_depende_da_ordem_da_entrada() -> None:  # A-7
    direto = calcular_cobranca(_arranjo_a1(), D("40.00"))
    invertido = calcular_cobranca(list(reversed(_arranjo_a1())), D("40.00"))
    assert direto
    assert invertido == direto
    assert [c.comprador_id for c in invertido] == [1, 2]


def test_frete_zero() -> None:  # A-8
    resultado = calcular_cobranca(_arranjo_a1(), D("0.00"))
    assert [c.frete for c in resultado] == [D("0.00"), D("0.00")]
    assert [c.total for c in resultado] == [D("105.00"), D("315.00")]


def test_servico_arredonda_meio_centavo_para_cima() -> None:  # A-9
    (a,) = calcular_cobranca([_comprador(1, _item(1, "0.10"))], D("0.00"))
    (b,) = calcular_cobranca([_comprador(1, _item(1, "0.09"))], D("0.00"))
    assert a.servico == D("0.01")
    assert b.servico == D("0.00")
    assert TAXA_DE_SERVICO == D("0.05")


def test_um_comprador_so_paga_todo_o_frete() -> None:
    (c,) = calcular_cobranca([_comprador(7, _item(1, "20.00"))], D("12.34"))
    assert c.frete == D("12.34")
    assert c.total == D("20.00") + D("1.00") + D("12.34")


def test_itens_saem_em_ordem_de_produto() -> None:
    (c,) = calcular_cobranca([_comprador(1, _item(9, "1.00"), _item(3, "1.00"))], D("0.00"))
    assert [i.produto_id for i in c.itens] == [3, 9]


def _recusa(compradores: list[CompradorACobrar], frete: Any) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        calcular_cobranca(compradores, frete)


@pytest.mark.parametrize(
    "frete",
    [D("-0.01"), D("40.001"), 40.0, "40.00", None, D("NaN"), D("Infinity")],
)
def test_frete_invalido_e_recusado(frete: Any) -> None:  # A-10
    _recusa(_arranjo_a1(), frete)


def test_preco_invalido_e_recusado() -> None:  # A-10
    _recusa([_comprador(1, ItemACobrar(1, 10.0, D("1")))], D("0.00"))  # type: ignore[arg-type]
    _recusa([_comprador(1, _item(1, "-1.00"))], D("0.00"))
    _recusa([_comprador(1, _item(1, "1.001"))], D("0.00"))


@pytest.mark.parametrize("quantidade", ["0", "-1", "0.0001", "1.2345"])
def test_quantidade_invalida_e_recusada(quantidade: str) -> None:  # A-10
    _recusa([_comprador(1, _item(1, "10.00", quantidade))], D("0.00"))


def test_quantidade_float_e_recusada() -> None:  # A-10
    _recusa([_comprador(1, ItemACobrar(1, D("1.00"), 1.5))], D("0.00"))  # type: ignore[arg-type]


def test_estruturas_invalidas_sao_recusadas() -> None:  # A-10
    _recusa([], D("10.00"))
    _recusa([_comprador(1, _item(1, "1.00")), _comprador(1, _item(2, "1.00"))], D("0.00"))
    _recusa([_comprador(1, _item(1, "1.00"), _item(1, "2.00"))], D("0.00"))
    _recusa([_comprador(1)], D("0.00"))
    _recusa([_comprador(1, _item(1, "0.00"))], D("0.00"))  # T = 0


def test_cobranca_aleatoria_respeita_as_invariantes() -> None:  # A-12
    sorteio = random.Random(20261102)  # noqa: S311  (semente fixa de teste)
    for _ in range(200):
        compradores = []
        for comprador_id in sorteio.sample(range(1, 500), sorteio.randint(1, 30)):
            produtos = sorteio.sample(range(1, 200), sorteio.randint(1, 4))
            itens = tuple(
                ItemACobrar(
                    produto,
                    D(sorteio.randint(1, 100000)).scaleb(-2),
                    D(sorteio.randint(1, 20000)).scaleb(-3),
                )
                for produto in produtos
            )
            compradores.append(CompradorACobrar(comprador_id, itens))
        frete = D(sorteio.randint(0, 50000)).scaleb(-2)
        resultado = calcular_cobranca(compradores, frete)
        assert len(resultado) == len(compradores)
        assert sum(c.frete for c in resultado) == frete
        for cobranca in resultado:
            assert cobranca.produtos == sum(i.subtotal for i in cobranca.itens)
            assert cobranca.total == cobranca.produtos + cobranca.servico + cobranca.frete
            assert cobranca.frete >= 0
            for valor in (cobranca.produtos, cobranca.servico, cobranca.frete, cobranca.total):
                assert valor.as_tuple().exponent == -2
            for item in cobranca.itens:
                assert item.subtotal.as_tuple().exponent == -2
