"""Registro do alcance pela execução (E16-07, regra 2-K, R05-J2). Plugin do pytest.

Fica ativo só com `--registrar-alcance=<arquivo.json>`; sem a opção não instala nada. Para cada
teste coletado registra, nas fases `setup` e `call` e em todas as threads, as funções e os métodos
de `apps/` e `config/` executados (os **pontos**, `<módulo pontuado>.<co_qualname>`) e as
requisições recebidas pelo handler do Django (`"<MÉTODO> <PATH_INFO>"`). Só observa: não importa
nem altera nada de `apps/` ou `config/`.

`pytest -p tests.rastreabilidade.alcance --registrar-alcance=alcance.json`
"""

import json
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import CodeType, FrameType
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTAS = tuple((RAIZ / nome).resolve() for nome in ("apps", "config"))
Perfil = Callable[[FrameType, str, Any], Any]


def _ponto_de(codigo: CodeType) -> str | None:
    """`apps.contas.adaptadores.Classe.metodo` se o código é de `apps/` ou `config/`."""
    try:
        arquivo = Path(codigo.co_filename).resolve()
    except OSError:
        return None
    if not any(pasta in arquivo.parents for pasta in PASTAS):
        return None
    partes = list(arquivo.relative_to(RAIZ).with_suffix("").parts)
    if partes[-1] == "__init__":
        partes.pop()
    return ".".join([*partes, codigo.co_qualname])


class Registro:
    def __init__(self, destino: Path) -> None:
        self.destino = destino
        self.atual: str | None = None
        self.dados: dict[str, dict[str, dict[str, None]]] = {}
        self._codigos: dict[CodeType, str | None] = {}

    def abrir(self, nodeid: str) -> None:
        self.atual = nodeid
        self.dados.setdefault(nodeid, {"pontos": {}, "requisicoes": {}})

    def perfil(self, frame: FrameType, evento: str, _arg: Any) -> None:
        if evento != "call" or self.atual is None:
            return
        codigo = frame.f_code
        if codigo not in self._codigos:
            self._codigos[codigo] = _ponto_de(codigo)
        ponto = self._codigos[codigo]
        if ponto is not None:
            self.dados[self.atual]["pontos"][ponto] = None

    def requisicao(self, **dados: Any) -> None:
        ambiente = dados.get("environ") or {}
        if self.atual is not None and ambiente:
            texto = f"{ambiente.get('REQUEST_METHOD', '')} {ambiente.get('PATH_INFO', '')}"
            self.dados[self.atual]["requisicoes"][texto] = None

    def gravar(self) -> None:
        saida = {
            nodeid: {chave: list(valores) for chave, valores in partes.items()}
            for nodeid, partes in self.dados.items()
        }
        self.destino.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")


_registro: Registro | None = None


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--registrar-alcance",
        action="store",
        default=None,
        metavar="ARQUIVO",
        help="grava no arquivo JSON os pontos de apps/ e config/ e as requisições de cada teste",
    )


def pytest_configure(config: pytest.Config) -> None:
    global _registro
    destino = config.getoption("--registrar-alcance", default=None)
    if destino:
        _registro = Registro(Path(destino))


@contextmanager
def _observando(item: pytest.Item) -> Iterator[None]:
    registro = _registro
    if registro is None:
        yield
        return
    from django.core.signals import request_started

    registro.abrir(item.nodeid)
    anterior = sys.getprofile()
    request_started.connect(registro.requisicao, weak=False, dispatch_uid="alcance")
    sys.setprofile(registro.perfil)
    threading.setprofile_all_threads(registro.perfil)
    try:
        yield
    finally:
        sys.setprofile(anterior)
        threading.setprofile_all_threads(anterior)
        request_started.disconnect(dispatch_uid="alcance")
        registro.atual = None


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Iterator[None]:
    with _observando(item):
        return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Iterator[None]:
    with _observando(item):
        return (yield)


def pytest_sessionfinish(session: pytest.Session) -> None:
    if _registro is not None:
        _registro.gravar()
