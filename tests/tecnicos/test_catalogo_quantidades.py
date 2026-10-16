"""E03-03: incremento, múltiplo, quantidade e subtotal (acceptance A-2 a A-9)."""

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from apps.catalogo.models import Produto, Unidade
from apps.catalogo.quantidades import (
    IncrementoInvalido,
    MultiploInvalido,
    QuantidadeInvalida,
    QuantidadeRecusada,
    calcular_subtotal,
    formatar_quantidade,
    validar_incremento,
    validar_multiplo,
    validar_quantidade,
)
from apps.catalogo.servicos import criar_produto
from apps.nucleo.valores import ValorInvalido
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, FornecedorFactory, ProdutoFactory

D = Decimal


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def _dados(**campos: Any) -> dict[str, Any]:
    base = {
        "nome": "Banana",
        "descricao": "",
        "unidade": "kg",
        "incremento": "0,25",
        "preco": "7,99",
        "multiplo": "",
        "disponivel": "on",
    }
    return {**base, **campos}


def _cadastro(fornecedor_id: int) -> str:
    return f"/administracao/fornecedores/{fornecedor_id}/produtos/novo/"


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("1", D(1)), ("2", D(2)), ("0.25", D("0.25")), ("0.5", D("0.5")), ("0.001", D("0.001"))],
)
def test_incrementos_validos(entrada: str, esperado: Decimal) -> None:  # A-2, cenário 110, T-50
    assert validar_incremento(entrada) == esperado
    assert validar_incremento(D(entrada)) == esperado


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize("entrada", ["0", "-1", "0.0001", "abc", 0.25, 1])
def test_incrementos_invalidos_no_servico(entrada: Any) -> None:  # A-3, cenários 86 e 110, T-38
    with pytest.raises(IncrementoInvalido):
        validar_incremento(entrada)


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.django_db
@pytest.mark.parametrize("entrada", ["0", "-1", "0,0001", "abc"])
def test_incremento_invalido_na_tela(admin_client: Client, entrada: str) -> None:  # A-3
    fornecedor = FornecedorFactory.create()
    resposta = admin_client.post(_cadastro(fornecedor.pk), _dados(incremento=entrada))
    assert resposta.status_code == 200
    assert "incremento" in resposta.context["form"].errors
    assert Produto.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("entrada", [0.25, 1])
def test_criar_produto_recusa_incremento_float_ou_int(entrada: Any) -> None:  # A-3
    admin = ContaFactory.create(administrador=True)
    fornecedor = FornecedorFactory.create()
    with pytest.raises(IncrementoInvalido):
        criar_produto(
            admin, fornecedor, nome="X", unidade="kg", incremento=entrada, preco=D("1.00")
        )
    assert Produto.objects.count() == 0


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("incremento", "multiplo"), [("0,25", "1"), ("2", "12")], ids=["um_com_0,25", "doze_com_2"]
)
def test_multiplo_valido_no_cadastro(
    admin_client: Client, incremento: str, multiplo: str
) -> None:  # A-4, cenários 87 e 111, T-26
    fornecedor = FornecedorFactory.create()
    resposta = admin_client.post(
        _cadastro(fornecedor.pk), _dados(incremento=incremento, multiplo=multiplo)
    )
    assert resposta.status_code == 302
    assert Produto.objects.get().multiplo == D(multiplo.replace(",", "."))


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("incremento", "multiplo"),
    [("0,3", "1"), ("2", "5"), ("1", "0"), ("1", "-12")],
    ids=["um_com_0,3", "cinco_com_2", "zero", "negativo"],
)
def test_multiplo_invalido_no_cadastro(
    admin_client: Client, incremento: str, multiplo: str
) -> None:  # A-5, cenários 66, 87 e 111, T-26, T-38
    fornecedor = FornecedorFactory.create()
    resposta = admin_client.post(
        _cadastro(fornecedor.pk), _dados(incremento=incremento, multiplo=multiplo)
    )
    assert resposta.status_code == 200
    assert "multiplo" in resposta.context["form"].errors
    assert Produto.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("incremento", "multiplo"),
    [("0.3", "1"), ("2", "5"), ("1", "0"), ("1", "-12"), ("0.25", "0.9")],
)
def test_servico_recusa_multiplo_invalido(incremento: str, multiplo: str) -> None:  # A-5
    admin = ContaFactory.create(administrador=True)
    fornecedor = FornecedorFactory.create()
    with pytest.raises(MultiploInvalido):
        criar_produto(
            admin,
            fornecedor,
            nome="X",
            unidade="kg",
            incremento=incremento,
            preco=D("1.00"),
            multiplo=multiplo,
        )
    assert Produto.objects.count() == 0


