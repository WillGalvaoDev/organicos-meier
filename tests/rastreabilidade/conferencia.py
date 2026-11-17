"""A conferência da matriz de rastreabilidade (E16-07, regras 2-A, 3, 3-A e 3-B).

Lê a árvore de sintaxe dos arquivos de `tests/`: não importa nem roda nenhum teste. A referência só
vale se o pytest a coletaria com a configuração do projeto e se ela não pula nem tem falha esperada.
O pulo feito por fixture ou por `conftest.py` não aparece na árvore: o `review.md` registra a lista
de pulados e de falhas esperadas da execução completa do CI e confirma que nenhum está na matriz.
"""

import ast
import fnmatch
from collections.abc import Mapping, Sequence
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CENARIOS_ESPERADOS = tuple(range(1, 120))
TECNICOS_ESPERADOS = tuple(f"T-{n}" for n in range(1, 56))
MARCAS_RECUSADAS = ("skip", "skipif", "xfail")
CHAMADAS_RECUSADAS = ("skip", "xfail", "importorskip")
Afirmacoes = Mapping[str, Sequence[str]]


class _Nomes:
    """Os nomes que o módulo liga ao pytest: `import pytest [as X]`, `from pytest import mark`,
    `from pytest import skip, xfail, importorskip`."""

    def __init__(self, arvore: ast.Module) -> None:
        self.modulo: set[str] = set()
        self.mark: set[str] = set()
        self.funcoes: dict[str, str] = {}
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                self.modulo.update(a.asname or a.name for a in no.names if a.name == "pytest")
            elif isinstance(no, ast.ImportFrom) and no.module == "pytest":
                for alias in no.names:
                    ligado = alias.asname or alias.name
                    if alias.name == "mark":
                        self.mark.add(ligado)
                    elif alias.name in CHAMADAS_RECUSADAS:
                        self.funcoes[ligado] = alias.name
        self.modulo = self.modulo or {"pytest"}

    def marca(self, no: ast.expr) -> str | None:
        """O nome da marca de `pytest.mark.<nome>[(...)]`, `<apelido>.mark.<nome>` ou
        `mark.<nome>`; `None` se a expressão não é uma marca do pytest."""
        alvo = no.func if isinstance(no, ast.Call) else no
        if not isinstance(alvo, ast.Attribute):
            return None
        base = alvo.value
        if isinstance(base, ast.Name) and base.id in self.mark:
            return alvo.attr
        if (
            isinstance(base, ast.Attribute)
            and base.attr == "mark"
            and isinstance(base.value, ast.Name)
            and base.value.id in self.modulo
        ):
            return alvo.attr
        return None

    def chamada(self, no: ast.AST) -> str | None:
        """`skip`, `xfail` ou `importorskip`, se `no` é uma chamada a eles."""
        if not isinstance(no, ast.Call):
            return None
        funcao = no.func
        if isinstance(funcao, ast.Name) and funcao.id in self.funcoes:
            return self.funcoes[funcao.id]
        if (
            isinstance(funcao, ast.Attribute)
            and funcao.attr in CHAMADAS_RECUSADAS
            and isinstance(funcao.value, ast.Name)
            and funcao.value.id in self.modulo
        ):
            return funcao.attr
        return None


def _skipif_pode_pular(marca: ast.expr) -> bool:
    """Só a constante literal `False` não pula. Qualquer outra condição (inclusive em texto) pode
    ser verdadeira no CI, e a conferência não executa código."""
    if not isinstance(marca, ast.Call):
        return True
    condicao = marca.args[0] if marca.args else None
    for palavra in marca.keywords:
        if palavra.arg == "condition":
            condicao = palavra.value
    return not (isinstance(condicao, ast.Constant) and condicao.value is False)


def _motivo_da_marca(nomes: _Nomes, marcas: Sequence[ast.expr]) -> str | None:
    for marca in marcas:
        nome = nomes.marca(marca)
        if nome == "skip":
            return "teste pulado (skip)"
        if nome == "skipif" and _skipif_pode_pular(marca):
            return "teste que pode ser pulado (skipif com condição que não é a constante False)"
        if nome == "xfail":
            return "teste com falha esperada (xfail) não prova o comportamento"
    return None


def _marcas_do_modulo(arvore: ast.Module) -> list[ast.expr]:
    marcas: list[ast.expr] = []
    for no in arvore.body:
        valor: ast.expr | None = None
        if isinstance(no, ast.Assign) and any(
            isinstance(a, ast.Name) and a.id == "pytestmark" for a in no.targets
        ):
            valor = no.value
        elif (
            isinstance(no, ast.AnnAssign)
            and isinstance(no.target, ast.Name)
            and no.target.id == "pytestmark"
        ):
            valor = no.value
        if valor is not None:
            marcas.extend(valor.elts if isinstance(valor, (ast.List, ast.Tuple)) else [valor])
    return marcas


def _define(no: ast.stmt, nome: str, valor: bool) -> bool:
    """`<nome> = <valor>` no corpo (por exemplo, `__test__ = False`)."""
    return (
        isinstance(no, ast.Assign)
        and any(isinstance(a, ast.Name) and a.id == nome for a in no.targets)
        and isinstance(no.value, ast.Constant)
        and no.value.value is valor
    )


