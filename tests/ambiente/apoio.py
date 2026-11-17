"""Apoio dos testes de ambiente (E16-R01, regras 14 e 15).

- `variaveis_obrigatorias`: os nomes que `base.py` e `prod.py` leem sem `default` (via `ast`);
- `conferir_dockerfile`: o `RUN` do `collectstatic` do `Dockerfile` tem um valor fictício para cada
  uma, só com nomes não resolvíveis, e nenhuma delas fica em `ENV` ou `ARG`.
"""

import ast
import re
import shlex
from pathlib import Path
from urllib.parse import urlsplit

RAIZ = Path(__file__).resolve().parents[2]
DOMINIOS_FICTICIOS = (".invalid", "localhost")


def variaveis_obrigatorias(textos: dict[str, str] | None = None) -> set[str]:
    """Os nomes literais de `env("NOME")` e `env.<método>("NOME")` sem `default`.

    Entram as condicionais (como `SEGREDO_AVISOS_SIMULADOR`), porque a homologação usa o simulador.
    `textos` troca o conteúdo dos arquivos (para os casos negativos dos testes).
    """
    textos = textos or {
        arquivo: (RAIZ / arquivo).read_text(encoding="utf-8")
        for arquivo in ("config/settings/base.py", "config/settings/prod.py")
    }
    nomes: set[str] = set()
    for texto in textos.values():
        for no in ast.walk(ast.parse(texto)):
            if not isinstance(no, ast.Call) or not no.args:
                continue
            funcao = no.func
            e_env = (isinstance(funcao, ast.Name) and funcao.id == "env") or (
                isinstance(funcao, ast.Attribute)
                and isinstance(funcao.value, ast.Name)
                and funcao.value.id == "env"
            )
            primeiro = no.args[0]
            if (
                e_env
                and isinstance(primeiro, ast.Constant)
                and isinstance(primeiro.value, str)
                and not any(k.arg == "default" for k in no.keywords)
            ):
                nomes.add(primeiro.value)
    return nomes


def _instrucoes(dockerfile: str) -> list[str]:
    """As instruções, com as continuações de linha (`\\`) unidas."""
    juntas = re.sub(r"\\\s*\n", " ", dockerfile)
    return [linha.strip() for linha in juntas.splitlines() if linha.strip() and linha[0] != "#"]


def ambiente_da_coleta(dockerfile: str) -> dict[str, str]:
    """As variáveis `NOME=valor` do `RUN` que executa o `collectstatic`."""
    for instrucao in _instrucoes(dockerfile):
        if instrucao.startswith("RUN ") and "collectstatic" in instrucao:
            return {
                parte.split("=", 1)[0]: parte.split("=", 1)[1]
                for parte in shlex.split(instrucao[4:])
                if re.match(r"^[A-Z][A-Z0-9_]*=", parte)
            }
    return {}


def _hosts_do_valor(nome: str, valor: str) -> list[str]:
    if nome == "ALLOWED_HOSTS":
        return [h.strip() for h in valor.split(",") if h.strip()]
    if "://" in valor:
        return [urlsplit(valor).hostname or ""]
    if "@" in valor:
        return [valor.rsplit("@", 1)[1]]
    return []


def conferir_dockerfile(dockerfile: str, obrigatorias: set[str]) -> list[str]:
    """Os problemas do passo de construção (lista vazia quando está correto)."""
    ambiente = ambiente_da_coleta(dockerfile)
    problemas = [
        f"falta no RUN do collectstatic: {n}" for n in sorted(obrigatorias - set(ambiente))
    ]
    for nome, valor in ambiente.items():
        for host in _hosts_do_valor(nome, valor):
            if not any(host == d or host.endswith(d) for d in DOMINIOS_FICTICIOS):
                problemas.append(f"{nome}: host não fictício: {host}")
    for instrucao in _instrucoes(dockerfile):
        if instrucao.split(" ", 1)[0] in ("ENV", "ARG"):
            for nome in obrigatorias:
                if re.search(rf"\b{re.escape(nome)}\b", instrucao):
                    problemas.append(f"{nome} aparece em {instrucao.split(' ', 1)[0]}")
    return problemas
