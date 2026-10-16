"""E01-02: conversão de entrada, arredondamento e múltiplo exato (acceptance A-1 a A-15, A-18)."""

from decimal import Decimal
from typing import Any

import pytest

from apps.nucleo.valores import (
    ValorInvalido,
    arredondar_centavos,
    dinheiro,
    eh_multiplo,
    quantidade,
)

D = Decimal


def test_conversao_dinheiro_texto_com_duas_casas() -> None:  # A-1
    assert dinheiro("7.99") == D("7.99")


def test_conversao_dinheiro_inteiro_vira_duas_casas() -> None:  # A-2
    resultado = dinheiro("8")
    assert resultado == D("8.00")
    assert str(resultado) == "8.00"


def test_conversao_dinheiro_recusa_excesso_de_casas() -> None:  # A-3
    with pytest.raises(ValorInvalido, match="casas"):
        dinheiro("7.999")


@pytest.mark.parametrize("funcao", [dinheiro, quantidade])
def test_conversao_recusa_float(funcao: Any) -> None:  # A-4
    with pytest.raises(ValorInvalido, match="tipo"):
        funcao(7.99)


@pytest.mark.parametrize(
    "entrada",
    ["", "abc", "NaN", "Infinity", "1,5", "1.000,00", True, 8],
)
def test_conversao_dinheiro_recusa_entradas_invalidas(entrada: Any) -> None:  # A-5
    with pytest.raises(ValorInvalido):
        dinheiro(entrada)


@pytest.mark.parametrize("entrada", [D("NaN"), D("Infinity"), D("-Infinity"), D("sNaN")])
def test_conversao_dinheiro_recusa_decimal_nao_finito(entrada: Decimal) -> None:
    with pytest.raises(ValorInvalido):
        dinheiro(entrada)


def test_conversao_quantidade_aceita_ate_tres_casas() -> None:  # A-6
    assert quantidade("0.25") == D("0.25")
    assert quantidade("2") == D("2")
    assert quantidade("0.125") == D("0.125")


def test_conversao_quantidade_recusa_excesso_de_casas() -> None:  # A-7
    with pytest.raises(ValorInvalido, match="casas"):
        quantidade("0.0001")


@pytest.mark.parametrize("entrada", ["", "abc", "NaN", "1,5", True, 2])
def test_conversao_quantidade_recusa_entradas_invalidas(entrada: Any) -> None:
    with pytest.raises(ValorInvalido):
        quantidade(entrada)


def test_conversao_dinheiro_notacao_com_expoente_normaliza() -> None:  # A-18
    resultado = dinheiro(D("1E+2"))
    assert resultado == D("100.00")
    assert str(resultado) == "100.00"


def test_conversao_dinheiro_aceita_zero_e_sinal() -> None:
    assert dinheiro("0") == D("0.00")
    assert dinheiro("-1.50") == D("-1.50")


def test_conversao_dinheiro_decimal_com_zeros_a_direita_nao_conta_como_casa() -> None:
    assert dinheiro(D("7.990")) == D("7.99")


def test_arredondamento_7_99_vezes_0_25() -> None:  # A-8
    assert arredondar_centavos(D("7.99") * D("0.25")) == D("2.00")


def test_arredondamento_2_50_vezes_0_25() -> None:  # A-9
    assert arredondar_centavos(D("2.50") * D("0.25")) == D("0.63")


def test_arredondamento_12_99_vezes_0_35() -> None:  # A-10
    assert arredondar_centavos(D("12.99") * D("0.35")) == D("4.55")


def test_arredondamento_idempotente() -> None:  # A-11
    primeiro = arredondar_centavos(D("0.015"))
    assert primeiro == D("0.02")
    assert arredondar_centavos(primeiro) == D("0.02")


