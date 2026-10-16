"""Estratégias do hypothesis para e-mails com variações de caixa e espaços (E02-10, T-37)."""

from hypothesis import strategies as st

_LOCAL = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=2, max_size=12)
_ROTULO = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=2, max_size=10)
_TLD = st.sampled_from(["com", "com.br", "org", "net"])


@st.composite
def enderecos(draw: st.DrawFn) -> tuple[str, str, str]:
    """(normalizado, variação com caixa e espaços, alias com `+` do mesmo usuário)."""
    local = draw(_LOCAL)
    dominio = f"{draw(_ROTULO)}.{draw(_TLD)}"
    normalizado = f"{local}@{dominio}"
    variado = "".join(draw(st.sampled_from([c.lower(), c.upper()])) for c in normalizado)
    esquerda = draw(st.text(alphabet=" \t", max_size=3))
    direita = draw(st.text(alphabet=" \t", max_size=3))
    alias = f"{local}+{draw(st.text(alphabet='abc123', min_size=1, max_size=4))}@{dominio}"
    return normalizado, f"{esquerda}{variado}{direita}", alias
