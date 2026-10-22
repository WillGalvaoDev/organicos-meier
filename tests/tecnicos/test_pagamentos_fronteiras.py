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


ROTAS_DE_PAGAMENTOS = {"pagamentos_avisos"}
ROTAS_DO_SIMULADOR = {
    "simulador_pagamentos_lista",
    "simulador_pagamentos_aprovar",
    "simulador_pagamentos_recusar",
    "simulador_pagamentos_expirar",
    "simulador_pagamentos_entregar",
    "simulador_pagamentos_depositar",
    "simulador_pagamentos_saida",
}


def _rotas_por_app(urlconf: str | None) -> dict[str, set[str]]:
    from django.urls import URLPattern, URLResolver, get_resolver

    def rotas(padroes: Any) -> Iterator[URLPattern]:
        for padrao in padroes:
            if isinstance(padrao, URLResolver):
                yield from rotas(padrao.url_patterns)
            else:
                yield padrao

    por_app: dict[str, set[str]] = {"pagamentos": set(), "simulador_pagamentos": set()}
    for rota in rotas(get_resolver(urlconf).url_patterns):
        for app in por_app:
            if rota.callback.__module__.startswith(f"apps.{app}"):
                por_app[app].add(str(rota.name))
    return por_app


def _confere_as_rotas(urlconf: str | None = None) -> None:
    from django.conf import settings

    assert "django.contrib.admin" not in settings.INSTALLED_APPS
    por_app = _rotas_por_app(urlconf)
    assert por_app["pagamentos"] == ROTAS_DE_PAGAMENTOS
    assert por_app["simulador_pagamentos"] == ROTAS_DO_SIMULADOR
    for app in ("pagamentos", "simulador_pagamentos"):
        assert not (APPS / app / "management").exists()


def test_nenhuma_rota_comando_ou_admin_registra_pagamento() -> None:
    # E07-03 A-12, cenário 37, E08-07 A-9
    _confere_as_rotas()


@pytest.mark.parametrize(
    ("urlconf", "rota"),
    [
        ("tests.apoio.urls_rota_extra_simulador", "simulador_rota_a_mais"),
        ("tests.apoio.urls_rota_extra_pagamentos", "pagamentos_rota_a_mais"),
    ],
    ids=["simulador", "pagamentos"],
)
def test_uma_rota_a_mais_em_qualquer_dos_dois_apps_e_recusada(urlconf: str, rota: str) -> None:
    # E08-07 A-9 (prova negativa)
    with pytest.raises(AssertionError) as erro:
        _confere_as_rotas(urlconf)
    assert rota in str(erro.value)


CAMPOS_DO_BANCO = ("NAME", "HOST", "PORT", "USER")


def test_o_simulador_tem_conexao_propria_para_o_mesmo_banco() -> None:  # A-20, E07-R03
    from django.conf import settings

    alias = settings.DATABASES["simulador_pagamentos"]
    padrao = settings.DATABASES["default"]
    assert {campo: alias[campo] for campo in CAMPOS_DO_BANCO} == {
        campo: padrao[campo] for campo in CAMPOS_DO_BANCO
    }
    assert settings.DATABASE_ROUTERS == ["apps.simulador_pagamentos.roteador.RoteadorDoSimulador"]


def test_o_roteador_manda_o_simulador_para_a_conexao_propria() -> None:  # A-20
    from apps.pagamentos.models import PagamentoNoProvedor
    from apps.simulador_pagamentos.models import AvisoSimulado, CobrancaSimulada
    from apps.simulador_pagamentos.roteador import RoteadorDoSimulador

    roteador = RoteadorDoSimulador()
    for modelo in (CobrancaSimulada, AvisoSimulado):
        assert roteador.db_for_read(modelo) == "simulador_pagamentos"
        assert roteador.db_for_write(modelo) == "simulador_pagamentos"
    assert roteador.db_for_read(PagamentoNoProvedor) is None
    assert roteador.db_for_write(PagamentoNoProvedor) is None
    assert roteador.allow_migrate("default", "simulador_pagamentos") is True
    assert roteador.allow_migrate("simulador_pagamentos", "simulador_pagamentos") is False


def test_a_producao_tambem_declara_a_conexao_do_simulador() -> None:  # A-20
    import json
    import os
    import subprocess
    import sys

    from tests.tecnicos.test_configuracao_producao import _AMBIENTE_MINIMO

    codigo = (
        "import json, importlib;"
        "m = importlib.import_module('config.settings.prod');"
        "campos = " + repr(list(CAMPOS_DO_BANCO)) + ";"
        "print(json.dumps({'bancos': {a: {c: str(m.DATABASES[a][c]) for c in campos}"
        " for a in m.DATABASES}, 'roteadores': m.DATABASE_ROUTERS}))"
    )
    base = {k: v for k, v in os.environ.items() if k not in _AMBIENTE_MINIMO}
    resultado = subprocess.run(  # noqa: S603
        [sys.executable, "-c", codigo],
        cwd=RAIZ,
        env={**base, **_AMBIENTE_MINIMO, "PYTHONPATH": str(RAIZ)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    lido = json.loads(resultado.stdout.strip().splitlines()[-1])
    assert lido["bancos"]["simulador_pagamentos"] == lido["bancos"]["default"]
    assert lido["roteadores"] == ["apps.simulador_pagamentos.roteador.RoteadorDoSimulador"]


@pytest.mark.django_db
def test_as_migracoes_nao_acusam_mudanca() -> None:  # A-20
    from django.core.management import call_command

    call_command("makemigrations", check=True, dry_run=True, verbosity=0)
