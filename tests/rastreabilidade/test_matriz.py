"""E16-07: a matriz de rastreabilidade cenário -> afirmações -> testes (acceptance A-1 a A-17).

Os casos negativos montam matrizes e arquivos de teste de exemplo aqui mesmo e os passam à função
de conferência, que lê as árvores de sintaxe dos arquivos de `tests/` sem importar nem rodar nada.
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
Afirmacoes = dict[str, list[str]]


def _completa() -> tuple[dict[int, Afirmacoes], dict[str, Afirmacoes]]:
    """Uma matriz válida: todas as entradas com uma afirmação que aponta para um teste real."""
    cenarios = {n: {f"afirmação do cenário {n}": [REAL]} for n in range(1, 120)}
    tecnicos = {f"T-{n}": {f"afirmação de T-{n}": [REAL]} for n in range(1, 56)}
    return cenarios, tecnicos


def _arquivo(raiz: Path, nome: str, conteudo: str) -> str:
    """Grava `tests/<nome>` em `raiz` e devolve o início da referência (`tests/<nome>::`)."""
    arquivo = raiz / "tests" / nome
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(conteudo, encoding="utf-8")
    return f"tests/{nome}::"


def _problemas_de(raiz: Path, referencia: str) -> list[str]:
    cenarios, tecnicos = _completa()
    cenarios[1] = {"afirmação": [referencia]}
    return [p for p in conferir(cenarios, tecnicos, raiz=raiz) if p.startswith("cenário 1:")]


def test_a_matriz_entregue_e_valida() -> None:  # A-1
    assert sorted(matriz.CENARIOS) == list(range(1, 120))
    assert sorted(matriz.TECNICOS, key=lambda k: int(k[2:])) == [f"T-{n}" for n in range(1, 56)]
    for entrada in (*matriz.CENARIOS.values(), *matriz.TECNICOS.values()):
        assert entrada
        for texto, testes in entrada.items():
            assert texto.strip()
            assert testes
    assert conferir(matriz.CENARIOS, matriz.TECNICOS) == []


def test_chaves_faltando_ou_sobrando() -> None:  # A-2
    cenarios, tecnicos = _completa()
    del cenarios[42]
    cenarios[120] = {"x": [REAL]}
    tecnicos["T-56"] = {"x": [REAL]}
    problemas = " | ".join(conferir(cenarios, tecnicos))
    assert "42" in problemas
    assert "faltando" in problemas
    assert "120" in problemas
    assert "sobrando" in problemas
    assert "T-56" in problemas


def test_referencias_invalidas() -> None:  # A-3
    cenarios, tecnicos = _completa()
    cenarios[1] = {"a": ["tests/tecnicos/nao_existe.py::test_x"]}
    cenarios[2] = {"a": ["tests/tecnicos/test_nucleo_tempo.py::test_que_nao_existe"]}
    cenarios[3] = {"a": ["tests/tecnicos/test_nucleo_tempo.py::_auxiliar_sem_prefixo_test"]}
    problemas = conferir(cenarios, tecnicos)
    texto = " | ".join(problemas)
    assert "nao_existe.py" in texto
    assert "test_que_nao_existe" in texto
    assert "_auxiliar_sem_prefixo_test" in texto
    assert len(problemas) == 3


def test_teste_pulado_simples_e_recusado(tmp_path: Path) -> None:  # A-4
    ref = _arquivo(
        tmp_path,
        "test_pulado.py",
        "import pytest\n\n"
        "@pytest.mark.skip(reason='x')\n"
        "def test_pulado(): ...\n\n"
        "@pytest.mark.skipif(True, reason='x')\n"
        "def test_pulado_sempre(): ...\n",
    )
    assert any("skip" in p for p in _problemas_de(tmp_path, ref + "test_pulado"))
    assert any("skipif" in p for p in _problemas_de(tmp_path, ref + "test_pulado_sempre"))


def test_referencia_repetida_na_mesma_afirmacao() -> None:  # A-5
    cenarios, tecnicos = _completa()
    cenarios[7] = {"a": [REAL, REAL]}
    assert any("repetida" in p and REAL in p for p in conferir(cenarios, tecnicos))


def test_metodo_de_classe_de_teste_e_aceito(tmp_path: Path) -> None:  # A-6
    ref = _arquivo(tmp_path, "test_classe.py", "class TestAlgo:\n    def test_metodo(self): ...\n")
    assert _problemas_de(tmp_path, ref + "TestAlgo::test_metodo") == []


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
    cenarios[999] = {"x": [REAL]}
    with pytest.raises(ValueError, match="999"):
        gerar_documento(cenarios, tecnicos)


# --- correção E16-R06: a referência precisa ser coletável e executável pelo pytest ---------------


def test_referencias_fora_da_coleta(tmp_path: Path) -> None:  # A-12
    fora = _arquivo(
        tmp_path, "test_exemplo.py", "class ForaDaColeta:\n    def test_exemplo(self): ...\n"
    )
    com_init = _arquivo(
        tmp_path,
        "test_com_init.py",
        "class TestComInit:\n    def __init__(self): ...\n    def test_exemplo(self): ...\n",
    )
    modulo = _arquivo(
        tmp_path, "test_modulo_desligado.py", "__test__ = False\n\ndef test_exemplo(): ...\n"
    )
    nome = _arquivo(tmp_path, "exemplo.py", "def test_exemplo(): ...\n")
    casos = {
        fora + "ForaDaColeta::test_exemplo": "Test",
        com_init + "TestComInit::test_exemplo": "__init__",
        modulo + "test_exemplo": "__test__",
        nome + "test_exemplo": "nome do arquivo",
    }
    for referencia, motivo in casos.items():
        problemas = _problemas_de(tmp_path, referencia)
        assert problemas, referencia
        assert motivo in problemas[0], (referencia, problemas)


@pytest.mark.parametrize(
    ("marca", "esperado"),
    [
        ('@pytest.mark.skipif(condition=True, reason="sempre")', "skipif"),
        ('@pytest.mark.skipif(os.environ.get("CI") == "true", reason="no CI")', "skipif"),
        ("@pytest.mark.skipif(\"sys.platform == 'linux'\")", "skipif"),
        ("@pytest.mark.xfail", "xfail"),
        ('@pytest.mark.xfail(strict=True, reason="x")', "xfail"),
    ],
)
def test_marcas_de_pulo_e_falha_esperada_no_decorador(
    tmp_path: Path, marca: str, esperado: str
) -> None:  # A-13
    ref = _arquivo(
        tmp_path,
        "test_marca.py",
        f"import os\nimport pytest\n\n{marca}\ndef test_exemplo(): ...\n",
    )
    problemas = _problemas_de(tmp_path, ref + "test_exemplo")
    assert problemas
    assert esperado in problemas[0]


@pytest.mark.parametrize(
    "conteudo",
    [
        "import pytest\n\npytestmark: list = [pytest.mark.skip]\n\ndef test_exemplo(): ...\n",
        "import pytest\n\npytestmark = pytest.mark.skip\n\ndef test_exemplo(): ...\n",
        "import pytest as pt\n\n@pt.mark.skip\ndef test_exemplo(): ...\n",
        'from pytest import mark\n\n@mark.skipif(True, reason="x")\ndef test_exemplo(): ...\n',
        'import pytest\n\ndef test_exemplo():\n    pytest.skip("x")\n',
        'import pytest\n\ndef test_exemplo():\n    pytest.xfail("x")\n',
        'from pytest import skip\n\ndef test_exemplo():\n    skip("x")\n',
        'import pytest\n\npytest.importorskip("modulo_ausente")\n\ndef test_exemplo(): ...\n',
        "import pytest\n\n@pytest.mark.skip\nclass TestPulada:\n    def test_exemplo(self): ...\n",
    ],
)
def test_outras_formas_de_pulo(tmp_path: Path, conteudo: str) -> None:  # A-13
    ref = _arquivo(tmp_path, "test_forma.py", conteudo)
    nome = "TestPulada::test_exemplo" if "TestPulada" in conteudo else "test_exemplo"
    assert _problemas_de(tmp_path, ref + nome), conteudo


def test_formas_aceitas(tmp_path: Path) -> None:  # A-14
    ref = _arquivo(
        tmp_path,
        "test_aceitas.py",
        "import pytest\n\n"
        '@pytest.mark.skipif(False, reason="nunca")\n'
        "def test_sem_pulo(): ...\n\n"
        "@pytest.mark.skip\n"
        "def test_repetida(): ...\n\n"
        "def test_repetida(): ...  # a última definição vale\n\n"
        "class TestValida:\n    def test_metodo(self): ...\n",
    )
    for nome in ("test_sem_pulo", "test_repetida", "TestValida::test_metodo"):
        assert _problemas_de(tmp_path, ref + nome) == [], nome


def test_a_ultima_definicao_pulada_e_recusada(tmp_path: Path) -> None:  # A-14 (inverso)
    ref = _arquivo(
        tmp_path,
        "test_ultima.py",
        "import pytest\n\ndef test_repetida(): ...\n\n"
        "@pytest.mark.skip\ndef test_repetida(): ...\n",
    )
    assert _problemas_de(tmp_path, ref + "test_repetida")


# --- correção E16-R05: a matriz tem uma lista de afirmações por entrada --------------------------


def test_afirmacoes_mal_formadas() -> None:  # A-15
    cenarios, tecnicos = _completa()
    cenarios[1] = {}
    cenarios[2] = {"": [REAL]}
    cenarios[3] = {"afirmação": []}
    cenarios[4] = {"afirmação": [REAL, REAL]}
    cenarios[5] = {"a": [REAL], "b": [REAL]}  # o mesmo teste em afirmações diferentes: aceito
    problemas = conferir(cenarios, tecnicos)
    for numero in (1, 2, 3, 4):
        assert any(p.startswith(f"cenário {numero}:") for p in problemas), numero
    assert not any(p.startswith("cenário 5:") for p in problemas)


def test_o_cenario_2_tem_as_seis_afirmacoes() -> None:  # A-16
    afirmacoes = matriz.CENARIOS[2]
    assert len(afirmacoes) == 6
    assert all(testes for testes in afirmacoes.values())
    suspensas = [t for texto, t in afirmacoes.items() if "suspens" in texto.lower()]
    assert len(suspensas) == 2


def test_t40_tem_duas_afirmacoes() -> None:  # A-17 (estrutura)
    assert len(matriz.TECNICOS["T-40"]) == 2