@pytest.mark.parametrize(
    ("entrada", "incremento", "esperado"),
    [("1", "0.25", D(1)), ("12", "2", D(12)), ("", "2", None), (None, "2", None)],
)
def test_validar_multiplo_aceita_e_aceita_vazio(
    entrada: Any, incremento: str, esperado: Decimal | None
) -> None:  # A-4
    assert validar_multiplo(entrada, D(incremento)) == esperado


@pytest.mark.parametrize(
    ("entrada", "incremento"), [("1", "0.3"), ("5", "2"), ("0", "1"), ("-12", "1"), ("0.9", "0.25")]
)
def test_validar_multiplo_recusa(entrada: str, incremento: str) -> None:  # A-5
    with pytest.raises(MultiploInvalido):
        validar_multiplo(entrada, D(incremento))
    with pytest.raises(MultiploInvalido):
        validar_multiplo(1.0, D(incremento))


def _produto(incremento: str) -> Produto:
    return ProdutoFactory.build(incremento=D(incremento))


# (incremento, entrada aceita); (incremento, entrada recusada) — tabela da §4.2 e cenários 63/85/109
ACEITAS = [
    ("1", "12"),
    ("2", "4"),
    ("0.25", "1.25"),
    ("0.5", "2.5"),
    ("1", "3"),
    ("0.5", "1.5"),
    ("1", "2"),
    ("0.25", "0.75"),
    ("0.25", "0.2500"),
]
RECUSADAS = [
    ("1", "12.5"),
    ("2", "3"),
    ("1", "1.5"),
    ("0.5", "1.2"),
    ("1", "2.5"),
    ("0.25", "0"),
    ("0.25", "-1"),
    ("0.25", "0.2501"),
    ("0.25", 1.5),
    ("1", 2),
]


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize(("incremento", "entrada"), ACEITAS)
def test_quantidades_aceitas(incremento: str, entrada: str) -> None:  # A-6, 63/85/109, T-26/T-38
    assert validar_quantidade(_produto(incremento), entrada) == D(entrada)


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize(("incremento", "entrada"), RECUSADAS)
def test_quantidades_recusadas(incremento: str, entrada: Any) -> None:  # A-7, 63/85/109, T-26/T-38
    with pytest.raises(QuantidadeInvalida):
        validar_quantidade(_produto(incremento), entrada)


def test_as_recusas_compartilham_a_base() -> None:
    assert issubclass(IncrementoInvalido, QuantidadeRecusada)
    assert issubclass(MultiploInvalido, QuantidadeRecusada)
    assert issubclass(QuantidadeInvalida, QuantidadeRecusada)


@pytest.mark.acceptance
@pytest.mark.tecnico
@pytest.mark.parametrize(
    ("preco", "quantidade", "esperado"),
    [
        ("12.00", "1.5", D("18.00")),
        ("12.99", "0.35", D("4.55")),
        ("7.99", "0.25", D("2.00")),
        ("2.50", "0.25", D("0.63")),
    ],
)
def test_subtotal_com_um_unico_arredondamento(
    preco: str, quantidade: str, esperado: Decimal
) -> None:  # A-8, cenários 63 e 64
    resultado = calcular_subtotal(D(preco), D(quantidade))
    assert resultado == esperado
    assert resultado.as_tuple().exponent == -2


def test_subtotal_de_455_centavos() -> None:  # A-8
    assert int(calcular_subtotal(D("12.99"), D("0.35")) * 100) == 455


@pytest.mark.tecnico
@pytest.mark.parametrize(
    ("preco", "quantidade"), [(12.0, D("1.5")), (D("12.00"), 1.5), (12.0, 1.5), (12, D("1"))]
)
def test_subtotal_recusa_float_e_int(preco: Any, quantidade: Any) -> None:  # A-9, T-50
    with pytest.raises(ValorInvalido):
        calcular_subtotal(preco, quantidade)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (D("0.250"), "0,25"),
        (D("1.000"), "1"),
        (D("1.500"), "1,5"),
        (D("10.000"), "10"),
        (D("0.001"), "0,001"),
        (D("100.000"), "100"),
    ],
)
def test_formatacao_de_quantidade(valor: Decimal, esperado: str) -> None:  # A-23
    assert formatar_quantidade(valor) == esperado


def test_unidades_aceitas_sao_as_cinco_da_especificacao() -> None:
    assert {u.value for u in Unidade} == {"unidade", "pacote", "caixa", "kg", "litro"}
