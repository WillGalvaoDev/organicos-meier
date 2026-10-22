"""E08-01: varredura estática de `float` em dinheiro e quantidade (acceptance A-11, T-39)."""

from pathlib import Path

import pytest

from tests.apoio.varredura_float import (
    MODULOS_DE_DINHEIRO,
    RAIZ,
    arquivos_dos_modulos,
    varrer_arquivo,
    varrer_modulos_de_dinheiro,
)


@pytest.mark.acceptance
def test_modulos_de_dinheiro_nao_usam_float() -> None:  # A-11, T-39
    assert varrer_modulos_de_dinheiro() == []


def test_a_varredura_cobre_os_modulos_e_ignora_as_migracoes() -> None:  # A-11
    arquivos = arquivos_dos_modulos()
    assert RAIZ / "apps/nucleo/valores.py" in arquivos
    assert RAIZ / "apps/pedidos/calculo.py" in arquivos
    assert RAIZ / "apps/pagamentos/chamadas.py" in arquivos
    assert not [a for a in arquivos if "migrations" in a.parts]
    assert not [a for a in arquivos if "contas" in a.parts]
    assert len(MODULOS_DE_DINHEIRO) == 8


def test_a_varredura_acusa_float_com_arquivo_e_linha(tmp_path: Path) -> None:  # A-11
    arquivo = tmp_path / "exemplo.py"
    arquivo.write_text("x = 1.5\nz = float(y)\nc = models.FloatField()\nok = 1\n", encoding="utf-8")
    achadas = varrer_arquivo(arquivo)
    assert [(a.linha, a.tipo) for a in achadas] == [
        (1, "literal float"),
        (2, "chamada a float"),
        (3, "FloatField"),
    ]
    assert all(a.arquivo == arquivo for a in achadas)
    assert f"{arquivo}:1:" in str(achadas[0])


def test_a_varredura_nao_acusa_inteiros_decimais_nem_anotacoes(tmp_path: Path) -> None:  # A-11
    arquivo = tmp_path / "limpo.py"
    arquivo.write_text(
        "from decimal import Decimal\n"
        "a = 1\n"
        "b = Decimal('1.5')\n"
        "def f(x: float) -> int:\n    return 1\n",
        encoding="utf-8",
    )
    assert varrer_arquivo(arquivo) == []
