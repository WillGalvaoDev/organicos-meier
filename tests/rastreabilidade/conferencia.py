"""A conferência da matriz de rastreabilidade (E16-07, regra 3).

Lê a árvore de sintaxe dos arquivos de `tests/`: não importa nem roda nenhum teste.
"""

import ast
from collections.abc import Mapping, Sequence
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CENARIOS_ESPERADOS = tuple(range(1, 120))
TECNICOS_ESPERADOS = tuple(f"T-{n}" for n in range(1, 56))


def _e_marca(no: ast.expr, nome: str) -> bool:
    """`pytest.mark.<nome>` ou `pytest.mark.<nome>(...)`."""
    alvo = no.func if isinstance(no, ast.Call) else no
    return (
        isinstance(alvo, ast.Attribute)
        and alvo.attr == nome
        and isinstance(alvo.value, ast.Attribute)
        and alvo.value.attr == "mark"
    )


def _pula_sempre(decoradores: Sequence[ast.expr]) -> bool:
    """`skip`, ou `skipif` com condição constante verdadeira."""
    for decorador in decoradores:
        if _e_marca(decorador, "skip"):
            return True
        if _e_marca(decorador, "skipif") and isinstance(decorador, ast.Call) and decorador.args:
            condicao = decorador.args[0]
            if isinstance(condicao, ast.Constant) and bool(condicao.value):
                return True
    return False


def _modulo_pulado(arvore: ast.Module) -> bool:
    for no in arvore.body:
        if isinstance(no, ast.Assign) and any(
            isinstance(alvo, ast.Name) and alvo.id == "pytestmark" for alvo in no.targets
        ):
            valores = no.value.elts if isinstance(no.value, (ast.List, ast.Tuple)) else [no.value]
            if _pula_sempre(list(valores)):
                return True
    return False


def _procurar(arvore: ast.Module, partes: list[str]) -> ast.AST | None:
    """A função `partes[-1]` no módulo ou na classe `partes[0]` (`Classe::funcao`)."""
    corpo: list[ast.stmt] = arvore.body
    pulado_pela_classe = False
    for nome_da_classe in partes[:-1]:
        classe = next(
            (n for n in corpo if isinstance(n, ast.ClassDef) and n.name == nome_da_classe), None
        )
        if classe is None:
            return None
        pulado_pela_classe = pulado_pela_classe or _pula_sempre(classe.decorator_list)
        corpo = classe.body
    for no in corpo:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == partes[-1]:
            if pulado_pela_classe:
                no.decorator_list.append(ast.parse("pytest.mark.skip").body[0].value)  # type: ignore[attr-defined]
            return no
    return None


def _conferir_referencia(raiz: Path, referencia: str) -> str | None:
    """O problema da referência, ou `None` se ela é válida."""
    caminho, _, resto = referencia.partition("::")
    partes = [p for p in resto.split("::") if p]
    if not caminho.startswith("tests/") or not caminho.endswith(".py") or not partes:
        return f"{referencia}: referência fora do formato `tests/arquivo.py::teste`"
    arquivo = raiz / caminho
    if not arquivo.is_file():
        return f"{referencia}: arquivo inexistente"
    if not partes[-1].startswith("test_"):
        return f"{referencia}: a função não começa com test_"
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    no = _procurar(arvore, partes)
    if no is None:
        return f"{referencia}: função inexistente no arquivo"
    if _modulo_pulado(arvore) or _pula_sempre(no.decorator_list):  # type: ignore[attr-defined]
        return f"{referencia}: teste pulado (skip)"
    return None


def _conferir_chaves(achadas: set[object], esperadas: Sequence[object], rotulo: str) -> list[str]:
    problemas = []
    faltando = [c for c in esperadas if c not in achadas]
    sobrando = [c for c in achadas if c not in esperadas]
    if faltando:
        problemas.append(f"{rotulo}: faltando {', '.join(map(str, faltando))}")
    if sobrando:
        problemas.append(f"{rotulo}: sobrando {', '.join(map(str, sorted(sobrando, key=str)))}")
    return problemas


def conferir(
    cenarios: Mapping[int, list[str]],
    tecnicos: Mapping[str, list[str]],
    raiz: Path = RAIZ,
) -> list[str]:
    """Os problemas da matriz (lista vazia quando ela está correta)."""
    problemas = _conferir_chaves(set(cenarios), CENARIOS_ESPERADOS, "cenários")
    problemas += _conferir_chaves(set(tecnicos), TECNICOS_ESPERADOS, "testes técnicos")
    for rotulo, mapa in (("cenário", cenarios), ("teste técnico", tecnicos)):
        for chave, referencias in mapa.items():
            if not referencias:
                problemas.append(f"{rotulo} {chave}: lista de testes vazia")
            vistas: set[str] = set()
            for referencia in referencias:
                if referencia in vistas:
                    problemas.append(f"{rotulo} {chave}: referência repetida: {referencia}")
                vistas.add(referencia)
                problema = _conferir_referencia(raiz, referencia)
                if problema is not None:
                    problemas.append(f"{rotulo} {chave}: {problema}")
    return problemas


def conferir_documento(
    documento: Path,
    cenarios: Mapping[int, list[str]],
    tecnicos: Mapping[str, list[str]],
) -> str | None:
    """`None` se o documento versionado é idêntico ao que o gerador produz agora."""
    from tests.rastreabilidade.gerar import gerar_documento

    esperado = gerar_documento(cenarios, tecnicos)
    if not documento.is_file() or documento.read_text(encoding="utf-8") != esperado:
        return f"{documento.name} está desatualizado: rode `python -m tests.rastreabilidade.gerar`"
    return None
