"""E07-02: ambiente e provedor de pagamentos configurados (acceptance A-1 a A-8)."""

import json
import os
import subprocess
import sys

import pytest

from tests.tecnicos.test_configuracao_producao import _AMBIENTE_MINIMO, RAIZ

SEGREDO = "segredo-dos-avisos-so-para-este-teste"
VARIAVEIS_DA_FATIA = ("AMBIENTE", "PROVEDOR_PAGAMENTOS", "SEGREDO_AVISOS_SIMULADOR")
# O ambiente mínimo sem as variáveis desta fatia, que cada teste define.
MINIMO = {k: v for k, v in _AMBIENTE_MINIMO.items() if k not in VARIAVEIS_DA_FATIA}
PROD = {**MINIMO, "SEGREDO_AVISOS_SIMULADOR": SEGREDO}
MENSAGEM_DO_SIMULADOR = "O simulador de pagamentos não pode ser usado em produção."
MENSAGEM_DO_AMBIENTE = "AMBIENTE deve ser 'homologacao' ou 'producao'."


def _ambiente(extra: dict[str, str]) -> dict[str, str]:
    base = {
        k: v
        for k, v in os.environ.items()
        if k not in _AMBIENTE_MINIMO and k not in VARIAVEIS_DA_FATIA
    }
    return {**base, **extra, "PYTHONPATH": str(RAIZ)}


def carregar(modulo: str, extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    codigo = (
        "import json, importlib;"
        f"m = importlib.import_module('{modulo}');"
        "print(json.dumps({'AMBIENTE': getattr(m, 'AMBIENTE', None),"
        "'PROVEDOR_PAGAMENTOS': getattr(m, 'PROVEDOR_PAGAMENTOS', None),"
        "'segredo': bool(getattr(m, 'SEGREDO_AVISOS_SIMULADOR', ''))}))"
    )
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", codigo],
        cwd=RAIZ,
        env=_ambiente(extra),
        capture_output=True,
        text=True,
        check=False,
    )


def lido(resultado: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert resultado.returncode == 0, resultado.stderr
    return dict(json.loads(resultado.stdout.strip().splitlines()[-1]))


def sem_segredos(resultado: subprocess.CompletedProcess[str]) -> None:
    assert _AMBIENTE_MINIMO["SECRET_KEY"] not in resultado.stderr
    assert SEGREDO not in resultado.stderr


@pytest.mark.acceptance
def test_producao_com_o_simulador_nao_carrega() -> None:  # A-1, cenário 38
    resultado = carregar(
        "config.settings.prod",
        {**PROD, "AMBIENTE": "producao", "PROVEDOR_PAGAMENTOS": "simulador"},
    )
    assert resultado.returncode != 0
    assert "ImproperlyConfigured" in resultado.stderr
    assert MENSAGEM_DO_SIMULADOR in resultado.stderr
    sem_segredos(resultado)


def test_producao_sem_provedor_configurado_nao_recebe_o_simulador() -> None:  # A-2
    resultado = carregar("config.settings.prod", {**PROD, "AMBIENTE": "producao"})
    assert resultado.returncode != 0
    assert MENSAGEM_DO_SIMULADOR in resultado.stderr
    sem_segredos(resultado)


@pytest.mark.parametrize("comando", [["check"], ["procrastinate", "worker", "--help"]])
def test_nem_a_web_nem_o_worker_sobem_em_producao_com_o_simulador(comando: list[str]) -> None:
    # A-3
    ambiente = _ambiente(
        {
            **PROD,
            "AMBIENTE": "producao",
            "PROVEDOR_PAGAMENTOS": "simulador",
            "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        }
    )
    resultado = subprocess.run(  # noqa: S603
        [sys.executable, "manage.py", *comando],
        cwd=RAIZ,
        env=ambiente,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode != 0
    assert MENSAGEM_DO_SIMULADOR in resultado.stderr
    sem_segredos(resultado)


def test_homologacao_usa_o_simulador() -> None:  # A-4
    configuracao = lido(
        carregar(
            "config.settings.prod",
            {**PROD, "AMBIENTE": "homologacao", "PROVEDOR_PAGAMENTOS": "simulador"},
        )
    )
    assert configuracao["AMBIENTE"] == "homologacao"
    assert configuracao["PROVEDOR_PAGAMENTOS"] == "simulador"


@pytest.mark.parametrize("ambiente", [None, "teste", "Producao"], ids=["ausente", "teste", "caixa"])
def test_ambiente_invalido_nao_carrega(ambiente: str | None) -> None:  # A-5
    extra = dict(PROD)
    if ambiente is not None:
        extra["AMBIENTE"] = ambiente
    resultado = carregar("config.settings.prod", extra)
    assert resultado.returncode != 0
    assert MENSAGEM_DO_AMBIENTE in resultado.stderr


@pytest.mark.parametrize("provedor", ["mercado_pago", "Simulador", " simulador "])
def test_provedor_diferente_de_simulador_nao_carrega(provedor: str) -> None:  # A-6
    dev = carregar("config.settings.dev", {**MINIMO, "PROVEDOR_PAGAMENTOS": provedor})
    prod = carregar(
        "config.settings.prod", {**PROD, "AMBIENTE": "homologacao", "PROVEDOR_PAGAMENTOS": provedor}
    )
    assert dev.returncode != 0, provedor
    assert prod.returncode != 0, provedor
    assert "PROVEDOR_PAGAMENTOS" in dev.stderr
    assert "PROVEDOR_PAGAMENTOS" in prod.stderr


def test_homologacao_exige_o_segredo_dos_avisos() -> None:  # A-7
    sem_segredo = {k: v for k, v in PROD.items() if k != "SEGREDO_AVISOS_SIMULADOR"}
    resultado = carregar(
        "config.settings.prod",
        {**sem_segredo, "AMBIENTE": "homologacao", "PROVEDOR_PAGAMENTOS": "simulador"},
    )
    assert resultado.returncode != 0
    assert "SEGREDO_AVISOS_SIMULADOR" in resultado.stderr


@pytest.mark.parametrize(
    ("modulo", "ambiente"),
    [("config.settings.dev", "desenvolvimento"), ("config.settings.test", "testes")],
)
def test_dev_e_testes_tem_ambiente_provedor_e_segredo(modulo: str, ambiente: str) -> None:  # A-8
    configuracao = lido(carregar(modulo, MINIMO))
    assert configuracao["AMBIENTE"] == ambiente
    assert configuracao["PROVEDOR_PAGAMENTOS"] == "simulador"
    assert configuracao["segredo"] is True
