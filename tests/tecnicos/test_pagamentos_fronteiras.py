"""E07-01: o resto do sistema só fala com o simulador pela interface (acceptance A-16)."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
APPS = RAIZ / "apps"
IMPORTA = re.compile(r"^\s*(?:from|import)\s+apps\.simulador_pagamentos\b", re.MULTILINE)
IMPORTA_MODELOS_DE_PAGAMENTOS = re.compile(
    r"^\s*(?:from\s+apps\.pagamentos\.models\b|from\s+apps\.pagamentos\s+import\s+.*\bmodels\b)",
    re.MULTILINE,
)


def modulos(base: Path) -> list[Path]:
    return [p for p in base.rglob("*.py") if "migrations" not in p.parts]


def test_so_a_interface_e_o_proprio_simulador_importam_o_simulador() -> None:  # A-16
    permitidos = {APPS / "pagamentos" / "provedor.py"}
    fora = [
        str(p.relative_to(RAIZ))
        for p in modulos(APPS)
        if IMPORTA.search(p.read_text(encoding="utf-8"))
        and p not in permitidos
        and (APPS / "simulador_pagamentos") not in p.parents
    ]
    assert fora == []
    assert IMPORTA.search((APPS / "pagamentos" / "provedor.py").read_text(encoding="utf-8"))


def test_o_simulador_nao_importa_modelos_de_pagamentos() -> None:  # A-16
    achados = [
        str(p.relative_to(RAIZ))
        for p in modulos(APPS / "simulador_pagamentos")
        if IMPORTA_MODELOS_DE_PAGAMENTOS.search(p.read_text(encoding="utf-8"))
    ]
    assert achados == []
