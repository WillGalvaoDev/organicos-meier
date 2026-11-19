"""A conferência da matriz de rastreabilidade (E16-07, regras 2-A, 3 e 3-A a 3-D).

Lê a árvore de sintaxe dos arquivos de `tests/`: não importa nem roda nenhum teste. A referência só
vale se o pytest a coletaria com a configuração do projeto e se ela não pula nem tem falha
esperada. `pytestmark` e `__test__` só valem nas formas aceitas (regra 3-D); qualquer outra
ocorrência recusa a referência. O pulo feito em tempo de execução (fixture, `conftest.py`) é
conferido pela execução real em `conferir_execucao.py` (regra 3-E).
"""

import ast
import fnmatch
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CENARIOS_ESPERADOS = tuple(range(1, 120))
TECNICOS_ESPERADOS = tuple(f"T-{n}" for n in range(1, 56))
MARCAS_RECUSADAS = ("skip", "skipif", "xfail")
CHAMADAS_RECUSADAS = ("skip", "xfail", "importorskip")
Afirmacoes = Mapping[str, Mapping[str, str]]
MAXIMO_DA_PROVA = 200
PROFUNDIDADE_DOS_AUXILIARES = 2


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
_PALAVRA = re.compile(r"\b(pytestmark|__test__)\b")
_BASES_DE_TESTE = {
    "unittest": {"TestCase"},
    "django.test": {"SimpleTestCase", "TestCase", "TransactionTestCase", "LiveServerTestCase"},
}
_METODOS_DE_ACESSO = ("__getattr__", "__getattribute__", "__init_subclass__")
_CONTEXTOS = {
    ast.If: "if", ast.Try: "try", ast.With: "with", ast.AsyncWith: "with", ast.For: "for",
    ast.AsyncFor: "for", ast.While: "while", ast.FunctionDef: "função",
    ast.AsyncFunctionDef: "função", ast.Match: "match",
}  # fmt: skip


def _pais_de(arvore: ast.AST) -> dict[int, ast.AST]:
    pais: dict[int, ast.AST] = {}
    for no in ast.walk(arvore):
        for filho in ast.iter_child_nodes(no):
            pais[id(filho)] = no
    return pais


def _contexto_de(no: ast.AST, pais: dict[int, ast.AST]) -> str | None:
    """O `if`, `try`, `with`, `for`, `while`, função ou `match` mais próximo que envolve `no`."""
    atual = pais.get(id(no))
    while atual is not None:
        for tipo, nome in _CONTEXTOS.items():
            if isinstance(atual, tipo):
                return nome
        atual = pais.get(id(atual))
    return None


def _forma_do_nome(no: ast.Name, pais: dict[int, ast.AST]) -> str:
    pai = pais.get(id(no))
    if isinstance(no.ctx, ast.Del):
        forma = "removido com del"
    elif isinstance(no.ctx, ast.Load):
        forma = "lido"
        if isinstance(pai, ast.Attribute):
            avo = pais.get(id(pai))
            if isinstance(avo, ast.Call) and avo.func is pai:
                forma = f"lido em chamada de método {pai.attr}"
            else:
                forma = f"lido em acesso ao atributo {pai.attr}"
        elif isinstance(pai, ast.Subscript):
            forma = "lido em subscrito"
    else:
        forma = "definido"
        while isinstance(pai, (ast.Tuple, ast.List, ast.Starred)):
            forma = "em desempacotamento"
            pai = pais.get(id(pai))
        if isinstance(pai, ast.AugAssign):
            forma = "em atribuição aumentada"
        elif isinstance(pai, ast.NamedExpr):
            forma = "no operador :="
        elif isinstance(pai, (ast.For, ast.AsyncFor)):
            forma = "como alvo de for"
        elif isinstance(pai, ast.comprehension):
            forma = "como alvo de compreensão"
        elif isinstance(pai, ast.withitem):
            forma = "como alvo de with"
        elif isinstance(pai, ast.Assign) and len(pai.targets) > 1:
            forma = "em atribuição encadeada"
    contexto = _contexto_de(no, pais)
    if contexto and (forma in ("definido", "lido") or forma.startswith("lido em")):
        forma = f"{forma} dentro de {contexto}"
    return forma


