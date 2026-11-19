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


# --- segunda correção residual E16-R05: afirmações atômicas (A-36, estrutura) ---------------------


def test_as_entradas_apontadas_tem_as_afirmacoes_atomicas() -> None:  # A-36
    assert len(matriz.CENARIOS[17]) == 4
    assert len(matriz.CENARIOS[20]) == 4
    assert len(matriz.CENARIOS[34]) == 4
    assert len(matriz.CENARIOS[59]) == 6
    assert len(matriz.TECNICOS["T-38"]) == 8
    formal = [a for a in matriz.CENARIOS[17] if "mensagem formal" in a]
    assert len(formal) == 1
    assert len(matriz.CENARIOS[17][formal[0]]) == 2  # depois do envio e antes da aprovação


# --- terceira correção E16-R05: o caso de parametrização citável e conferido (A-39 e A-40) -------

TESTE_COM_CASOS = (
    "import pytest\n\n"
    'CASOS_USADOS = [(1, "0.5", True)]\n'
    'CASOS_SOLTOS = [(9, "9.5", False)]\n\n'
    '@pytest.mark.parametrize(("u", "x", "ok"), CASOS_USADOS)\n'
    "def test_a(u, x, ok):\n"
    '    fora_do_decorador = (7, "7.7", True)\n'
    "    assert ok is True\n\n"
    '@pytest.mark.parametrize(("u", "x", "ok"), [(2, "1.5", False)])\n'
    "def test_b(u, x, ok):\n"
    "    assert ok is False\n"
)


def _problemas_do_caso(raiz: Path, funcao: str, prova: str) -> list[str]:
    ref = _arquivo(raiz, "test_casos.py", TESTE_COM_CASOS)
    cenarios, tecnicos = _completa()
    cenarios[1] = {"afirmação": {ref + funcao: prova}}
    return [p for p in conferir(cenarios, tecnicos, raiz=raiz) if p.startswith("cenário 1:")]


@pytest.mark.parametrize(
    ("funcao", "caso"),
    [
        ("test_a", '(7, "7.7", True)'),  # no corpo, fora do decorador e de qualquer assert
        ("test_a", '(2, "1.5", False)'),  # no `parametrize` de outro teste do módulo
        ("test_a", '(9, "9.5", False)'),  # numa constante que o decorador do teste não usa
    ],
)
def test_o_caso_fora_do_parametrize_do_teste_e_acusado(
    tmp_path: Path, funcao: str, caso: str
) -> None:  # A-39
    prova = f"Confere `ok is True` no caso `{caso}`."
    problemas = _problemas_do_caso(tmp_path, funcao, prova)
    assert problemas, caso
    assert "prova inválida" in problemas[0]
    assert "test_casos.py::" + funcao in problemas[0]
    assert "parametrize" in problemas[0]


@pytest.mark.parametrize(
    ("funcao", "prova"),
    [
        ("test_b", 'Confere `ok is False` no caso `(2, "1.5", False)`.'),
        ("test_a", 'Confere `ok is True` no caso `(1, "0.5", True)`.'),
    ],
)
def test_o_caso_do_decorador_ou_da_constante_usada_e_aceito(
    tmp_path: Path, funcao: str, prova: str
) -> None:  # A-40
    assert _problemas_do_caso(tmp_path, funcao, prova) == []


# --- terceira correção E16-R05: elementos concretos (A-41 a A-44, estrutura) ----------------------

TESTE_DO_DINHEIRO = (
    "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py"
    "::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso"
)
TESTE_DA_ROTA = (
    "tests/aceitacao/test_cenario_63_rota_1_2_kg.py::test_cenario_63_rota_recusa_1_2_kg_sem_gravar"
)
TESTE_DO_HISTORICO = (
    "tests/aceitacao/test_cenario_96_historico.py"
    "::test_cenario_96_historico_mostra_reservado_e_pendente_com_estoque_zerado"
)


def _afirmacao(entrada: dict[str, dict[str, str]], trecho: str) -> dict[str, str]:
    achadas = [provas for afirmacao, provas in entrada.items() if trecho in afirmacao]
    assert len(achadas) == 1, trecho
    return achadas[0]


def test_c63_liga_a_rota_e_cita_o_caso_do_kg() -> None:  # A-41 (estrutura)
    api = _afirmacao(matriz.CENARIOS[63], "pela API")
    assert list(api) == [TESTE_DA_ROTA]
    assert "`resposta.status_code == 200`" in api[TESTE_DA_ROTA]
    aceito = _afirmacao(matriz.CENARIOS[63], "1,5 kg é aceito")
    assert any('`(Unidade.KG, "0.5", "1.5", True)`' in prova for prova in aceito.values())


def test_t11_a_direcao_vai_de_a_para_a_obrigacao_de_b() -> None:  # A-42 (estrutura)
    provas = _afirmacao(matriz.TECNICOS["T-11"], "para obrigação de B")
    assert list(provas) == [TESTE_DO_DINHEIRO]
    prova = provas[TESTE_DO_DINHEIRO]
    assert "`pytest.raises(MovimentoProibido)`" in prova
    assert "(_saldos(), MovimentoFinanceiro.objects.count()) == antes" in prova
    assert not any("test_o_repasse_de_a_nao_usa" in ref for ref in provas)
    limite = _afirmacao(matriz.TECNICOS["T-11"], "limitado ao valor liberado de A")
    assert any("test_o_repasse_de_a_nao_usa" in ref for ref in limite)


