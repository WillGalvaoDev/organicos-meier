"""E16-07: a matriz de rastreabilidade cenário -> afirmações -> testes (acceptance A-1 a A-17).

Os casos negativos montam matrizes e arquivos de teste de exemplo aqui mesmo e os passam à função
de conferência, que lê as árvores de sintaxe dos arquivos de `tests/` sem importar nem rodar nada.
"""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
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


FONTES_A22 = [
    (
        'import pytest\n@pytest.mark.skipif(False, False, reason="x")\ndef test_exemplo(): ...\n',
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
]


@pytest.mark.parametrize(("fonte", "funcao"), FONTES_A22)
def test_formas_residuais_aceitas(tmp_path: Path, fonte: str, funcao: str) -> None:  # A-22
    ref = _arquivo(tmp_path, "test_valido.py", fonte)
    assert _problemas_de(tmp_path, ref + funcao) == []


# --- segunda correção residual E16-R06: lista fechada, execução real e A-23 diferencial ----------

APOIO = (
    "from contextlib import contextmanager\n"
    "import pytest\n"
    'pytestmark = pytest.mark.skip(reason="do apoio")\n'
    "class BaseImportada:\n"
    '    pytestmark = pytest.mark.skip(reason="base importada")\n'
    "class Meta(type):\n"
    "    __test__ = False\n"
    "@contextmanager\n"
    "def contexto():\n"
    '    yield [pytest.mark.skip(reason="com with")]\n'
)
PULADO, FALHA_ESPERADA, NAO_COLETADO, FALHOU = "pulado", "falha esperada", "não coletado", "falhou"
EXECUCAO = {  # resultado esperado do pytest real -> (código de saída, contagem por resultado)
    PULADO: (0, {"skipped": 1}),
    FALHA_ESPERADA: (0, {"xfailed": 1}),
    NAO_COLETADO: (5, {}),
    FALHOU: (1, {"failed": 1}),
}
ESPERADO_DO_A20_E_A21 = {
    "pytestmark da classe": PULADO,
    "skipif com duas condições": PULADO,
    "__test__ anotado": NAO_COLETADO,
    "pytestmark anotado de classe com xfail": FALHA_ESPERADA,
    "skipif sem condição": None,
    "skipif com condition=True depois de False": None,
    "__test__ com nome na classe": NAO_COLETADO,
    "pytestmark com atribuição aumentada": PULADO,
    "pytestmark.append": PULADO,
    "pytestmark dentro de if": PULADO,
}
_C = "import pytest\n"
_T = "def test_exemplo(): assert False\n"
# nome -> (fonte, referência, trechos do motivo, resultado do pytest)
FONTES_A29 = {
    "append dentro de if": (
        _C
        + "pytestmark = []\n"
        + "if True:\n"
        + '    pytestmark.append(pytest.mark.skip(reason="pulado"))\n'
        + _T,
        "test_exemplo",
        ["lido", "chamada de método", "dentro de if", "(linha 4)"],
        PULADO,
    ),
    "__test__ encadeado": (
        "__test__ = habilitado = False\n" + _T,
        "test_exemplo",
        ["__test__", "atribuição encadeada", "(linha 1)"],
        NAO_COLETADO,
    ),
}
# nome -> (fonte, referência, trechos do motivo, resultado do pytest, só recusa por precaução)
FONTES_A30 = {
    "leitura por alias": (
        _C + "pytestmark = []\nx = pytestmark\nx.append(pytest.mark.skip)\n" + _T,
        "test_exemplo",
        ["pytestmark", "lido"],
        PULADO,
        False,
    ),
    "definido duas vezes": (
        _C + "pytestmark = []\npytestmark = [pytest.mark.skip]\n" + _T,
        "test_exemplo",
        ["pytestmark", "mais de uma vez"],
        PULADO,
        False,
    ),
    "operador morsa": (
        _C + "(pytestmark := [pytest.mark.skip])\n" + _T,
        "test_exemplo",
        ["pytestmark", "operador :="],
        PULADO,
        False,
    ),
    "alvo de for": (
        _C + "for pytestmark in [[pytest.mark.skip]]: pass\n" + _T,
        "test_exemplo",
        ["pytestmark", "alvo de for"],
        PULADO,
        False,
    ),
    "alvo de with": (
        "from apoio import contexto\nwith contexto() as pytestmark: pass\n" + _T,
        "test_exemplo",
        ["pytestmark", "alvo de with"],
        PULADO,
        False,
    ),
    "del": (
        _C + "pytestmark = []\ndel pytestmark\n" + _T,
        "test_exemplo",
        ["pytestmark", "del"],
        FALHOU,
        True,
    ),
    "importado do apoio": (
        "from apoio import pytestmark\n" + _T,
        "test_exemplo",
        ["pytestmark", "importado"],
        PULADO,
        False,
    ),
    "import estrela": (
        "from apoio import *\n" + _T,
        "test_exemplo",
        ["import *"],
        PULADO,
        False,
    ),
    "import como pytestmark": (
        "import pytest as pytestmark\n" + _T,
        "test_exemplo",
        ["pytestmark", "importado"],
        None,
        True,
    ),
    "globals().update": (
        _C + "globals().update(pytestmark=[pytest.mark.skip])\n" + _T,
        "test_exemplo",
        ["pytestmark", "argumento nomeado"],
        PULADO,
        False,
    ),
    "vars()": (
        'vars()["__test__"] = False\n' + _T,
        "test_exemplo",
        ["__test__", "texto literal"],
        NAO_COLETADO,
        False,
    ),
    "exec": (
        _C + 'exec("pytestmark = [pytest.mark.skip]")\n' + _T,
        "test_exemplo",
        ["pytestmark", "texto literal"],
        PULADO,
        False,
    ),
    "__getattr__ do módulo": (
        _C
        + "def __getattr__(nome):\n"
        + '    if nome == "pytestmark":\n'
        + '        return [pytest.mark.skip(reason="getattr")]\n'
        + "    raise AttributeError(nome)\n"
        + _T,
        "test_exemplo",
        ["__getattr__"],
        PULADO,
        False,
    ),
    "append em função chamada": (
        _C
        + "pytestmark = []\n"
        + "def _arma():\n"
        + "    pytestmark.append(pytest.mark.skip)\n"
        + "_arma()\n"
        + _T,
        "test_exemplo",
        ["pytestmark", "lido"],
        PULADO,
        False,
    ),
    "__test__ dentro de try na classe": (
        "class TestExemplo:\n"
        "    try:\n"
        "        __test__ = False\n"
        "    except Exception:\n"
        "        pass\n"
        "    def test_exemplo(self): assert False\n",
        "TestExemplo::test_exemplo",
        ["__test__", "dentro de try"],
        NAO_COLETADO,
        False,
    ),
}
FONTES_A31 = {
    "base com pytestmark skip": (
        _C
        + "class Base:\n"
        + "    pytestmark = pytest.mark.skip\n"
        + "class TestExemplo(Base):\n"
        + "    def test_exemplo(self): assert False\n",
        "TestExemplo::test_exemplo",
        ["Base", "skip"],
        PULADO,
        False,
    ),
    "base com __test__ False": (
        "class Base:\n"
        "    __test__ = False\n"
        "class TestExemplo(Base):\n"
        "    def test_exemplo(self): assert False\n",
        "TestExemplo::test_exemplo",
        ["Base", "__test__"],
        NAO_COLETADO,
        False,
    ),
    "base importada": (
        "from apoio import BaseImportada\n"
        "class TestExemplo(BaseImportada):\n"
        "    def test_exemplo(self): assert False\n",
        "TestExemplo::test_exemplo",
        ["BaseImportada", "base"],
        PULADO,
        False,
    ),
    "metaclasse": (
        "from apoio import Meta\n"
        "class TestExemplo(metaclass=Meta):\n"
        "    def test_exemplo(self): assert False\n",
        "TestExemplo::test_exemplo",
        ["metaclass", "argumento nomeado"],
        NAO_COLETADO,
        False,
    ),
    "__getattr__ na classe": (
        "class TestExemplo:\n"
        "    def __getattr__(self, nome): raise AttributeError(nome)\n"
        "    def test_exemplo(self): assert False\n",
        "TestExemplo::test_exemplo",
        ["__getattr__"],
        FALHOU,
        True,
    ),
}
FONTES_A32 = {
    "base com django_db": (
        _C
        + "class Base:\n"
        + "    pytestmark = [pytest.mark.django_db]\n"
        + "class TestExemplo(Base):\n"
        + "    def test_exemplo(self): ...\n",
        "TestExemplo::test_exemplo",
    ),
    "TestCase do django": (
        "from django.test import TestCase\n"
        "class TestExemplo(TestCase):\n"
        "    def test_exemplo(self): ...\n",
        "TestExemplo::test_exemplo",
    ),
    "unittest.TestCase": (
        "import unittest\nclass TestExemplo(unittest.TestCase):\n    def test_exemplo(self): ...\n",
        "TestExemplo::test_exemplo",
    ),
    "docstring que cita pytestmark": (
        '"""Este módulo não define pytestmark nem __test__."""\n\ndef test_exemplo(): ...\n',
        "test_exemplo",
    ),
    "comentário com __test__": (
        "# __test__ = False não vale aqui\ndef test_exemplo(): ...\n",
        "test_exemplo",
    ),
}


def _recusa_de(tmp_path: Path, fonte: str, funcao: str) -> str:
    ref = _arquivo(tmp_path, "test_exemplo.py", fonte)
    problemas = _problemas_de(tmp_path, ref + funcao)
    assert problemas, fonte
    return problemas[0]


def test_as_duas_fontes_da_revalidacao_de_9f4163b(tmp_path: Path) -> None:  # A-29
    for nome, (fonte, funcao, trechos, _) in FONTES_A29.items():
        mensagem = _recusa_de(tmp_path, fonte, funcao)
        for trecho in trechos:
            assert trecho in mensagem, (nome, trecho, mensagem)


def test_a_lista_fechada_recusa_as_demais_ocorrencias(tmp_path: Path) -> None:  # A-30
    for nome, (fonte, funcao, trechos, *_) in FONTES_A30.items():
        mensagem = _recusa_de(tmp_path, fonte, funcao)
        assert "linha" in mensagem, (nome, mensagem)
        for trecho in trechos:
            assert trecho in mensagem, (nome, trecho, mensagem)


def test_a_heranca_e_recusada(tmp_path: Path) -> None:  # A-31
    for nome, (fonte, funcao, trechos, *_) in FONTES_A31.items():
        mensagem = _recusa_de(tmp_path, fonte, funcao)
        for trecho in trechos:
            assert trecho in mensagem, (nome, trecho, mensagem)


def test_formas_da_lista_fechada_e_heranca_aceitas(tmp_path: Path) -> None:  # A-32
    for nome, (fonte, funcao) in FONTES_A32.items():
        ref = _arquivo(tmp_path, "test_valido.py", fonte)
        assert _problemas_de(tmp_path, ref + funcao) == [], nome
    for fonte_a22, funcao_a22 in FONTES_A22:
        ref = _arquivo(tmp_path, "test_valido.py", fonte_a22)
        assert _problemas_de(tmp_path, ref + funcao_a22) == []


def _ambiente_isolado() -> dict[str, str]:
    base = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE")
    ambiente = {k: os.environ[k] for k in base if k in os.environ}
    ambiente["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return ambiente


def _rodar_o_pytest_real(pasta: Path, fonte: str) -> tuple[int, dict[str, int], str]:
    """Roda a fonte com o pytest real, isolado (regra 3-F); devolve código, contagens e saída."""
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (pasta / "apoio.py").write_text(APOIO, encoding="utf-8")
    (pasta / "test_exemplo.py").write_text(fonte, encoding="utf-8")
    relatorio = pasta / "relatorio.xml"
    comando = [
        sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
        "-c", str(pasta / "pytest.ini"), "--rootdir", str(pasta), "--junitxml", str(relatorio),
    ]  # fmt: skip
    resultado = subprocess.run(  # noqa: S603
        comando, cwd=pasta, env=_ambiente_isolado(), capture_output=True, text=True, check=False
    )
    saida = resultado.stdout + resultado.stderr
    contagens: dict[str, int] = {}
    if relatorio.is_file():
        for caso in ET.parse(relatorio).getroot().iter("testcase"):  # noqa: S314
            pulo = caso.find("skipped")
            if caso.find("error") is not None:
                chave = "error"
            elif caso.find("failure") is not None:
                chave = "failed"
            elif pulo is not None:
                chave = "xfailed" if pulo.get("type") == "pytest.xfail" else "skipped"
            else:
                chave = "passed"
            contagens[chave] = contagens.get(chave, 0) + 1
    return resultado.returncode, contagens, saida


def _corpus() -> list[tuple[str, str, str, str | None, bool]]:
    """(nome, fonte, referência, resultado esperado do pytest, só precaução)."""
    corpus: list[tuple[str, str, str, str | None, bool]] = []
    for nome, (fonte, funcao, _) in {**FONTES_DO_REVISOR, **FONTES_RECUSADAS}.items():
        corpus.append((nome, fonte, funcao, ESPERADO_DO_A20_E_A21[nome], False))
    for nome, (fonte, funcao, _, resultado29) in FONTES_A29.items():
        corpus.append((nome, fonte, funcao, resultado29, False))
    for nome, (fonte, funcao, _, resultado, precaucao) in {**FONTES_A30, **FONTES_A31}.items():
        corpus.append((nome, fonte, funcao, resultado, precaucao))
    return corpus


def test_o_pytest_real_confirma_cada_recusa_e_cada_aceitacao(tmp_path: Path) -> None:  # A-23
    # o controle: as fontes aceitas do A-22 com `assert False` dão 1 failed (o ambiente executa)
    for i, (fonte, _funcao) in enumerate(FONTES_A22):
        corpo = fonte.replace("...", "assert False")
        codigo, contagens, saida = _rodar_o_pytest_real(tmp_path / f"controle{i}", corpo)
        assert (codigo, contagens) == EXECUCAO[FALHOU], (i, saida)
    # o corpus: resultado declarado, código e contagem exatos, e a propriedade diferencial
    for i, (nome, fonte, funcao, esperado, precaucao) in enumerate(_corpus()):
        estatico = tmp_path / f"estatico{i}"
        ref = _arquivo(estatico, "test_exemplo.py", fonte)
        recusada = bool(_problemas_de(estatico, ref + funcao))
        if esperado is None:  # não executável: o pytest dá erro de coleta; só a recusa vale
            assert recusada, nome
            continue
        codigo, contagens, saida = _rodar_o_pytest_real(tmp_path / f"real{i}", fonte)
        assert (codigo, contagens) == EXECUCAO[esperado], (nome, codigo, contagens, saida)
        rodou = contagens == {"failed": 1}
        if precaucao:
            assert recusada, nome
        else:
            assert recusada == (not rodou), (nome, recusada, contagens)


def _relatorio(tmp_path: Path, *casos: str) -> Path:
    arquivo = tmp_path / "relatorio-pytest.xml"
    corpo = "".join(casos)
    arquivo.write_text(
        f"<?xml version='1.0'?><testsuites><testsuite>{corpo}</testsuite></testsuites>",
        encoding="utf-8",
    )
    return arquivo


def _caso(modulo: str, nome: str, filho: str = "") -> str:
    return f'<testcase classname="{modulo}" name="{nome}" time="0.01">{filho}</testcase>'


M = "tests.tecnicos.test_exemplo"
R_FUNCAO = "tests/tecnicos/test_exemplo.py::test_a"
R_METODO = "tests/tecnicos/test_exemplo.py::TestC::test_b"


def _execucao(relatorio: Path, *referencias: str) -> list[str]:
    from tests.rastreabilidade.conferir_execucao import conferir_execucao

    cenarios = {1: {"afirmação": {r: "x" for r in referencias}}}
    return conferir_execucao(relatorio, cenarios, {})


def test_a_execucao_acusa_o_que_nao_passou(tmp_path: Path) -> None:  # A-33
    pulo = '<skipped type="pytest.skip" message="x">pulado</skipped>'
    xfail = '<skipped type="pytest.xfail" message="x">falha esperada</skipped>'
    casos = {
        "ausente": ([_caso(M, "test_outro")], "sem testcase"),
        "skipped": ([_caso(M, "test_a", pulo)], "skipped"),
        "xfail": ([_caso(M, "test_a", xfail)], "xfail"),
        "failure": ([_caso(M, "test_a", '<failure message="x">x</failure>')], "failure"),
        "error": ([_caso(M, "test_a", '<error message="x">x</error>')], "error"),
        "parametrizada": ([_caso(M, "test_a[a]"), _caso(M, "test_a[b]", pulo)], "skipped"),
    }
    for nome, (xml, resultado) in casos.items():
        pasta = tmp_path / nome
        pasta.mkdir()
        problemas = _execucao(_relatorio(pasta, *xml), R_FUNCAO)
        assert len(problemas) == 1, (nome, problemas)
        assert R_FUNCAO in problemas[0], (nome, problemas)
        assert resultado in problemas[0], (nome, problemas)


def test_a_execucao_aceita_o_que_passou(tmp_path: Path) -> None:  # A-34
    relatorio = _relatorio(
        tmp_path,
        _caso(M, "test_a"),
        _caso(M + ".TestC", "test_b"),
        _caso(M, "test_p[1]"),
        _caso(M, "test_p[2]"),
    )
    referencias = (R_FUNCAO, R_METODO, "tests/tecnicos/test_exemplo.py::test_p")
    assert _execucao(relatorio, *referencias) == []


def test_o_ci_grava_e_confere_o_relatorio_da_execucao() -> None:  # A-35
    import yaml

    fluxo = yaml.safe_load((RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    comandos = [
        str(passo.get("run", ""))
        for trabalho in fluxo["jobs"].values()
        for passo in trabalho["steps"]
        if "pytest" in str(passo.get("run", ""))
    ]
    gravacao = [n for n, c in enumerate(comandos) if "--junitxml=relatorio-pytest.xml" in c]
    conferencia = [
        n
        for n, c in enumerate(comandos)
        if "python -m tests.rastreabilidade.conferir_execucao relatorio-pytest.xml" in c
    ]
    assert gravacao
    assert conferencia
    assert conferencia[0] == gravacao[0] + 1


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