def _docstrings(arvore: ast.AST) -> set[int]:
    achadas: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corpo = no.body
            if (
                corpo
                and isinstance(corpo[0], ast.Expr)
                and isinstance(corpo[0].value, ast.Constant)
                and isinstance(corpo[0].value.value, str)
            ):
                achadas.add(id(corpo[0].value))
    return achadas


def _alvo_aceito(no: ast.stmt) -> ast.Name | None:
    """O nome de controle definido por `no` na forma aceita, ou `None`."""
    if isinstance(no, ast.Assign) and len(no.targets) == 1:
        alvo = no.targets[0]
        if isinstance(alvo, ast.Name) and alvo.id in CONTROLES:
            return alvo
    if isinstance(no, ast.AnnAssign) and no.value is not None:
        if isinstance(no.target, ast.Name) and no.target.id in CONTROLES:
            return no.target
    return None


def _ocorrencias(arvore: ast.Module) -> list[tuple[int, str]]:
    """Toda ocorrência de `pytestmark` e `__test__` que não é a forma aceita (regra 3-D), mais as
    formas que trazem esses nomes sem escrevê-los. Cada item é (linha, motivo)."""
    pais = _pais_de(arvore)
    aceitos: set[int] = set()
    achadas: list[tuple[int, str]] = []
    corpos: list[list[ast.stmt]] = [arvore.body]
    corpos += [no.body for no in ast.walk(arvore) if isinstance(no, ast.ClassDef)]
    for corpo in corpos:
        vistos: set[str] = set()
        for instrucao in corpo:
            alvo = _alvo_aceito(instrucao)
            if alvo is None:
                continue
            if alvo.id in vistos:
                achadas.append(
                    (
                        instrucao.lineno,
                        f"{alvo.id} definido mais de uma vez (linha {instrucao.lineno})",
                    )
                )
            vistos.add(alvo.id)
            aceitos.add(id(alvo))
    docstrings = _docstrings(arvore)
    for no in ast.walk(arvore):
        linha = getattr(no, "lineno", 0)
        if isinstance(no, ast.Name) and no.id in CONTROLES and id(no) not in aceitos:
            forma = _forma_do_nome(no, pais)
            achadas.append((linha, f"{no.id} {forma} (linha {linha})"))
        elif isinstance(no, ast.Attribute) and no.attr in CONTROLES:
            achadas.append((linha, f"{no.attr} como atributo (linha {linha})"))
        elif isinstance(no, ast.alias):
            for nome in (no.name, no.asname):
                if nome in CONTROLES:
                    linha = getattr(no, "lineno", linha)
                    achadas.append((linha, f"{nome} importado (linha {linha})"))
        elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if no.name in CONTROLES:
                achadas.append((linha, f"{no.name} definido como função ou classe (linha {linha})"))
        elif isinstance(no, ast.arg) and no.arg in CONTROLES:
            achadas.append((linha, f"{no.arg} como parâmetro (linha {linha})"))
        elif isinstance(no, ast.keyword) and no.arg in CONTROLES:
            linha = getattr(no, "lineno", linha)
            achadas.append((linha, f"{no.arg} como argumento nomeado (linha {linha})"))
        elif isinstance(no, (ast.Global, ast.Nonlocal)):
            for nome in no.names:
                if nome in CONTROLES:
                    achadas.append((linha, f"{nome} declarado global ou nonlocal (linha {linha})"))
        elif isinstance(no, ast.ExceptHandler) and no.name in CONTROLES:
            achadas.append((linha, f"{no.name} capturado por except (linha {linha})"))
        elif isinstance(no, (ast.MatchAs, ast.MatchStar)) and no.name in CONTROLES:
            achadas.append((linha, f"{no.name} capturado por match (linha {linha})"))
        elif isinstance(no, ast.MatchMapping) and no.rest in CONTROLES:
            achadas.append((linha, f"{no.rest} capturado por match (linha {linha})"))
        elif isinstance(no, ast.Constant) and isinstance(no.value, str):
            if id(no) not in docstrings:
                achado = _PALAVRA.search(no.value)
                if achado:
                    achadas.append((linha, f"{achado.group(1)} em texto literal (linha {linha})"))
        elif isinstance(no, ast.ImportFrom) and any(a.name == "*" for a in no.names):
            achadas.append((linha, f"import * (linha {linha})"))
        elif isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
            if no.func.id in ("exec", "eval", "compile") and not _dentro_de_funcao(no, pais):
                achadas.append((linha, f"{no.func.id} chamado fora de função (linha {linha})"))
    for no in arvore.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == "__getattr__":
            achadas.append((no.lineno, f"__getattr__ definido no módulo (linha {no.lineno})"))
    return sorted(achadas, key=lambda a: (a[0], not a[1].startswith(CONTROLES)))


