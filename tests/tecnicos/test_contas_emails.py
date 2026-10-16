"""E02-01: normalização única de e-mail (acceptance A-1 a A-5)."""

from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from apps.contas.emails import EmailInvalido, normalizar_email


@pytest.mark.parametrize("entrada", ["  Ana@Exemplo.com ", "ANA@EXEMPLO.COM", "ana@exemplo.com"])
def test_normalizar_email_ignora_caixa_e_espacos_nas_pontas(entrada: str) -> None:  # A-1
    assert normalizar_email(entrada) == "ana@exemplo.com"


@pytest.mark.parametrize("entrada", ["usuario+teste@gmail.com", "u.suario@gmail.com"])
def test_normalizar_email_nao_altera_aliases(entrada: str) -> None:  # A-2
    assert normalizar_email(entrada) == entrada
    assert normalizar_email(entrada) != "usuario@gmail.com"


@pytest.mark.parametrize(
    "entrada",
    ["", "   ", "semarroba", "a@@b.com", "ana @x.com", None, 123],
)
def test_normalizar_email_recusa_entradas_invalidas(entrada: Any) -> None:  # A-3
    with pytest.raises(EmailInvalido):
        normalizar_email(entrada)


def test_normalizar_email_mensagem_nao_repete_o_endereco() -> None:
    with pytest.raises(EmailInvalido) as erro:
        normalizar_email("segredo@@exemplo.com")
    assert "segredo" not in str(erro.value)


_LOCAL = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789._-", min_size=1, max_size=20
).filter(lambda t: not t.startswith(".") and not t.endswith(".") and ".." not in t)
_DOMINIO = st.builds(
    lambda rotulo, tld: f"{rotulo}.{tld}",
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=15),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=2, max_size=6),
)
_EMAILS = st.builds(lambda local, dominio: f"{local}@{dominio}", _LOCAL, _DOMINIO)


@st.composite
def _variacoes(draw: st.DrawFn) -> tuple[str, str]:
    base = draw(_EMAILS)
    variado = "".join(draw(st.sampled_from([c.lower(), c.upper()])) for c in base)
    pontas_esq = draw(st.text(alphabet=" \t\n", max_size=3))
    pontas_dir = draw(st.text(alphabet=" \t\n", max_size=3))
    return base, f"{pontas_esq}{variado}{pontas_dir}"


@given(_variacoes())
def test_normalizar_email_propriedade_variacoes_e_idempotencia(par: tuple[str, str]) -> None:  # A-4
    base, variado = par
    normalizado = normalizar_email(variado)
    assert normalizado == normalizar_email(base)
    assert normalizar_email(normalizado) == normalizado


@given(_EMAILS, st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=8))
def test_normalizar_email_propriedade_alias_continua_distinto(
    email: str, etiqueta: str
) -> None:  # A-5
    usuario, dominio = email.split("@")
    alias = f"{usuario}+{etiqueta}@{dominio}"
    assert normalizar_email(alias) != normalizar_email(email)