def test_t38_as_provas_de_unidade_citam_o_caso_e_a_unidade() -> None:  # A-43 (estrutura)
    esperado = {
        "em L são": (
            "Unidade.LITRO",
            ['(Unidade.LITRO, "0.5", "1.5", True)', '"0.5", "1.2", False)'],
        ),
        "em kg são": ("Unidade.KG", ['(Unidade.KG, "0.5", "1.2", False)']),
        "em unidade são": ("Unidade.UNIDADE", ['(Unidade.UNIDADE, "1", "2.5", False)']),
    }
    for trecho, (unidade, casos) in esperado.items():
        provas = _afirmacao(matriz.TECNICOS["T-38"], trecho)
        assert not any("test_quantidades_aceitas" in ref for ref in provas), trecho
        assert not any("test_quantidades_recusadas" in ref for ref in provas), trecho
        for prova in provas.values():
            assert unidade in prova, trecho
            assert all(caso in prova for caso in casos), trecho


def test_c96_tem_a_afirmacao_do_carrinho_e_a_do_historico() -> None:  # A-44
    entrada = matriz.CENARIOS[96]
    historico = _afirmacao(entrada, "O histórico")
    assert TESTE_DO_HISTORICO in historico
    assert any("carrinho" in afirmacao for afirmacao in entrada)
    assert not any(
        "histórico" in afirmacao.lower() for afirmacao in entrada if "carrinho" in afirmacao
    )


# --- quarta correção E16-R05: a guarda conservadora da constante de casos (A-47 e A-48) ----------

_PARAMETRIZE = (
    "import pytest\n\n"
    'CASOS = [(1, "0.5", True)]\n\n'
    '@pytest.mark.parametrize(("u", "x", "ok"), CASOS)\n'
    "def test_exemplo(u, x, ok):\n"
    '    assert (u, x, ok) == (1, "0.5", True)\n'
)
_CASO_NOVO = '(9, "9.5", False)'
MOTIVO_DA_CONSTANTE = "constante de casos com mais de uma ligação ou alterada no módulo"

FONTES_DA_CONSTANTE_ALTERADA = {
    "reatribuída depois do decorador (reprodução do revisor)": _PARAMETRIZE
    + f"CASOS = [{_CASO_NOVO}]\n",
    "mais atribuição": _PARAMETRIZE + f"CASOS += [{_CASO_NOVO}]\n",
    "append": _PARAMETRIZE + f"CASOS.append({_CASO_NOVO})\n",
    "índice": _PARAMETRIZE + f"CASOS[0] = {_CASO_NOVO}\n",
    "atribuída só depois da definição": _PARAMETRIZE.replace('CASOS = [(1, "0.5", True)]\n\n', "")
    + f"CASOS = [{_CASO_NOVO}]\n",
    "global em função": _PARAMETRIZE
    + f"\ndef religa():\n    global CASOS\n    CASOS = [{_CASO_NOVO}]\n",
    "for no módulo": _PARAMETRIZE + f"for CASOS in [[{_CASO_NOVO}]]:\n    pass\n",
}


def _problemas_da_fonte(raiz: Path, fonte: str, prova: str) -> list[str]:
    ref = _arquivo(raiz, "test_constante.py", fonte)
    cenarios, tecnicos = _completa()
    cenarios[1] = {"afirmação": {ref + "test_exemplo": prova}}
    return [p for p in conferir(cenarios, tecnicos, raiz=raiz) if p.startswith("cenário 1:")]


@pytest.mark.parametrize("nome", list(FONTES_DA_CONSTANTE_ALTERADA))
def test_a_constante_de_casos_alterada_e_acusada(tmp_path: Path, nome: str) -> None:  # A-47
    prova = f'Caso `{_CASO_NOVO}`; `(u, x, ok) == (1, "0.5", True)`.'
    problemas = _problemas_da_fonte(tmp_path, FONTES_DA_CONSTANTE_ALTERADA[nome], prova)
    assert problemas, nome
    assert "test_constante.py::test_exemplo" in problemas[0]
    assert MOTIVO_DA_CONSTANTE in problemas[0], problemas


def test_a_constante_de_casos_de_uma_ligacao_so_e_aceita(tmp_path: Path) -> None:  # A-48
    prova = 'Caso `(1, "0.5", True)`; `(u, x, ok) == (1, "0.5", True)`.'
    assert _problemas_da_fonte(tmp_path, _PARAMETRIZE, prova) == []
    no_decorador = _PARAMETRIZE.replace('CASOS = [(1, "0.5", True)]\n\n', "").replace(
        "), CASOS)", '), [(1, "0.5", True)])'
    )
    assert _problemas_da_fonte(tmp_path, no_decorador, prova) == []


# --- quarta correção E16-R05: a auditoria de cada ligação (A-49 e A-50) --------------------------