def test_arredondamento_recusa_float() -> None:  # A-12
    with pytest.raises(ValorInvalido, match="tipo"):
        arredondar_centavos(1.5)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("valor", "passo"),
    [(D("1.25"), D("0.25")), (D("0"), D("0.25")), (D("4"), D("2"))],
)
def test_multiplo_exato_verdadeiro(valor: Decimal, passo: Decimal) -> None:  # A-13
    assert eh_multiplo(valor, passo) is True


@pytest.mark.parametrize(("valor", "passo"), [(D("1.2"), D("0.5")), (D("3"), D("2"))])
def test_multiplo_exato_falso(valor: Decimal, passo: Decimal) -> None:  # A-14
    assert eh_multiplo(valor, passo) is False


@pytest.mark.parametrize("passo", [D("0"), D("-0.25")])
def test_multiplo_passo_invalido(passo: Decimal) -> None:  # A-15
    with pytest.raises(ValorInvalido):
        eh_multiplo(D("1"), passo)


def test_multiplo_recusa_float() -> None:
    with pytest.raises(ValorInvalido, match="tipo"):
        eh_multiplo(1.25, D("0.25"))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("funcao", "entrada"),
    [
        (dinheiro, "1.00000000000000000000000000001"),
        (dinheiro, D("1.00000000000000000000000000001")),
        (quantidade, "0.25000000000000000000000000001"),
        (quantidade, D("0.25000000000000000000000000001")),
    ],
)
def test_conversao_recusa_excesso_de_casas_alem_da_precisao_do_contexto(
    funcao: Any, entrada: Any
) -> None:  # R02
    with pytest.raises(ValorInvalido, match="casas"):
        funcao(entrada)


@pytest.mark.parametrize(
    ("funcao", "entrada", "esperado"),
    [
        (dinheiro, "1.00000000000000000000000000000", D("1.00")),
        (dinheiro, D("7.990000000000000000000000000000"), D("7.99")),
        (quantidade, "0.250000000000000000000000000000", D("0.250")),
    ],
)
def test_conversao_zeros_finais_continuam_equivalentes(
    funcao: Any, entrada: Any, esperado: Decimal
) -> None:  # R02
    assert funcao(entrada) == esperado


@pytest.mark.parametrize(
    ("texto", "casas", "esperado"),
    [
        ("150,00", 2, D("150.00")),
        ("150.00", 2, D("150.00")),
        ("150", 2, D("150.00")),
        ("  0,01 ", 2, D("0.01")),
        ("0,25", 3, D("0.250")),
        ("2,5", 3, D("2.500")),
        ("0.125", 3, D("0.125")),
    ],
)
def test_leitura_digitada_aceita_virgula_ou_ponto(
    texto: str, casas: int, esperado: Decimal
) -> None:
    # E03-01: entrada de formulário
    from apps.nucleo.valores import ler_decimal_digitado

    resultado = ler_decimal_digitado(texto, casas)
    assert resultado == esperado
    assert str(resultado) == str(esperado)


@pytest.mark.parametrize(
    ("texto", "casas"),
    [
        ("1.000,00", 2),  # separador de milhar
        ("1,000.00", 2),
        ("1.000", 2),  # três casas em campo de dinheiro
        ("0,001", 2),
        ("0,0001", 3),
        ("1,2,3", 2),
        ("1..2", 2),
        ("abc", 2),
        ("", 2),
        ("   ", 2),
        ("NaN", 2),
        ("1e3", 2),
        ("-", 2),
        ("+,5", 2),
    ],
)
def test_leitura_digitada_recusa_formatos_invalidos(texto: str, casas: int) -> None:
    from apps.nucleo.valores import ler_decimal_digitado

    with pytest.raises(ValorInvalido):
        ler_decimal_digitado(texto, casas)


@pytest.mark.parametrize("entrada", [7.5, 8, True, None])
def test_leitura_digitada_recusa_tipos_que_nao_sao_texto(entrada: Any) -> None:
    from apps.nucleo.valores import ler_decimal_digitado

    with pytest.raises(ValorInvalido):
        ler_decimal_digitado(entrada, 2)
