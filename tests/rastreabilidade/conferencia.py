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
    """O pytest pula quando QUALQUER condição é verdadeira, e a conferência não executa código:
    só vale `skipif` em que todas as condições (posicionais e `condition=`) são a constante
    literal `False`. `skipif` sem condição pula, e também é recusado."""
    if not isinstance(marca, ast.Call):
        return True
    condicoes = [*marca.args, *(p.value for p in marca.keywords if p.arg == "condition")]
    if not condicoes:
        return True
    return not all(isinstance(c, ast.Constant) and c.value is False for c in condicoes)


def _motivo_da_marca(nomes: _Nomes, marcas: Sequence[ast.expr], onde: str) -> str | None:
    """O motivo de recusa, citando a forma e onde ela está (`onde`)."""
    for marca in marcas:
        nome = nomes.marca(marca)
        if nome == "skip":
            return f"{onde} com skip (teste pulado)"
        if nome == "skipif" and _skipif_pode_pular(marca):
            return f"{onde} com skipif (pode pular: nem toda condição é a constante False)"
        if nome == "xfail":
            return f"{onde} com xfail (falha esperada não prova o comportamento)"
    return None


CONTROLES = ("pytestmark", "__test__")


def _nomes_alvo(alvo: ast.expr) -> set[str]:
    """Os nomes simples que a atribuição liga (inclusive dentro de tupla, lista ou `*`)."""
    if isinstance(alvo, ast.Name):
        return {alvo.id}
    if isinstance(alvo, (ast.Tuple, ast.List)):
        return set().union(*(_nomes_alvo(e) for e in alvo.elts)) if alvo.elts else set()
    if isinstance(alvo, ast.Starred):
        return _nomes_alvo(alvo.value)
    return set()


def _toca_controle(no: ast.AST) -> str | None:
    """O nome de controle (`pytestmark` ou `__test__`) que `no` altera de um jeito que a árvore
    não analisa: atribuição aumentada, desempacotamento, chamada de método, `setattr` ou
    `globals()[...]`. `None` se não há nada disso."""
    if isinstance(no, ast.AugAssign):
        achados = _nomes_alvo(no.target) & set(CONTROLES)
        return f"{sorted(achados)[0]} com atribuição aumentada" if achados else None
    if isinstance(no, ast.Assign):
        for alvo in no.targets:
            if isinstance(alvo, (ast.Tuple, ast.List)) and _nomes_alvo(alvo) & set(CONTROLES):
                return "pytestmark ou __test__ por desempacotamento"
            if isinstance(alvo, ast.Subscript) and isinstance(alvo.value, ast.Call):
                return "pytestmark ou __test__ por globals()[...]"
    if isinstance(no, ast.Expr) and isinstance(no.value, ast.Call):
        chamada = no.value
        funcao = chamada.func
        if (
            isinstance(funcao, ast.Attribute)
            and isinstance(funcao.value, ast.Name)
            and funcao.value.id in CONTROLES
        ):
            return f"{funcao.value.id}.{funcao.attr}(...)"
        if isinstance(funcao, ast.Name) and funcao.id == "setattr":
            literais = {a.value for a in chamada.args if isinstance(a, ast.Constant)}
            if literais & set(CONTROLES):
                return "setattr de pytestmark ou __test__"
    return None


def _definicao_aninhada(corpo: list[ast.stmt]) -> str | None:
    """`pytestmark` ou `__test__` definido dentro de `if`, `try`, `with`, `for` ou `while`."""
    for no in corpo:
        if isinstance(no, (ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.While)):
            for filho in ast.walk(no):
                if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                alvos: list[ast.expr] = []
                if isinstance(filho, ast.Assign):
                    alvos = list(filho.targets)
                elif isinstance(filho, (ast.AnnAssign, ast.AugAssign)):
                    alvos = [filho.target]
                for alvo in alvos:
                    achados = _nomes_alvo(alvo) & set(CONTROLES)
                    if achados:
                        return (
                            f"{sorted(achados)[0]} definido dentro de {type(no).__name__.lower()}"
                        )
    return None


def _controle_do_corpo(
    nomes: _Nomes, corpo: list[ast.stmt], onde: str
) -> tuple[list[ast.expr], str | None]:
    """As marcas do `pytestmark` do corpo (módulo ou classe) e o motivo de recusa, se houver:
    forma que não se pode analisar, `__test__` que não é a constante `True` (ou `False`, que já
    recusa) e marca que não é do pytest."""
    marcas: list[ast.expr] = []
    aninhado = _definicao_aninhada(corpo)
    if aninhado:
        return marcas, f"{aninhado} ({onde})"
    for no in corpo:
        forma = _toca_controle(no)
        if forma:
            return marcas, f"{forma} ({onde})"
        alvo: ast.expr | None = None
        valor: ast.expr | None = None
        if isinstance(no, ast.Assign) and len(no.targets) == 1:
            alvo, valor = no.targets[0], no.value
        elif isinstance(no, ast.AnnAssign):
            alvo, valor = no.target, no.value
        if not isinstance(alvo, ast.Name) or valor is None:
            continue
        if alvo.id == "pytestmark":
            elementos = valor.elts if isinstance(valor, (ast.List, ast.Tuple)) else [valor]
            for elemento in elementos:
                if nomes.marca(elemento) is None:
                    return marcas, f"pytestmark com valor que não se analisa ({onde})"
            marcas.extend(elementos)
        elif alvo.id == "__test__":
            if isinstance(valor, ast.Constant) and valor.value is False:
                return marcas, f"__test__ = False ({onde})"
            if not (isinstance(valor, ast.Constant) and valor.value is True):
                return marcas, f"__test__ com valor que não é a constante True ({onde})"
    return marcas, None


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
    marcas_do_modulo, recusa = _controle_do_corpo(nomes, arvore.body, "módulo")
    if recusa:
        return f"{referencia}: {recusa}"
    motivo = _motivo_da_marca(nomes, marcas_do_modulo, "pytestmark do módulo")
    if motivo:
        return f"{referencia}: {motivo}"
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
        marcas_da_classe, recusa = _controle_do_corpo(
            nomes, classe.body, f"classe {nome_da_classe}"
        )
        if recusa:
            return f"{referencia}: {recusa}"
        motivo = _motivo_da_marca(
            nomes, classe.decorator_list, f"decorador da classe {nome_da_classe}"
        ) or _motivo_da_marca(nomes, marcas_da_classe, f"pytestmark da classe {nome_da_classe}")
        if motivo:
            return f"{referencia}: {motivo}"
        corpo = classe.body
    funcao = _ultima_definicao(corpo, partes[-1])
    if funcao is None:
        return f"{referencia}: função inexistente no arquivo"
    motivo = _motivo_da_marca(nomes, funcao.decorator_list, "decorador da função")
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