def _dentro_de_funcao(no: ast.AST, pais: dict[int, ast.AST]) -> bool:
    atual = pais.get(id(no))
    while atual is not None:
        if isinstance(atual, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return True
        atual = pais.get(id(atual))
    return False


def _marcas_do_corpo(
    nomes: _Nomes, corpo: list[ast.stmt], onde: str
) -> tuple[list[ast.expr], str | None]:
    """As marcas do `pytestmark` da forma aceita e o motivo de recusa do valor, se houver:
    `pytestmark` que não é marca do pytest e `__test__` que não é a constante `True`."""
    marcas: list[ast.expr] = []
    for no in corpo:
        alvo = _alvo_aceito(no)
        if alvo is None or not isinstance(no, (ast.Assign, ast.AnnAssign)) or no.value is None:
            continue
        valor = no.value
        if alvo.id == "pytestmark":
            elementos = valor.elts if isinstance(valor, (ast.List, ast.Tuple)) else [valor]
            for elemento in elementos:
                if nomes.marca(elemento) is None:
                    return marcas, f"pytestmark com valor que não se analisa ({onde})"
            marcas.extend(elementos)
        else:
            if isinstance(valor, ast.Constant) and valor.value is False:
                return marcas, f"__test__ = False ({onde})"
            if not (isinstance(valor, ast.Constant) and valor.value is True):
                return marcas, f"__test__ com valor que não é a constante True ({onde})"
    return marcas, None


def _base_aceita(
    base: ast.expr, arvore: ast.Module, classes: dict[str, ast.ClassDef]
) -> str | None:
    """`None` se a base é aceita; senão o motivo. Aceitas: classe do mesmo arquivo, `object`,
    `unittest.TestCase` e as classes de teste de `django.test`."""
    if isinstance(base, ast.Name):
        if base.id in classes or base.id == "object":
            return None
        for no in arvore.body:
            if isinstance(no, ast.ImportFrom) and no.module in _BASES_DE_TESTE:
                for alias in no.names:
                    if (alias.asname or alias.name) == base.id:
                        if alias.name in _BASES_DE_TESTE[no.module]:
                            return None
    if (
        isinstance(base, ast.Attribute)
        and isinstance(base.value, ast.Name)
        and base.value.id == "unittest"
        and base.attr == "TestCase"
        and any(
            isinstance(n, ast.Import)
            and any(a.name == "unittest" and not a.asname for a in n.names)
            for n in arvore.body
        )
    ):
        return None
    texto = ast.unparse(base)
    return f"base {texto} importada de outro lugar ou expressão (a herança não é conferida)"


def _cadeia_da_classe(
    classe: ast.ClassDef, arvore: ast.Module, nomes: _Nomes
) -> tuple[list[ast.ClassDef], str | None]:
    """A classe e as bases do mesmo arquivo, conferidas pelas regras 3-A a 3-D."""
    classes = {n.name: n for n in arvore.body if isinstance(n, ast.ClassDef)}
    cadeia: list[ast.ClassDef] = []
    pendentes = [classe]
    while pendentes:
        atual = pendentes.pop()
        if atual in cadeia:
            continue
        cadeia.append(atual)
        if atual.keywords:
            nome = atual.keywords[0].arg
            return cadeia, f"a classe {atual.name} tem argumento nomeado na definição ({nome}=)"
        for item in atual.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name in _METODOS_DE_ACESSO:
                    return cadeia, f"a classe {atual.name} define {item.name}"
        for base in atual.bases:
            motivo = _base_aceita(base, arvore, classes)
            if motivo:
                return cadeia, f"classe {atual.name}: {motivo}"
            if isinstance(base, ast.Name) and base.id in classes:
                pendentes.append(classes[base.id])
    return cadeia, None


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
    ocorrencias = _ocorrencias(arvore)
    if ocorrencias:
        return f"{referencia}: {ocorrencias[0][1]}"
    marcas_do_modulo, recusa = _marcas_do_corpo(nomes, arvore.body, "módulo")
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
        cadeia, recusa = _cadeia_da_classe(classe, arvore, nomes)
        if recusa:
            return f"{referencia}: {recusa}"
        for membro in cadeia:
            if any(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "__init__"
                for n in membro.body
            ):
                return f"{referencia}: a classe {membro.name} define __init__ (não é coletada)"
            marcas_da_classe, recusa = _marcas_do_corpo(nomes, membro.body, f"classe {membro.name}")
            if recusa:
                return f"{referencia}: {recusa}"
            motivo = _motivo_da_marca(
                nomes, membro.decorator_list, f"decorador da classe {membro.name}"
            ) or _motivo_da_marca(nomes, marcas_da_classe, f"pytestmark da classe {membro.name}")
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


def _normalizar(texto: str) -> str:
    return " ".join(texto.split())


def _trechos_de_prova(funcao: ast.AST, auxiliares: dict[str, ast.AST], fonte: str) -> list[str]:
    """O texto (com espaços normalizados) de cada `assert` e de cada `pytest.raises(...)` da
    função e das funções do mesmo módulo que ela chama pelo nome (até `PROFUNDIDADE...`)."""
    trechos: list[str] = []
    vistas: set[int] = set()

    def visita(no: ast.AST, nivel: int) -> None:
        if id(no) in vistas:
            return
        vistas.add(id(no))
        for filho in ast.walk(no):
            if isinstance(filho, ast.Assert):
                trechos.append(_normalizar(ast.get_source_segment(fonte, filho) or ""))
            elif isinstance(filho, (ast.With, ast.AsyncWith)):
                for item in filho.items:
                    expressao = item.context_expr
                    funcao_chamada = expressao.func if isinstance(expressao, ast.Call) else None
                    nome = getattr(funcao_chamada, "attr", getattr(funcao_chamada, "id", ""))
                    if nome == "raises":
                        trechos.append(_normalizar(ast.get_source_segment(fonte, expressao) or ""))
            elif (
                isinstance(filho, ast.Call)
                and isinstance(filho.func, ast.Name)
                and filho.func.id in auxiliares
                and nivel < PROFUNDIDADE_DOS_AUXILIARES
            ):
                visita(auxiliares[filho.func.id], nivel + 1)

    visita(funcao, 0)
    return trechos


MOTIVO_DA_CONSTANTE = "constante de casos com mais de uma ligação ou alterada no módulo"


def _ligacoes_do_nome(arvore: ast.Module, nome: str) -> list[ast.AST]:
    """Toda ligação do nome no módulo inteiro e todo uso que o altera: atribuição, `+=`, `del`,
    `for`, `with ... as`, `import ... as`, `global`, `nonlocal`, parâmetro, `except ... as`,
    captura de `match`, definição de função ou classe, índice ou fatia no lado esquerdo e
    qualquer chamada de método do nome (`NOME.append(...)`)."""
    achadas: list[ast.AST] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name) and no.id == nome and isinstance(no.ctx, (ast.Store, ast.Del)):
            achadas.append(no)
        elif isinstance(no, ast.arg) and no.arg == nome:
            achadas.append(no)
        elif isinstance(no, ast.alias) and (no.asname or no.name.split(".")[0]) == nome:
            achadas.append(no)
        elif isinstance(no, (ast.Global, ast.Nonlocal)) and nome in no.names:
            achadas.append(no)
        elif isinstance(no, ast.ExceptHandler) and no.name == nome:
            achadas.append(no)
        elif isinstance(no, (ast.MatchAs, ast.MatchStar)) and no.name == nome:
            achadas.append(no)
        elif isinstance(no, ast.MatchMapping) and no.rest == nome:
            achadas.append(no)
        elif (
            isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and no.name == nome
        ):
            achadas.append(no)
        elif (
            isinstance(no, ast.Subscript)
            and isinstance(no.ctx, (ast.Store, ast.Del))
            and isinstance(no.value, ast.Name)
            and no.value.id == nome
        ):
            achadas.append(no)
        elif (
            isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name) and no.value.id == nome
        ):
            achadas.append(no)
    return achadas


