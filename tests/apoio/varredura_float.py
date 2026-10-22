"""Varredura estática de `float` em módulos de dinheiro e quantidade (E08-01 A-11, T-39).

Código de teste, não de produção. Pela árvore de sintaxe (`ast`), acusa o literal `float`, a
chamada a `float` e o `FloatField`, com arquivo e linha.
"""

import ast
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Módulos de dinheiro e quantidade. `apps/contas` fica fora: usa `float` em instantes de
# autenticação, sem dinheiro.
MODULOS_DE_DINHEIRO = (
    "apps/pedidos",
    "apps/pagamentos",
    "apps/simulador_pagamentos",
    "apps/catalogo",
    "apps/interesses",
    "apps/rodadas",
    "apps/fornecedores",
    "apps/nucleo/valores.py",
)


@dataclass(frozen=True)
class Ocorrencia:
    arquivo: Path
    linha: int
    tipo: str

    def __str__(self) -> str:
        return f"{self.arquivo}:{self.linha}: {self.tipo}"


class _Visitante(ast.NodeVisitor):
    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo
        self.achadas: list[Ocorrencia] = []

    def _acusar(self, no: ast.AST, tipo: str) -> None:
        self.achadas.append(Ocorrencia(self.arquivo, getattr(no, "lineno", 0), tipo))

    def visit_Constant(self, no: ast.Constant) -> None:
        if isinstance(no.value, float):
            self._acusar(no, "literal float")

    def visit_Call(self, no: ast.Call) -> None:
        if isinstance(no.func, ast.Name) and no.func.id == "float":
            self._acusar(no, "chamada a float")
        self.generic_visit(no)

    def visit_Name(self, no: ast.Name) -> None:
        if no.id == "FloatField":
            self._acusar(no, "FloatField")

    def visit_Attribute(self, no: ast.Attribute) -> None:
        if no.attr == "FloatField":
            self._acusar(no, "FloatField")
        self.generic_visit(no)


def varrer_arquivo(arquivo: Path) -> list[Ocorrencia]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
    visitante = _Visitante(arquivo)
    visitante.visit(arvore)
    return sorted(visitante.achadas, key=lambda o: o.linha)


def arquivos_dos_modulos(raiz: Path = RAIZ) -> list[Path]:
    arquivos: list[Path] = []
    for modulo in MODULOS_DE_DINHEIRO:
        caminho = raiz / modulo
        if caminho.is_file():
            arquivos.append(caminho)
            continue
        arquivos.extend(
            arquivo
            for arquivo in sorted(caminho.rglob("*.py"))
            if "migrations" not in arquivo.parts
        )
    return arquivos


def varrer_modulos_de_dinheiro(raiz: Path = RAIZ) -> list[Ocorrencia]:
    achadas: list[Ocorrencia] = []
    for arquivo in arquivos_dos_modulos(raiz):
        achadas.extend(varrer_arquivo(arquivo))
    return achadas
