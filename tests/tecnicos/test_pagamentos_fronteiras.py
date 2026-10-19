"""E07-01: o resto do sistema só fala com o simulador pela interface (acceptance A-16)."""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

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


ESCRITA = re.compile(
    r"\.(?:create|get_or_create|update_or_create|bulk_create|bulk_update|save|update|delete)\("
)
MODELOS_DE_PAGAMENTO = re.compile(r"\b(?:PagamentoNoProvedor|ConsultaDoPagamento)\b")


@pytest.mark.acceptance
def test_so_a_sincronizacao_escreve_nos_registros_de_pagamento() -> None:  # A-12, cenário 37
    permitidos = {
        APPS / "pagamentos" / "sincronizacao.py",
        APPS / "pagamentos" / "models.py",
    }
    escrevem = []
    for modulo in modulos(APPS):
        texto = modulo.read_text(encoding="utf-8")
        if modulo in permitidos or not MODELOS_DE_PAGAMENTO.search(texto):
            continue
        if ESCRITA.search(texto):
            escrevem.append(str(modulo.relative_to(RAIZ)))
    assert escrevem == []
    sincronizacao = (APPS / "pagamentos" / "sincronizacao.py").read_text(encoding="utf-8")
    assert ESCRITA.search(sincronizacao)


def test_nenhuma_rota_comando_ou_admin_registra_pagamento() -> None:  # A-12, cenário 37
    from django.conf import settings
    from django.urls import URLPattern, URLResolver, get_resolver

    assert "django.contrib.admin" not in settings.INSTALLED_APPS

    def rotas(padroes: Any) -> Iterator[URLPattern]:
        for padrao in padroes:
            if isinstance(padrao, URLResolver):
                yield from rotas(padrao.url_patterns)
            else:
                yield padrao

    de_pagamentos = {
        r.name
        for r in rotas(get_resolver().url_patterns)
        if r.callback.__module__.startswith(("apps.pagamentos", "apps.simulador_pagamentos"))
    }
    assert de_pagamentos <= {"pagamentos_avisos"}
    for app in ("pagamentos", "simulador_pagamentos"):
        assert not (APPS / app / "management").exists()