def _constante_aceita(arvore: ast.Module, nome: str, linha_do_decorador: int) -> bool:
    """Regra 2-H: uma única ligação no módulo, atribuição simples no nível do módulo, antes do
    decorador, e nunca alterada em outro lugar."""
    ligacoes = _ligacoes_do_nome(arvore, nome)
    if len(ligacoes) != 1:
        return False
    for no in arvore.body:
        if isinstance(no, ast.Assign) and len(no.targets) == 1:
            alvo = no.targets[0]
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvo = no.target
        else:
            continue
        if isinstance(alvo, ast.Name) and alvo.id == nome:
            return no.lineno < linha_do_decorador
    return False


def _decoradores_de_caso(
    arvore: ast.Module, cadeia: Sequence[ast.AST], fonte: str
) -> tuple[list[str], list[str]]:
    """O texto (normalizado) de cada `parametrize` que vale para o teste (o da função e o das
    classes que a contêm) e de cada constante do módulo que esse decorador usa pelo nome e que a
    regra 2-H aceita. Devolve também o texto das constantes recusadas (para o diagnóstico)."""
    aceitos: list[str] = []
    recusados: list[str] = []
    for dono in cadeia:
        for decorador in getattr(dono, "decorator_list", []):
            alvo = decorador.func if isinstance(decorador, ast.Call) else decorador
            if getattr(alvo, "attr", "") != "parametrize":
                continue
            aceitos.append(_normalizar(ast.get_source_segment(fonte, decorador) or ""))
            for nome in {n.id for n in ast.walk(decorador) if isinstance(n, ast.Name)}:
                if _constante_aceita(arvore, nome, decorador.lineno):
                    for no in arvore.body:
                        valor = None
                        if isinstance(no, ast.Assign) and len(no.targets) == 1:
                            alvo_do_no, valor = no.targets[0], no.value
                        elif isinstance(no, ast.AnnAssign) and no.value is not None:
                            alvo_do_no, valor = no.target, no.value
                        if (
                            valor is not None
                            and isinstance(alvo_do_no, ast.Name)
                            and alvo_do_no.id == nome
                        ):
                            aceitos.append(_normalizar(ast.get_source_segment(fonte, valor) or ""))
                elif _ligacoes_do_nome(arvore, nome):
                    recusados.extend(_instrucoes_que_citam(arvore, nome, fonte))
                else:
                    continue
    return aceitos, recusados


