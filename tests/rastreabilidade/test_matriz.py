"""E16-07: a matriz de rastreabilidade cenário -> testes (acceptance A-1 a A-9).

Os casos negativos montam matrizes de teste aqui mesmo e as passam à função de conferência, que
lê as árvores de sintaxe dos arquivos de `tests/` sem importar nem rodar nada.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from tests.rastreabilidade import matriz
from tests.rastreabilidade.conferencia import RAIZ, conferir, conferir_documento
from tests.rastreabilidade.gerar import gerar_documento

REAL = "tests/tecnicos/test_nucleo_tempo.py::test_fronteira_prazo_encerrado_exclusivo"
DOCUMENTO = RAIZ / "docs" / "rastreabilidade-fase1.md"


def _completa(**mudancas: list[str] | None) -> tuple[dict[int, list[str]], dict[str, list[str]]]:
    """Uma matriz válida (todas as chaves apontam para um teste real), com mudanças pontuais."""
    cenarios = {n: [REAL] for n in range(1, 120)}
    tecnicos = {f"T-{n}": [REAL] for n in range(1, 56)}
    for chave, valor in mudancas.items():
        alvo = tecnicos if chave.startswith("T_") else cenarios
        nome: int | str = chave.replace("T_", "T-") if chave.startswith("T_") else int(chave[1:])
        if valor is None:
            del alvo[nome]  # type: ignore[arg-type]
        else:
            alvo[nome] = valor  # type: ignore[index]
    return cenarios, tecnicos


def test_a_matriz_entregue_e_valida() -> None:  # A-1
    assert sorted(matriz.CENARIOS) == list(range(1, 120))
    assert sorted(matriz.TECNICOS, key=lambda k: int(k[2:])) == [f"T-{n}" for n in range(1, 56)]
    assert all(matriz.CENARIOS.values())
    assert all(matriz.TECNICOS.values())
    assert conferir(matriz.CENARIOS, matriz.TECNICOS) == []


def test_chaves_faltando_ou_sobrando() -> None:  # A-2
    cenarios, tecnicos = _completa(c42=None)
    cenarios[120] = [REAL]
    tecnicos["T-56"] = [REAL]
    problemas = " | ".join(conferir(cenarios, tecnicos))
    assert "42" in problemas
    assert "faltando" in problemas
    assert "120" in problemas
    assert "sobrando" in problemas
    assert "T-56" in problemas


def test_referencias_invalidas() -> None:  # A-3
    cenarios, tecnicos = _completa(
        c1=["tests/tecnicos/nao_existe.py::test_x"],
        c2=["tests/tecnicos/test_nucleo_tempo.py::test_que_nao_existe"],
        c3=["tests/tecnicos/test_nucleo_tempo.py::_auxiliar_que_nao_comeca_com_test"],
    )
    problemas = conferir(cenarios, tecnicos)
    texto = " | ".join(problemas)
    assert "nao_existe.py" in texto
    assert "test_que_nao_existe" in texto
    assert "_auxiliar_que_nao_comeca_com_test" in texto
    assert len(problemas) == 3


def test_teste_pulado_e_recusado(tmp_path: Path) -> None:  # A-4
    arquivo = tmp_path / "tests" / "tecnicos" / "test_pulado.py"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text(
        "import pytest\n\n"
        "@pytest.mark.skip(reason='x')\n"
        "def test_pulado(): ...\n\n"
        "@pytest.mark.skipif(True, reason='x')\n"
        "def test_pulado_sempre(): ...\n\n"
        "@pytest.mark.skipif(False, reason='x')\n"
        "def test_nao_pulado(): ...\n",
        encoding="utf-8",
    )
    ref = "tests/tecnicos/test_pulado.py::"
    cenarios, tecnicos = _completa(c1=[ref + "test_pulado"], c2=[ref + "test_pulado_sempre"])
    texto = " | ".join(conferir(cenarios, tecnicos, raiz=tmp_path))
    assert "test_pulado" in texto
    assert "pulado" in texto
    assert "test_pulado_sempre" in texto
    assert "test_nao_pulado" not in texto


def test_referencia_repetida() -> None:  # A-5
    cenarios, tecnicos = _completa(c7=[REAL, REAL])
    problemas = conferir(cenarios, tecnicos)
    assert any("repetida" in p and REAL in p for p in problemas)


def test_metodo_de_classe_de_teste_e_aceito(tmp_path: Path) -> None:  # A-6
    arquivo = tmp_path / "tests" / "tecnicos" / "test_classe.py"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text("class TestAlgo:\n    def test_metodo(self): ...\n", encoding="utf-8")
    cenarios, tecnicos = _completa(c1=["tests/tecnicos/test_classe.py::TestAlgo::test_metodo"])
    assert conferir(cenarios, tecnicos, raiz=tmp_path) == [
        p for p in conferir(cenarios, tecnicos, raiz=tmp_path) if "test_classe.py" not in p
    ]
    assert not [p for p in conferir(cenarios, tecnicos, raiz=tmp_path) if "TestAlgo" in p]


def test_o_gerador_escreve_as_duas_tabelas(tmp_path: Path) -> None:  # A-7
    saida = tmp_path / "doc.md"
    resultado = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "tests.rastreabilidade.gerar", "--saida", str(saida)],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    texto = saida.read_text(encoding="utf-8")
    assert "## Cenários (§16)" in texto
    assert "## Testes técnicos (infraestrutura 8)" in texto
    linha_6 = next(linha for linha in texto.splitlines() if linha.startswith("| 6 |"))
    assert (
        linha_6.split("|")[2].strip().startswith("Produto de R$ 10,00, múltiplo 12 e 18 unidades")
    )
    linha_t12 = next(linha for linha in texto.splitlines() if linha.startswith("| T-12 |"))
    assert linha_t12.split("|")[2].strip() == "A3"


def test_o_documento_versionado_esta_em_dia(tmp_path: Path) -> None:  # A-8
    assert conferir_documento(DOCUMENTO, matriz.CENARIOS, matriz.TECNICOS) is None
    alterado = tmp_path / "rastreabilidade.md"
    linhas = DOCUMENTO.read_text(encoding="utf-8").splitlines()
    alterado.write_text("\n".join(linhas[:-1]) + "\n", encoding="utf-8")
    assert "desatualizado" in (conferir_documento(alterado, matriz.CENARIOS, matriz.TECNICOS) or "")


def test_cenario_sem_texto_nos_documentos_base_falha_a_geracao() -> None:  # A-9
    cenarios, tecnicos = _completa()
    cenarios[999] = [REAL]
    with pytest.raises(ValueError, match="999"):
        gerar_documento(cenarios, tecnicos)
