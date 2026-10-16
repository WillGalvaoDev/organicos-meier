"""E02-09: normalização do telefone brasileiro (acceptance A-4 e A-5)."""

import pytest

from apps.contas.perfil import TelefoneInvalido, normalizar_telefone


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("(21) 99999-8888", "+5521999998888"),
        ("21999998888", "+5521999998888"),
        ("+55 21 99999-8888", "+5521999998888"),
        ("5521999998888", "+5521999998888"),
        ("2199998888", "+552199998888"),
        ("  (21) 9999-8888  ", "+552199998888"),
        ("+552199998888", "+552199998888"),
        ("55 21 99999-8888", "+5521999998888"),
        ("(55) 99999-8888", "+5555999998888"),  # DDD 55 (RS) não é confundido com o país
    ],
)
def test_telefone_valido_vira_e164_brasileiro(entrada: str, esperado: str) -> None:  # A-4
    assert normalizar_telefone(entrada) == esperado


@pytest.mark.parametrize("vazio", ["", "   ", None])
def test_telefone_vazio_remove_o_telefone(vazio: str | None) -> None:
    assert normalizar_telefone(vazio) is None


@pytest.mark.parametrize(
    "entrada",
    [
        "099999888",
        "+1 212 555 0100",
        "abc",
        "21 9999",
        "0 21 99999-8888",
        "2199999888877",
        "21-99999-8888-1",
        "+55 (21) 99999-88x8",
        "21+999998888",
        "++5521999998888",
    ],
)
def test_telefone_invalido_e_recusado(entrada: str) -> None:  # A-5
    with pytest.raises(TelefoneInvalido):
        normalizar_telefone(entrada)


def test_normalizacao_e_idempotente() -> None:
    primeiro = normalizar_telefone("(21) 99999-8888")
    assert primeiro is not None
    assert normalizar_telefone(primeiro) == primeiro


def test_mensagem_do_erro_nao_repete_o_numero() -> None:
    with pytest.raises(TelefoneInvalido) as erro:
        normalizar_telefone("099999888")
    assert "099999888" not in str(erro.value)
