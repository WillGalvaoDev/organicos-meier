"""E02-02: configuração de produção (acceptance A-18 e A-19)."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]

_AMBIENTE_MINIMO = {
    "SECRET_KEY": "chave-de-teste-nao-secreta",
    "DATABASE_URL": "postgres://u:p@localhost:5433/d",
    "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "DEFAULT_FROM_EMAIL": "contato@exemplo.com.br",
    "ORIGEM_PUBLICA": "https://organicosmeier.exemplo.com.br",
    "GOOGLE_CLIENT_ID": "id-de-cliente-de-teste",
    "GOOGLE_CLIENT_SECRET": "segredo-de-teste",
}


def _carregar_producao(ambiente: dict[str, str]) -> subprocess.CompletedProcess[str]:
    codigo = (
        "import json, importlib;"
        "m = importlib.import_module('config.settings.prod');"
        "print(json.dumps({k: getattr(m, k) for k in ["
        "'SESSION_COOKIE_SECURE','CSRF_COOKIE_SECURE','SESSION_COOKIE_HTTPONLY',"
        "'SESSION_COOKIE_SAMESITE','EMAIL_BACKEND','DEFAULT_FROM_EMAIL',"
        "'AUTH_PASSWORD_VALIDATORS']}))"
    )
    base = {k: v for k, v in os.environ.items() if k not in _AMBIENTE_MINIMO}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", codigo],
        cwd=RAIZ,
        env={**base, **ambiente, "PYTHONPATH": str(RAIZ)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_producao_cookies_seguros() -> None:  # A-18
    resultado = _carregar_producao(_AMBIENTE_MINIMO)
    assert resultado.returncode == 0, resultado.stderr
    configuracao = json.loads(resultado.stdout.strip().splitlines()[-1])
    assert configuracao["SESSION_COOKIE_SECURE"] is True
    assert configuracao["CSRF_COOKIE_SECURE"] is True
    assert configuracao["SESSION_COOKIE_HTTPONLY"] is True
    assert configuracao["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert configuracao["EMAIL_BACKEND"] == _AMBIENTE_MINIMO["EMAIL_BACKEND"]
    assert configuracao["DEFAULT_FROM_EMAIL"] == _AMBIENTE_MINIMO["DEFAULT_FROM_EMAIL"]


def test_producao_sem_email_backend_falha_ao_carregar() -> None:  # A-19
    ambiente = {k: v for k, v in _AMBIENTE_MINIMO.items() if k != "EMAIL_BACKEND"}
    resultado = _carregar_producao(ambiente)
    assert resultado.returncode != 0
    assert "EMAIL_BACKEND" in resultado.stderr


def test_producao_sem_remetente_falha_ao_carregar() -> None:
    ambiente = {k: v for k, v in _AMBIENTE_MINIMO.items() if k != "DEFAULT_FROM_EMAIL"}
    resultado = _carregar_producao(ambiente)
    assert resultado.returncode != 0
    assert "DEFAULT_FROM_EMAIL" in resultado.stderr


def test_producao_sem_credenciais_do_google_falha_ao_carregar() -> None:  # A-17
    for variavel in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        ambiente = {k: v for k, v in _AMBIENTE_MINIMO.items() if k != variavel}
        resultado = _carregar_producao(ambiente)
        assert resultado.returncode != 0, variavel
        assert variavel in resultado.stderr


def _nome_curto(validador: dict[str, object]) -> str:
    return str(validador["NAME"]).rsplit(".", 1)[-1]


def test_validador_de_semelhanca_conhece_os_atributos_da_conta_em_producao() -> None:  # A-24
    resultado = _carregar_producao(_AMBIENTE_MINIMO)
    assert resultado.returncode == 0, resultado.stderr
    validadores = json.loads(resultado.stdout.strip().splitlines()[-1])["AUTH_PASSWORD_VALIDATORS"]
    por_nome = {_nome_curto(v): v for v in validadores}
    assert set(por_nome) == {
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    }
    assert por_nome["UserAttributeSimilarityValidator"]["OPTIONS"] == {
        "user_attributes": ["nome", "email_normalizado"]
    }
    assert por_nome["MinimumLengthValidator"]["OPTIONS"] == {"min_length": 10}


def test_validador_de_semelhanca_conhece_os_atributos_da_conta_em_teste(settings: Any) -> None:
    from django.contrib.auth.password_validation import (
        MinimumLengthValidator,
        UserAttributeSimilarityValidator,
        get_default_password_validators,
    )

    instancias = get_default_password_validators()
    semelhanca = next(v for v in instancias if isinstance(v, UserAttributeSimilarityValidator))
    assert semelhanca.user_attributes == ("nome", "email_normalizado")
    assert semelhanca.max_similarity == 0.7  # o padrão do Django não foi afrouxado
    assert next(v for v in instancias if isinstance(v, MinimumLengthValidator)).min_length == 10
    assert len(instancias) == 4
