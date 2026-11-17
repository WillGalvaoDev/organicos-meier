"""E16-01: artefatos de implantação (acceptance A-12 a A-14).

Só lê os arquivos: a construção da imagem é conferida no CI (A-15).
"""

import re
import tomllib
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
SEGREDOS = (
    "SECRET_KEY",
    "DATABASE_URL",
    "EMAIL_HOST_PASSWORD",
    "GOOGLE_CLIENT_SECRET",
    "SEGREDO_AVISOS_SIMULADOR",
    "GOOGLE_CLIENT_ID",
    "EMAIL_HOST_USER",
    "EMAIL_HOST",
    "EMAIL_BACKEND",
    "DEFAULT_FROM_EMAIL",
    "ALLOWED_HOSTS",
    "ORIGEM_PUBLICA",
)


def _texto(nome: str) -> str:
    return (RAIZ / nome).read_text(encoding="utf-8")


def test_dockerfile_e_dockerignore() -> None:  # A-12
    ignorados = {
        linha.strip().rstrip("/") for linha in _texto(".dockerignore").splitlines() if linha.strip()
    }
    for caminho in (".env", ".venv", "media", ".git", "staticfiles"):
        assert caminho in ignorados, caminho
    dockerfile = _texto("Dockerfile")
    assert "uv sync --locked --no-dev" in dockerfile
    usuario = re.findall(r"^USER\s+(\S+)", dockerfile, flags=re.MULTILINE)
    assert usuario
    assert usuario[-1] not in ("root", "0")
    assert "postgresql-client-17" in dockerfile
    assert "age" in dockerfile
    for linha in dockerfile.splitlines():
        if linha.strip().startswith("ENV"):
            for nome in ("SECRET_KEY", "DATABASE_URL", "PASSWORD", "SENHA"):
                assert nome not in linha, linha


def test_fly_toml() -> None:  # A-13
    config = tomllib.loads(_texto("fly.toml"))
    assert config["primary_region"] == "gru"
    processos = config["processes"]
    assert "gunicorn config.wsgi" in processos["web"]
    assert "procrastinate worker" in processos["worker"]
    assert "migrate --noinput" in config["deploy"]["release_command"]
    http = config["http_service"]
    assert http["internal_port"] == 8000
    assert http["force_https"] is True
    verificacao = http["checks"][0]
    assert verificacao["path"] == "/saude/"
    assert verificacao["method"].upper() == "GET"
    assert verificacao["interval"] == "30s"
    assert verificacao["timeout"] == "5s"
    ambiente = config["env"]
    assert ambiente == {
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "AMBIENTE": "homologacao",
        "PROVEDOR_PAGAMENTOS": "simulador",
        "CANAL_WHATSAPP": "desligado",
        "TZ": "UTC",
    }
    for nome in SEGREDOS:
        assert nome not in ambiente


def test_ci_constroi_a_imagem() -> None:  # A-14
    fluxo = yaml.safe_load(_texto(".github/workflows/ci.yml"))
    jobs = fluxo["jobs"]
    passos_da_imagem = [p.get("run", "") for j in jobs.values() for p in j["steps"]]
    construcao = [p for p in passos_da_imagem if "docker build" in p]
    assert construcao
    assert not any("push" in p for p in construcao)
    passos = [p.get("run", "") for p in jobs["verificacoes"]["steps"]]
    for comando in ("uv sync --locked", "ruff check", "ruff format --check", "mypy", "pytest"):
        assert any(comando in p for p in passos), comando
