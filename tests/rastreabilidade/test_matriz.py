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
Afirmacoes = dict[str, dict[str, str]]
PROVA = "A fronteira de 24 h: `assert prazo_encerrado(limite, limite) is True`."


def _completa() -> tuple[dict[int, Afirmacoes], dict[str, Afirmacoes]]:
    """Uma matriz válida: todas as entradas com uma afirmação que aponta para um teste real."""
    cenarios = {n: {f"afirmação do cenário {n}": {REAL: PROVA}} for n in range(1, 120)}
    tecnicos = {f"T-{n}": {f"afirmação de T-{n}": {REAL: PROVA}} for n in range(1, 56)}
    return cenarios, tecnicos


def _arquivo(raiz: Path, nome: str, conteudo: str) -> str:
    """Grava `tests/<nome>` em `raiz` e devolve o início da referência (`tests/<nome>::`)."""
    arquivo = raiz / "tests" / nome
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(conteudo, encoding="utf-8")
    return f"tests/{nome}::"


def _problemas_de(raiz: Path, referencia: str) -> list[str]:
    cenarios, tecnicos = _completa()
    cenarios[1] = {"afirmação": {referencia: "x"}}
    return [
        p
        for p in conferir(cenarios, tecnicos, raiz=raiz)
        if p.startswith("cenário 1:") and "prova inválida" not in p
    ]


def test_a_matriz_entregue_e_valida() -> None:  # A-1
    assert sorted(matriz.CENARIOS) == list(range(1, 120))
    assert sorted(matriz.TECNICOS, key=lambda k: int(k[2:])) == [f"T-{n}" for n in range(1, 56)]
    for entrada in (*matriz.CENARIOS.values(), *matriz.TECNICOS.values()):
        assert entrada
        for texto, provas in entrada.items():
            assert texto.strip()
            assert provas
    assert conferir(matriz.CENARIOS, matriz.TECNICOS) == []


def test_chaves_faltando_ou_sobrando() -> None:  # A-2
    cenarios, tecnicos = _completa()
    del cenarios[42]
    cenarios[120] = {"x": {REAL: PROVA}}
    tecnicos["T-56"] = {"x": {REAL: PROVA}}
    problemas = " | ".join(conferir(cenarios, tecnicos))
    assert "42" in problemas
    assert "faltando" in problemas
    assert "120" in problemas
    assert "sobrando" in problemas
    assert "T-56" in problemas


def test_referencias_invalidas() -> None:  # A-3
    cenarios, tecnicos = _completa()
    cenarios[1] = {"a": {"tests/tecnicos/nao_existe.py::test_x": "x"}}
    cenarios[2] = {"a": {"tests/tecnicos/test_nucleo_tempo.py::test_que_nao_existe": "x"}}
    cenarios[3] = {"a": {"tests/tecnicos/test_nucleo_tempo.py::_auxiliar_sem_prefixo_test": "x"}}
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
    cenarios[999] = {"x": {REAL: PROVA}}
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
    cenarios[2] = {"": {REAL: PROVA}}
    cenarios[3] = {"afirmação": {}}
    cenarios[5] = {"a": {REAL: PROVA}, "b": {REAL: PROVA}}  # o mesmo teste em duas afirmações
    problemas = conferir(cenarios, tecnicos)
    for numero in (1, 2, 3):
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


# --- correção residual E16-R06: formas que a árvore de sintaxe não prova que rodam (A-20 a A-23) --

FONTES_DO_REVISOR = {
    "pytestmark da classe": (
        "import pytest\n"
        "class TestExemplo:\n"
        '    pytestmark = pytest.mark.skip(reason="pulado")\n'
        "    def test_exemplo(self): assert False\n",
        "TestExemplo::test_exemplo",
        "pytestmark da classe TestExemplo",
    ),
    "skipif com duas condições": (
        "import pytest\n"
        '@pytest.mark.skipif(False, True, reason="segunda verdadeira")\n'
        "def test_exemplo(): assert False\n",
        "test_exemplo",
        "skipif",
    ),
    "__test__ anotado": (
        "__test__: bool = False\ndef test_exemplo(): assert False\n",
        "test_exemplo",
        "__test__",
    ),
}
FONTES_RECUSADAS = {
    "pytestmark anotado de classe com xfail": (
        "import pytest\n"
        "class TestExemplo:\n"
        "    pytestmark: list = [pytest.mark.xfail]\n"
        "    def test_exemplo(self): assert False\n",
        "TestExemplo::test_exemplo",
        "pytestmark da classe TestExemplo",
    ),
    "skipif sem condição": (
        "import pytest\n@pytest.mark.skipif()\ndef test_exemplo(): assert False\n",
        "test_exemplo",
        "skipif",
    ),
    "skipif com condition=True depois de False": (
        "import pytest\n"
        "@pytest.mark.skipif(False, condition=True)\n"
        "def test_exemplo(): assert False\n",
        "test_exemplo",
        "skipif",
    ),
    "__test__ com nome na classe": (
        "HABILITADO = False\n"
        "class TestExemplo:\n"
        "    __test__ = HABILITADO\n"
        "    def test_exemplo(self): assert False\n",
        "TestExemplo::test_exemplo",
        "__test__",
    ),
    "pytestmark com atribuição aumentada": (
        "import pytest\n"
        "pytestmark = []\n"
        "pytestmark += [pytest.mark.skip]\n"
        "def test_exemplo(): assert False\n",
        "test_exemplo",
        "atribuição aumentada",
    ),
    "pytestmark.append": (
        "import pytest\n"
        "pytestmark = []\n"
        "pytestmark.append(pytest.mark.skip)\n"
        "def test_exemplo(): assert False\n",
        "test_exemplo",
        "append",
    ),
    "pytestmark dentro de if": (
        "import pytest\n"
        "if True:\n"
        "    pytestmark = pytest.mark.skip\n"
        "def test_exemplo(): assert False\n",
        "test_exemplo",
        "if",
    ),
}


