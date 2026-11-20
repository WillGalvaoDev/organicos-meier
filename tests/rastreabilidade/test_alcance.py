"""Regra 2-K da E16-07, R05-J2: o alcance do `caminho` conferido pela execução (A-66 a A-69)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from tests.rastreabilidade.conferencia import RAIZ

REF = "tests/exemplo/test_a.py::test_um"
CHAVE = 1
AFIRMACAO = "afirmação"


def _auditoria(
    caminho: str, referencia: str = REF
) -> dict[tuple[int | str, str, str], dict[str, str]]:
    linha = {
        "preparacao": "p",
        "acao": "a",
        "resultado": "r",
        "caminho": caminho,
        "veredito": "íntegra",
    }
    return {(CHAVE, AFIRMACAO, referencia): linha}


def _caso(pontos: list[str], requisicoes: list[str]) -> dict[str, list[str]]:
    return {"pontos": pontos, "requisicoes": requisicoes}


FUNCAO = "apps.pedidos.ocorrencias.registrar_ocorrencia"
OUTRA = "apps.pedidos.calculo.calcular_cobranca"


def test_a_conferencia_do_alcance_acusa_os_seis_casos() -> None:  # A-66
    from tests.rastreabilidade.conferir_alcance import conferir_alcance

    # 1. ponto de função ausente num dos dois casos de uma referência parametrizada
    registro = {f"{REF}[a]": _caso([FUNCAO], []), f"{REF}[b]": _caso([OUTRA], [])}
    problemas = conferir_alcance(_auditoria(FUNCAO), registro)
    assert problemas == [f"1 {REF} [b]: ponto não executado: {FUNCAO}"]
    # 2. ponto de função ausente no único caso
    problemas = conferir_alcance(_auditoria(FUNCAO), {REF: _caso([OUTRA], [])})
    assert len(problemas) == 1
    assert FUNCAO in problemas[0]
    assert problemas[0].startswith(f"1 {REF} [")
    # 3. rota sem requisição
    problemas = conferir_alcance(_auditoria("rota:POST /entrar/"), {REF: _caso([], [])})
    assert len(problemas) == 1
    assert "rota:POST /entrar/" in problemas[0]
    # 4. a mesma rota só com GET
    problemas = conferir_alcance(
        _auditoria("rota:POST /entrar/"), {REF: _caso([], ["GET /entrar/"])}
    )
    assert len(problemas) == 1
    assert "ponto não executado: rota:POST /entrar/" in problemas[0]
    # 5. o parâmetro casa com um segmento só
    problemas = conferir_alcance(
        _auditoria("rota:GET /convite/<str:token>/"),
        {REF: _caso([], ["GET /convite/a/b/"])},
    )
    assert len(problemas) == 1
    assert "rota:GET /convite/<str:token>/" in problemas[0]
    # 6. referência sem nenhum nodeid no registro
    problemas = conferir_alcance(
        _auditoria(FUNCAO), {"tests/exemplo/test_a.py::test_dois": _caso([FUNCAO], [])}
    )
    assert problemas == [f"1 {REF}: referência sem registro de alcance"]


def test_a_conferencia_do_alcance_aceita_o_que_foi_executado() -> None:  # A-67
    from tests.rastreabilidade.conferir_alcance import conferir_alcance

    registro = {
        f"{REF}[a]": _caso([FUNCAO, OUTRA], ["GET /convite/abc/", "POST /entrar/"]),
        f"{REF}[b]": _caso([FUNCAO, OUTRA], ["GET /convite/xyz/", "POST /entrar/"]),
    }
    caminho = f"{FUNCAO}; rota:GET /convite/<str:token>/; rota:POST /entrar/"
    assert conferir_alcance(_auditoria(caminho), registro) == []
    nao_conferidas = "modulo:config.settings.prod; comando:manage.py check; fonte:manage.py"
    assert conferir_alcance(_auditoria(nao_conferidas), {REF: _caso([], [])}) == []
    # uma referência de classe corresponde ao nodeid com a classe
    ref_classe = "tests/exemplo/test_a.py::TestC::test_um"
    assert conferir_alcance(_auditoria(FUNCAO, ref_classe), {ref_classe: _caso([FUNCAO], [])}) == []


MODULO_DE_PROVA = """
import threading