def _chamadas_no_nivel_do_modulo(arvore: ast.Module, nomes: _Nomes) -> list[str]:
    """Chamadas a `skip`, `xfail` e `importorskip` executadas na importação do módulo."""
    achadas: list[str] = []

    def visita(no: ast.AST) -> None:
        for filho in ast.iter_child_nodes(no):
            if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            nome = nomes.chamada(filho)
            if nome:
                achadas.append(nome)
            visita(filho)

    visita(arvore)
    return achadas


def _ultima_definicao(
    corpo: list[ast.stmt], nome: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    achada = None
    for no in corpo:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            achada = no
    return achada


def _conferir_referencia(raiz: Path, referencia: str) -> str | None:
    """O problema da referência, ou `None` se ela é válida."""
    caminho, _, resto = referencia.partition("::")
    partes = [p for p in resto.split("::") if p]
    if not caminho.startswith("tests/") or not caminho.endswith(".py") or not partes:
        return f"{referencia}: referência fora do formato `tests/arquivo.py::teste`"
    arquivo = raiz / caminho
    if not arquivo.is_file():
        return f"{referencia}: arquivo inexistente"
    nome_do_arquivo = arquivo.name
    if not (
        fnmatch.fnmatch(nome_do_arquivo, "test_*.py")
        or fnmatch.fnmatch(nome_do_arquivo, "*_test.py")
    ):
        return f"{referencia}: o nome do arquivo não é coletado pelo pytest (test_*.py)"
    if not partes[-1].startswith("test_"):
        return f"{referencia}: a função não começa com test_"
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    nomes = _Nomes(arvore)
    if any(_define(no, "__test__", False) for no in arvore.body):
        return f"{referencia}: o módulo define __test__ = False"
    motivo = _motivo_da_marca(nomes, _marcas_do_modulo(arvore))
    if motivo:
        return f"{referencia}: {motivo} (pytestmark do módulo)"
    if _chamadas_no_nivel_do_modulo(arvore, nomes):
        return f"{referencia}: o módulo chama skip, xfail ou importorskip ao ser importado"
    corpo = arvore.body
    for nome_da_classe in partes[:-1]:
        classes = [n for n in corpo if isinstance(n, ast.ClassDef) and n.name == nome_da_classe]
        if not classes:
            return f"{referencia}: classe inexistente no arquivo"
        classe = classes[-1]
        if not nome_da_classe.startswith("Test"):
            return f"{referencia}: a classe {nome_da_classe} não começa com Test (não é coletada)"
        if any(isinstance(n, ast.FunctionDef) and n.name == "__init__" for n in classe.body):
            return f"{referencia}: a classe {nome_da_classe} define __init__ (não é coletada)"
        if any(_define(n, "__test__", False) for n in classe.body):
            return f"{referencia}: a classe {nome_da_classe} define __test__ = False"
        motivo = _motivo_da_marca(nomes, classe.decorator_list)
        if motivo:
            return f"{referencia}: {motivo} (classe {nome_da_classe})"
        corpo = classe.body
    funcao = _ultima_definicao(corpo, partes[-1])
    if funcao is None:
        return f"{referencia}: função inexistente no arquivo"
    motivo = _motivo_da_marca(nomes, funcao.decorator_list)
    if motivo:
        return f"{referencia}: {motivo}"
    for no in ast.walk(funcao):
        chamada = nomes.chamada(no)
        if chamada:
            return f"{referencia}: o corpo do teste chama {chamada}(...)"
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
    cenarios: Mapping[int, Afirmacoes],
    tecnicos: Mapping[str, Afirmacoes],
    raiz: Path = RAIZ,
) -> list[str]:
    """Os problemas da matriz (lista vazia quando ela está correta)."""
    problemas = _conferir_chaves(set(cenarios), CENARIOS_ESPERADOS, "cenários")
    problemas += _conferir_chaves(set(tecnicos), TECNICOS_ESPERADOS, "testes técnicos")
    for rotulo, mapa in (("cenário", cenarios), ("teste técnico", tecnicos)):
        for chave, afirmacoes in mapa.items():
            if not afirmacoes:
                problemas.append(f"{rotulo} {chave}: nenhuma afirmação")
            for afirmacao, referencias in afirmacoes.items():
                if not afirmacao.strip():
                    problemas.append(f"{rotulo} {chave}: afirmação com texto vazio")
                if not referencias:
                    problemas.append(f"{rotulo} {chave}: afirmação sem testes: {afirmacao[:40]}")
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
    cenarios: Mapping[int, Afirmacoes],
    tecnicos: Mapping[str, Afirmacoes],
) -> str | None:
    """`None` se o documento versionado é idêntico ao que o gerador produz agora."""
    from tests.rastreabilidade.gerar import gerar_documento

    esperado = gerar_documento(cenarios, tecnicos)
    if not documento.is_file() or documento.read_text(encoding="utf-8") != esperado:
        return f"{documento.name} está desatualizado: rode `python -m tests.rastreabilidade.gerar`"
    return None