def _instrucoes_que_citam(arvore: ast.Module, nome: str, fonte: str) -> list[str]:
    """O texto das instruções que ligam ou alteram o nome (para acusar o caso citado)."""
    textos: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.stmt) and not isinstance(
            no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            if any(isinstance(filho, ast.Name) and filho.id == nome for filho in ast.walk(no)):
                textos.append(_normalizar(ast.get_source_segment(fonte, no) or ""))
    return textos


def _localizar_funcao(
    raiz: Path, referencia: str
) -> tuple[ast.AST, dict[str, ast.AST], str, list[str], list[str]] | None:
    """A função de teste, as funções do módulo (por nome), o texto do arquivo e os casos de
    parametrização do teste."""
    caminho, _, resto = referencia.partition("::")
    partes = [p for p in resto.split("::") if p]
    fonte = (raiz / caminho).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    corpo = arvore.body
    cadeia: list[ast.AST] = []
    for nome_da_classe in partes[:-1]:
        classes = [n for n in corpo if isinstance(n, ast.ClassDef) and n.name == nome_da_classe]
        if not classes:
            return None
        cadeia.append(classes[-1])
        corpo = classes[-1].body
    funcao = _ultima_definicao(corpo, partes[-1])
    if funcao is None:
        return None
    cadeia.append(funcao)
    auxiliares: dict[str, ast.AST] = {}
    for no in arvore.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            auxiliares[no.name] = no  # a última definição vale
    casos, recusados = _decoradores_de_caso(arvore, cadeia, fonte)
    return funcao, auxiliares, fonte, casos, recusados


def _conferir_prova(raiz: Path, referencia: str, prova: str) -> str | None:
    """O motivo de a prova ser inválida, ou `None` (regra 2-D): texto, até 200 caracteres, com
    trecho entre crases copiado de um `assert` ou `pytest.raises(...)` da função ou de uma função
    do módulo que ela chama pelo nome. Todo trecho entre crases tem de estar num desses lugares
    ou no `parametrize` do teste (regra 2-F): um assert correto não esconde um caso inválido."""
    if not prova.strip():
        return "prova sem texto"
    if len(prova) > MAXIMO_DA_PROVA:
        return f"prova com mais de {MAXIMO_DA_PROVA} caracteres"
    trechos = re.findall(r"`([^`]+)`", prova)
    if not trechos:
        return "prova sem trecho do código entre crases"
    localizada = _localizar_funcao(raiz, referencia)
    if localizada is None:
        return "função não localizada"
    funcao, auxiliares, fonte, casos, recusados = localizada
    asserts = _trechos_de_prova(funcao, auxiliares, fonte)
    achou_assert = False
    for trecho in trechos:
        procurado = _normalizar(trecho)
        if procurado not in _normalizar(fonte):
            return f"o trecho `{trecho}` não aparece no arquivo"
        if any(procurado in texto for texto in asserts):
            achou_assert = True
        elif not any(procurado in texto for texto in casos):
            if any(procurado in texto for texto in recusados):
                return f"o trecho `{trecho}` vem de uma {MOTIVO_DA_CONSTANTE}"
            return (
                f"o trecho `{trecho}` aparece no arquivo, mas não num assert, num raises "
                "nem no parametrize do teste (ou numa constante que ele usa)"
            )
    if not achou_assert:
        return "nenhum trecho entre crases vem de um assert ou de um raises do teste"
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
            for afirmacao, provas in afirmacoes.items():
                if not afirmacao.strip():
                    problemas.append(f"{rotulo} {chave}: afirmação com texto vazio")
                if not provas:
                    problemas.append(f"{rotulo} {chave}: afirmação sem testes: {afirmacao[:40]}")
                for referencia, prova in provas.items():
                    problema = _conferir_referencia(raiz, referencia)
                    if problema is not None:
                        problemas.append(f"{rotulo} {chave}: {problema}")
                        continue
                    motivo = _conferir_prova(raiz, referencia, prova)
                    if motivo is not None:
                        problemas.append(
                            f"{rotulo} {chave}: prova inválida em {referencia}: {motivo}"
                        )
    return problemas


CAMPOS_DA_AUDITORIA = ("preparacao", "acao", "resultado", "veredito")
MAXIMO_DO_CAMPO = 200


def conferir_auditoria(
    auditoria: Mapping[tuple[int | str, str, str], Mapping[str, str]],
    cenarios: Mapping[int, Afirmacoes],
    tecnicos: Mapping[str, Afirmacoes],
) -> list[str]:
    """Os problemas da auditoria por ligação (regra 2-G): as chaves são exatamente as ligações da
    matriz, os quatro campos estão preenchidos com até 200 caracteres e o veredito é `"íntegra"` ou
    começa com `"corrigida: "`."""
    ligacoes = {
        (chave, afirmacao, referencia)
        for tabela in (cenarios, tecnicos)
        for chave, afirmacoes in tabela.items()
        for afirmacao, provas in afirmacoes.items()
        for referencia in provas
    }
    problemas: list[str] = []
    for chave in sorted(ligacoes - set(auditoria), key=str):
        problemas.append(f"{chave[0]}: ligação sem linha na auditoria: {chave[2]}")
    for chave in sorted(set(auditoria) - ligacoes, key=str):
        problemas.append(f"{chave[0]}: linha da auditoria sem ligação na matriz: {chave[2]}")
    for chave, linha in auditoria.items():
        onde = f"{chave[0]} {chave[2]}"
        for campo in CAMPOS_DA_AUDITORIA:
            valor = linha.get(campo, "")
            if not valor.strip():
                problemas.append(f"{onde}: campo vazio na auditoria: {campo}")
            elif len(valor) > MAXIMO_DO_CAMPO:
                problemas.append(f"{onde}: {campo} com mais de {MAXIMO_DO_CAMPO} caracteres")
        veredito = linha.get("veredito", "")
        if veredito.strip() and veredito != "íntegra" and not veredito.startswith("corrigida: "):
            problemas.append(
                f'{onde}: veredito inválido (só "íntegra" ou "corrigida: ..."): {veredito[:30]}'
            )
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