from django.test import Client

from apps.nucleo.tempo import agora, prazo_encerrado


def test_registra_o_que_roda() -> None:
    agora()
    fio = threading.Thread(target=lambda: prazo_encerrado(agora(), agora()))
    fio.start()
    fio.join()
    Client().get("/saude/")


def test_perfil_do_segundo_teste() -> None:
    assert True
"""


def _rodar(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    modulo = tmp_path / "test_prova.py"
    modulo.write_text(MODULO_DE_PROVA, encoding="utf-8")
    ambiente = {**os.environ, "PYTHONPATH": str(RAIZ)}
    comando = [
        sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p",
        "tests.rastreabilidade.alcance", "-c", str(RAIZ / "pyproject.toml"),
        "--rootdir", str(tmp_path), str(modulo), *extra,
    ]  # fmt: skip
    return subprocess.run(  # noqa: S603
        comando, cwd=tmp_path, env=ambiente, capture_output=True, text=True, check=False
    )


def test_o_registro_grava_pontos_threads_e_requisicoes(tmp_path: Path) -> None:  # A-68
    arquivo = tmp_path / "alcance.json"
    resultado = _rodar(tmp_path, f"--registrar-alcance={arquivo}")
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    registro = json.loads(arquivo.read_text(encoding="utf-8"))
    (nodeid,) = [n for n in registro if n.endswith("::test_registra_o_que_roda")]
    pontos = registro[nodeid]["pontos"]
    assert "apps.nucleo.tempo.agora" in pontos
    assert "apps.nucleo.tempo.prazo_encerrado" in pontos  # só roda na thread criada no teste
    assert "apps.nucleo.saude.saude" in pontos
    assert not any(p.startswith(("tests.", "tests/")) for p in pontos)
    assert len(pontos) == len(set(pontos))
    assert registro[nodeid]["requisicoes"] == ["GET /saude/"]
    (outro,) = [n for n in registro if n.endswith("::test_perfil_do_segundo_teste")]
    assert registro[outro] == {"pontos": [], "requisicoes": []}


def test_sem_a_opcao_nada_e_gravado_nem_instalado(tmp_path: Path) -> None:  # A-68
    modulo = tmp_path / "test_prova.py"
    modulo.write_text(
        "import sys\n\n\ndef test_sem_perfil() -> None:\n    assert sys.getprofile() is None\n",
        encoding="utf-8",
    )
    ambiente = {**os.environ, "PYTHONPATH": str(RAIZ)}
    comando = [
        sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p",
        "tests.rastreabilidade.alcance", "-c", str(RAIZ / "pyproject.toml"),
        "--rootdir", str(tmp_path), str(modulo),
    ]  # fmt: skip
    resultado = subprocess.run(  # noqa: S603
        comando, cwd=tmp_path, env=ambiente, capture_output=True, text=True, check=False
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_o_ci_confere_o_alcance_depois_da_regra_3e() -> None:  # A-69 (leitura do ci.yml)
    fluxo = yaml.safe_load((RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    comandos = [
        str(passo.get("run", ""))
        for trabalho in fluxo["jobs"].values()
        for passo in trabalho["steps"]
        if "tests.rastreabilidade" in str(passo.get("run", ""))
    ]
    execucao = [n for n, c in enumerate(comandos) if "conferir_execucao relatorio-pytest.xml" in c]
    alcance = [
        n
        for n, c in enumerate(comandos)
        if "python -m tests.rastreabilidade.conferir_alcance --executar alcance.json" in c
    ]
    assert execucao
    assert alcance
    assert alcance[0] > execucao[0]
