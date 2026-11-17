"""Gera `docs/rastreabilidade-fase1.md` a partir da matriz (E16-07, regra 4).

`python -m tests.rastreabilidade.gerar [--saida CAMINHO]`. O resumo de cada cenário e a regra de
cada teste técnico são lidos dos documentos-base na hora da geração: um número sem texto
correspondente faz a geração falhar.
"""

import argparse
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from tests.rastreabilidade.conferencia import RAIZ

FUNCIONAL = RAIZ / "organicos-meier-especificacao-funcional.md"
INFRAESTRUTURA = RAIZ / "organicos-meier-infraestrutura.md"
DOCUMENTO = RAIZ / "docs" / "rastreabilidade-fase1.md"
MAXIMO_DO_RESUMO = 100


def _cenarios_do_documento() -> dict[int, str]:
    texto = FUNCIONAL.read_text(encoding="utf-8")
    inicio = texto.index("## 16. Cenários mínimos de aceitação")
    fim = texto.index("\n## ", inicio + 1)
    return {
        int(m.group(1)): m.group(2).strip()
        for m in re.finditer(r"^(\d+)\. (.+)$", texto[inicio:fim], flags=re.MULTILINE)
    }


def _tecnicos_do_documento() -> dict[str, str]:
    """ID -> regra, da tabela de testes técnicos da seção 8."""
    texto = INFRAESTRUTURA.read_text(encoding="utf-8")
    inicio = texto.index("## 8. Critérios de aceitação e testes")
    fim = texto.index("\n## ", inicio + 1)
    regras = {}
    for linha in texto[inicio:fim].splitlines():
        partes = [p.strip() for p in linha.strip().strip("|").split("|")]
        if linha.startswith("| T-") and len(partes) >= 3:
            regras[partes[0]] = partes[-1]
    return regras


def _resumo(texto: str) -> str:
    texto = " ".join(texto.replace("`", "").replace("|", "/").split())
    if len(texto) <= MAXIMO_DO_RESUMO:
        return texto
    return texto[: MAXIMO_DO_RESUMO - 3].rstrip() + "..."


def _afirmacoes(afirmacoes: Mapping[str, Sequence[str]]) -> str:
    """Cada afirmação seguida dos testes que a provam."""
    blocos = []
    for texto, referencias in afirmacoes.items():
        testes = "<br>".join(f"`{r}`" for r in referencias)
        blocos.append(f"**{texto.replace('|', '/')}**<br>{testes}")
    return "<br><br>".join(blocos)


def gerar_documento(
    cenarios: Mapping[int, Mapping[str, Sequence[str]]],
    tecnicos: Mapping[str, Mapping[str, Sequence[str]]],
) -> str:
    textos = _cenarios_do_documento()
    regras = _tecnicos_do_documento()
    linhas = [
        "# Rastreabilidade da fase 1",
        "",
        "Gerado por `python -m tests.rastreabilidade.gerar` a partir de "
        "`tests/rastreabilidade/matriz.py`; não editar à mão (E16-07). Cada linha aponta os "
        "testes que provam o cenário ou o teste técnico.",
        "",
        "## Cenários (§16)",
        "",
        "| Cenário | Resumo | Testes |",
        "|---|---|---|",
    ]
    for numero in sorted(cenarios):
        if numero not in textos:
            raise ValueError(f"cenário {numero} sem texto nos documentos-base")
        linhas.append(f"| {numero} | {_resumo(textos[numero])} | {_afirmacoes(cenarios[numero])} |")
    linhas += [
        "",
        "## Testes técnicos (infraestrutura 8)",
        "",
        "| ID | Regra | Testes |",
        "|---|---|---|",
    ]
    for chave in sorted(tecnicos, key=lambda k: int(k[2:])):
        if chave not in regras:
            raise ValueError(f"teste técnico {chave} sem texto nos documentos-base")
        linhas.append(f"| {chave} | {regras[chave]} | {_afirmacoes(tecnicos[chave])} |")
    return "\n".join(linhas) + "\n"


def main() -> None:
    from tests.rastreabilidade import matriz

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=DOCUMENTO)
    saida: Path = parser.parse_args().saida
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(gerar_documento(matriz.CENARIOS, matriz.TECNICOS), encoding="utf-8")
    print(f"{saida} escrito")


if __name__ == "__main__":
    main()
