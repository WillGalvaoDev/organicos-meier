"""A conferência do alcance do `caminho` pela execução instrumentada (E16-07, regra 2-K, R05-J2).

A existência estática de um ponto não prova que o teste o executa. O comando roda, num subprocesso,
só as referências distintas da matriz com o plugin `tests.rastreabilidade.alcance` e confere que
cada ponto de função (`apps.` e `config.`) e cada `rota:` do `caminho` foi executado em **cada**
caso da referência. As formas `modulo:`, `comando:` e `fonte:` não são conferidas aqui.

`python -m tests.rastreabilidade.conferir_alcance --executar alcance.json`
"""

import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from tests.rastreabilidade.conferencia import PASTAS_DE_PRODUCAO, RAIZ
from tests.rastreabilidade.conferir_execucao import _referencias

Auditoria = Mapping[tuple[int | str, str, str], Mapping[str, str]]
Registro = Mapping[str, Mapping[str, list[str]]]
_CONVERSOR = re.compile(r"<(?:[^>:]+:)?[^>]+>")


def _padrao_da_rota(caminho: str) -> re.Pattern[str]:
    """O `PATH_INFO` casa por inteiro; `<conversor:nome>` casa um segmento não vazio sem `/`."""
    partes = _CONVERSOR.split(caminho)
    return re.compile("[^/]+".join(re.escape(p) for p in partes))


def _casos_de(referencia: str, registro: Registro) -> list[str]:
    return [n for n in registro if n == referencia or n.startswith(f"{referencia}[")]


def _executado(ponto: str, caso: Mapping[str, list[str]]) -> bool | None:
    """`True`/`False` se o ponto é conferido pela execução; `None` se é de outra forma."""
    forma, separador, valor = ponto.partition(":")
    if separador:
        if forma != "rota":
            return None
        metodo, _, caminho = valor.strip().partition(" ")
        padrao = _padrao_da_rota(caminho)
        for requisicao in caso.get("requisicoes", []):
            m, _, path = requisicao.partition(" ")
            if m == metodo and padrao.fullmatch(path):
                return True
        return False
    if ponto.split(".")[0] in PASTAS_DE_PRODUCAO:
        return ponto in caso.get("pontos", [])
    return None


def conferir_alcance(auditoria: Auditoria, registro: Registro) -> list[str]:
    """Os problemas do alcance: `<chave> <referência> [<caso>]: ponto não executado: <ponto>`."""
    problemas: list[str] = []
    for (chave, _afirmacao, referencia), linha in auditoria.items():
        casos = _casos_de(referencia, registro)
        if not casos:
            problemas.append(f"{chave} {referencia}: referência sem registro de alcance")
            continue
        pontos = [p.strip() for p in linha.get("caminho", "").split("; ") if p.strip()]
        for nodeid in casos:
            nome_do_caso = nodeid.removeprefix(referencia).strip("[]") or "único"
            for ponto in pontos:
                if _executado(ponto, registro[nodeid]) is False:
                    problemas.append(
                        f"{chave} {referencia} [{nome_do_caso}]: ponto não executado: {ponto}"
                    )
    return problemas


def main(argumentos: list[str]) -> int:
    from tests.rastreabilidade import auditoria, matriz

    if len(argumentos) != 2 or argumentos[0] != "--executar":
        print("uso: python -m tests.rastreabilidade.conferir_alcance --executar alcance.json")
        return 2
    arquivo = Path(argumentos[1])
    arquivo.unlink(missing_ok=True)
    comando = [
        sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
        "-p", "tests.rastreabilidade.alcance", f"--registrar-alcance={arquivo}",
        *_referencias(matriz.CENARIOS, matriz.TECNICOS),
    ]  # fmt: skip
    resultado = subprocess.run(comando, cwd=RAIZ, check=False)  # noqa: S603
    if resultado.returncode != 0:
        print(f"o pytest do subprocesso falhou (código {resultado.returncode})")
        return 1
    if not arquivo.is_file():
        print(f"o pytest do subprocesso não gravou {arquivo}")
        return 1
    registro = json.loads(arquivo.read_text(encoding="utf-8"))
    problemas = conferir_alcance(auditoria.AUDITORIA, registro)
    for problema in problemas:
        print(problema)
    if not problemas:
        print("Todo ponto de função e de rota foi executado em cada caso.")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