def test_as_tres_fontes_do_revisor(tmp_path: Path) -> None:  # A-20
    for nome, (fonte, funcao, motivo) in FONTES_DO_REVISOR.items():
        ref = _arquivo(tmp_path, "test_exemplo.py", fonte)
        problemas = _problemas_de(tmp_path, ref + funcao)
        assert problemas, nome
        assert motivo in problemas[0], (nome, problemas)


def test_formas_residuais_recusadas(tmp_path: Path) -> None:  # A-21
    for nome, (fonte, funcao, motivo) in FONTES_RECUSADAS.items():
        ref = _arquivo(tmp_path, "test_exemplo.py", fonte)
        problemas = _problemas_de(tmp_path, ref + funcao)
        assert problemas, nome
        assert motivo in problemas[0], (nome, problemas)


@pytest.mark.parametrize(
    ("fonte", "funcao"),
    [
        (
            "import pytest\n"
            '@pytest.mark.skipif(False, False, reason="x")\n'
            "def test_exemplo(): ...\n",
            "test_exemplo",
        ),
        (
            "class TestValida:\n    __test__ = True\n    def test_exemplo(self): ...\n",
            "TestValida::test_exemplo",
        ),
        (
            "import pytest\n"
            "class TestValida:\n"
            "    pytestmark = [pytest.mark.django_db]\n"
            "    def test_exemplo(self): ...\n",
            "TestValida::test_exemplo",
        ),
        (
            "import pytest\npytestmark: list = [pytest.mark.tecnico]\ndef test_exemplo(): ...\n",
            "test_exemplo",
        ),
    ],
)
def test_formas_residuais_aceitas(tmp_path: Path, fonte: str, funcao: str) -> None:  # A-22
    ref = _arquivo(tmp_path, "test_valido.py", fonte)
    assert _problemas_de(tmp_path, ref + funcao) == []


def test_o_pytest_confirma_que_as_fontes_recusadas_nao_rodam(tmp_path: Path) -> None:  # A-23
    for nome, (fonte, _funcao, _motivo) in {**FONTES_DO_REVISOR, **FONTES_RECUSADAS}.items():
        pasta = tmp_path / nome.replace(" ", "_")
        pasta.mkdir()
        (pasta / "test_exemplo.py").write_text(fonte, encoding="utf-8")
        resultado = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-c", "/dev/null"],
            cwd=pasta,
            capture_output=True,
            text=True,
            check=False,
        )
        saida = resultado.stdout + resultado.stderr
        assert "failed" not in saida, (nome, saida)
        assert "passed" not in saida, (nome, saida)


# --- correção residual E16-R05: a prova escrita por referência (A-24 a A-26) ----------------------

TESTE_DE_PROVA = (
    "import pytest\n\n"
    "def _confere(valor):\n"
    "    assert valor == 42\n\n"
    "def _nao_chamada(valor):\n"
    "    assert valor == 77\n\n"
    "def test_exemplo():\n"
    "    resultado = calcular(2)\n"
    "    assert resultado == 5\n"
    "    with pytest.raises(ValueError):\n"
    "        calcular(-1)\n"
    "    _confere(resultado)\n"
)


def _problemas_de_prova(raiz: Path, prova: str) -> list[str]:
    ref = _arquivo(raiz, "test_prova.py", TESTE_DE_PROVA)
    cenarios, tecnicos = _completa()
    cenarios[1] = {"afirmação": {ref + "test_exemplo": prova}}
    return [p for p in conferir(cenarios, tecnicos, raiz=raiz) if p.startswith("cenário 1:")]


@pytest.mark.parametrize(
    ("prova", "motivo"),
    [
        ("", "texto"),
        ("O teste confere o resultado.", "crases"),
        ("O teste confere `resultado == 99`.", "não aparece"),
        ("O teste chama `calcular(2)`.", "assert"),
        ("O teste confere `valor == 77`.", "assert"),
    ],
)
def test_provas_invalidas(tmp_path: Path, prova: str, motivo: str) -> None:  # A-24
    problemas = _problemas_de_prova(tmp_path, prova)
    assert problemas, prova
    assert "prova inválida" in problemas[0]
    assert motivo in problemas[0], problemas


@pytest.mark.parametrize(
    "prova",
    [
        "O teste confere `resultado == 5`.",
        "O teste exige `pytest.raises(ValueError)` para entrada inválida.",
        "O auxiliar chamado confere `valor == 42`.",
    ],
)
def test_provas_validas(tmp_path: Path, prova: str) -> None:  # A-25
    assert _problemas_de_prova(tmp_path, prova) == []


def test_a_prova_passa_de_200_caracteres(tmp_path: Path) -> None:
    problemas = _problemas_de_prova(tmp_path, "`resultado == 5` " + "x" * 200)
    assert problemas
    assert "200" in problemas[0]


def test_todas_as_ligacoes_tem_prova_valida() -> None:  # A-26
    assert conferir(matriz.CENARIOS, matriz.TECNICOS) == []
    assert conferir_documento(DOCUMENTO, matriz.CENARIOS, matriz.TECNICOS) is None