def _auditoria_de(
    cenarios: dict[int, Afirmacoes], tecnicos: dict[str, Afirmacoes]
) -> dict[tuple[int | str, str, str], dict[str, str]]:
    linha = {"preparacao": "p", "acao": "a", "resultado": "r", "veredito": "íntegra"}
    return {
        (chave, afirmacao, ref): dict(linha)
        for tabela in (cenarios, tecnicos)
        for chave, afs in tabela.items()
        for afirmacao, provas in afs.items()
        for ref in provas
    }


def test_a_auditoria_acusa_as_cinco_falhas() -> None:  # A-49
    from tests.rastreabilidade.conferencia import conferir_auditoria

    cenarios, tecnicos = _completa()
    base = _auditoria_de(cenarios, tecnicos)
    assert conferir_auditoria(base, cenarios, tecnicos) == []
    chave = (1, "afirmação do cenário 1", REAL)

    sem_linha = {k: v for k, v in base.items() if k != chave}
    assert any(
        "sem linha na auditoria" in p for p in conferir_auditoria(sem_linha, cenarios, tecnicos)
    )

    com_sobra = {**base, (1, "outra afirmação", REAL): dict(base[chave])}
    assert any(
        "sem ligação na matriz" in p for p in conferir_auditoria(com_sobra, cenarios, tecnicos)
    )

    vazio = {**base, chave: {**base[chave], "acao": " "}}
    assert any(
        "campo vazio" in p and "acao" in p for p in conferir_auditoria(vazio, cenarios, tecnicos)
    )

    comprido = {**base, chave: {**base[chave], "resultado": "x" * 201}}
    assert any("mais de 200" in p for p in conferir_auditoria(comprido, cenarios, tecnicos))

    ok = {**base, chave: {**base[chave], "veredito": "ok"}}
    assert any("veredito" in p for p in conferir_auditoria(ok, cenarios, tecnicos))
    corrigida = {**base, chave: {**base[chave], "veredito": "corrigida: religada"}}
    assert conferir_auditoria(corrigida, cenarios, tecnicos) == []


def test_a_auditoria_entregue_cobre_exatamente_as_ligacoes() -> None:  # A-50
    from tests.rastreabilidade import auditoria
    from tests.rastreabilidade.conferencia import conferir_auditoria

    assert conferir_auditoria(auditoria.AUDITORIA, matriz.CENARIOS, matriz.TECNICOS) == []


# --- quarta correção E16-R05: os sete resíduos da regra 2-G (A-51, estrutura) -------------------

FILA = "tests/tecnicos/test_fila_ponta_a_ponta.py"
VIAVEL = "tests/tecnicos/test_apuracao_viavel.py"


def _refs(entrada: dict[str, dict[str, str]], trecho: str) -> list[str]:
    return list(_afirmacao(entrada, trecho))


def test_os_sete_residuos_da_regra_2g_estao_corrigidos() -> None:  # A-51
    assert _refs(matriz.CENARIOS[74], "O pedido congelado não muda") == [
        VIAVEL + "::test_o_pedido_congelado_nao_muda"
    ]
    assert not any(
        "test_unidades_da_caixa_invalidada_voltam_para_a_fila" in ref
        for ref in _refs(matriz.CENARIOS[74], "O pedido congelado não muda")
    )
    assert _refs(matriz.CENARIOS[84], "podem pertencer a contas distintas") == [
        "tests/aceitacao/test_cenarios_84_aliases_contas_distintas.py"
        "::test_cenario_84_aliases_com_mais_sao_contas_distintas"
    ]
    teste_90 = (
        "tests/aceitacao/test_cenarios_90_item_inteiro_de_0_25_kg.py"
        "::test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado"
    )
    assert len(matriz.CENARIOS[90]) == 3
    assert all(list(provas) == [teste_90] for provas in matriz.CENARIOS[90].values())
    pk_real = _refs(matriz.TECNICOS["T-44"], "item de pedido congelado")
    assert pk_real == [FILA + "::test_rota_com_o_pk_real_do_item_congelado_e_recusada"]
    em_pedido = _refs(matriz.TECNICOS["T-44"], "parcela em pedido é recusada pelo serviço")
    assert em_pedido == [
        "tests/tecnicos/test_interesses_remover_pendente.py::test_parcela_em_pedido_nao_entra_na_remocao"
    ]
    caixas = _refs(matriz.TECNICOS["T-47"], "formação de caixas")
    assert caixas == [
        "tests/tecnicos/test_interesses_progresso.py::test_a_formacao_de_caixas_ignora_as_pendentes"
    ]
    for trecho, caso in (("igual a zero", '"0"'), ("negativo", '"-1"')):
        (prova,) = _afirmacao(matriz.CENARIOS[86], trecho).values()
        assert caso in prova, trecho
    (fora_do_incremento,) = _afirmacao(matriz.TECNICOS["T-43"], "fora do incremento").values()
    assert '"1.5"' in fora_do_incremento
    (acima,) = _afirmacao(matriz.TECNICOS["T-43"], "acima do pendente").values()
    assert '"5"' in acima
