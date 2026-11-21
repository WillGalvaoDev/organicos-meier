"""A conferência da matriz pela execução real (E16-07, regra 3-E).

A árvore de sintaxe não vê pulo feito em tempo de execução (fixture, `conftest.py`, decorador). O
CI grava o relatório JUnit da suíte (`--junitxml=relatorio-pytest.xml`) e esta etapa confere que
cada referência da matriz tem pelo menos um `testcase` e que todos passaram.

`python -m tests.rastreabilidade.conferir_execucao relatorio-pytest.xml`
"""

import sys
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path

from tests.rastreabilidade.conferencia import Afirmacoes


def _referencias(
    cenarios: Mapping[int, Afirmacoes], tecnicos: Mapping[str, Afirmacoes]
) -> list[str]:
    vistas: dict[str, None] = {}
    for mapa in (cenarios, tecnicos):
        for afirmacoes in mapa.values():
            for provas in afirmacoes.values():
                for referencia in provas:
                    vistas[referencia] = None
    return list(vistas)


def _resultado(caso: ET.Element) -> str:
    if caso.find("error") is not None:
        return "error"
    if caso.find("failure") is not None:
        return "failure"
    pulo = caso.find("skipped")
    if pulo is not None:
        return "skipped (xfail)" if pulo.get("type") == "pytest.xfail" else "skipped"
    return "passed"


def conferir_execucao(
    relatorio: Path,
    cenarios: Mapping[int, Afirmacoes],
    tecnicos: Mapping[str, Afirmacoes],
) -> list[str]:
    """Os problemas da execução (lista vazia quando toda referência passou). A correspondência é
    pelo módulo em notação de pontos, pela classe (se houver) e pelo nome, com ou sem `[...]`."""
    casos = list(ET.parse(relatorio).getroot().iter("testcase"))  # noqa: S314
    problemas: list[str] = []
    for referencia in _referencias(cenarios, tecnicos):
        caminho, _, resto = referencia.partition("::")
        partes = [p for p in resto.split("::") if p]
        nome = partes[-1]
        esperado = ".".join([caminho.removesuffix(".py").replace("/", "."), *partes[:-1]])
        achados = [
            caso
            for caso in casos
            if caso.get("classname") == esperado
            and (caso.get("name") == nome or (caso.get("name") or "").startswith(f"{nome}["))
        ]
        if not achados:
            problemas.append(f"{referencia}: sem testcase no relatório")
            continue
        resultados = sorted({_resultado(c) for c in achados} - {"passed"})
        if resultados:
            problemas.append(f"{referencia}: não passou ({', '.join(resultados)})")
    return problemas


def main(argumentos: list[str]) -> int:
    from tests.rastreabilidade import matriz

    if len(argumentos) != 1:
        print("uso: python -m tests.rastreabilidade.conferir_execucao relatorio-pytest.xml")
        return 2
    problemas = conferir_execucao(Path(argumentos[0]), matriz.CENARIOS, matriz.TECNICOS)
    for problema in problemas:
        print(problema)
    if not problemas:
        print("Toda referência da matriz passou na execução.")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
