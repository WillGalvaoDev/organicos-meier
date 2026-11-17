"""E16-01: configuração de homologação em `config.settings.prod` (acceptance A-5 a A-11).

Cada teste carrega as configurações num subprocesso, com o "ambiente fictício completo" (AF).
"""

import json
import os
import subprocess
import sys
from typing import Any

import pytest

from tests.tecnicos.test_configuracao_producao import _AMBIENTE_MINIMO, RAIZ

AF = {
    **_AMBIENTE_MINIMO,
    "AMBIENTE": "homologacao",
    # chave longa o bastante para a verificação `security.W009` do `check --deploy`
    "SECRET_KEY": "chave-de-homologacao-so-para-testes-0123456789-abcdefghijklmnopqrstuvwxyz",
    "PROVEDOR_PAGAMENTOS": "simulador",
    "CANAL_WHATSAPP": "desligado",
    "EMAIL_HOST": "email-smtp.sa-east-1.amazonaws.com",
    "EMAIL_HOST_USER": "usuario-de-teste",
    "EMAIL_HOST_PASSWORD": "senha-de-teste-do-smtp",
}
MENSAGEM_DE_HOSTS = "ALLOWED_HOSTS deve listar os domínios do ambiente."
MENSAGEM_DE_TLS = "DATABASE_URL deve exigir TLS (sslmode=require)."
MENSAGEM_DO_POOL = "DATABASE_URL deve usar a conexão direta do Neon, sem -pooler."
SENHA = "senha-secreta-do-banco"


def carregar(
    extra: dict[str, str] | None = None,
    *,
    sem: tuple[str, ...] = (),
    modulo: str = "config.settings.prod",
    atributos: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    """Carrega o módulo de configurações e imprime os atributos pedidos como JSON."""
    # o `.env` local (ignorado pelo git) não entra: o teste só vê o ambiente que monta
    codigo = (
        "import json, importlib, environ;"
        "environ.Env.read_env = classmethod(lambda cls, *a, **k: None);"
        f"m = importlib.import_module('{modulo}');"
        f"print(json.dumps({{k: getattr(m, k, None) for k in {list(atributos)!r}}}, default=str))"
    )
    base = {k: v for k, v in os.environ.items() if k not in AF and k not in sem}
    ambiente = {k: v for k, v in {**AF, **(extra or {})}.items() if k not in sem}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", codigo],
        cwd=RAIZ,
        env={**base, **ambiente, "PYTHONPATH": str(RAIZ)},
        capture_output=True,
        text=True,
        check=False,
    )


def lido(resultado: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert resultado.returncode == 0, resultado.stderr
    return dict(json.loads(resultado.stdout.strip().splitlines()[-1]))


def test_allowed_hosts_e_obrigatorio() -> None:  # A-5
    ausente = carregar(sem=("ALLOWED_HOSTS",))
    assert ausente.returncode != 0
    assert "ALLOWED_HOSTS" in ausente.stderr
    for valor in ("*", ""):
        resultado = carregar({"ALLOWED_HOSTS": valor})
        assert resultado.returncode != 0
        assert "ImproperlyConfigured" in resultado.stderr
        assert MENSAGEM_DE_HOSTS in resultado.stderr


def test_origens_confiaveis_derivam_da_origem_publica() -> None:  # A-6
    dados = lido(carregar(atributos=("CSRF_TRUSTED_ORIGINS", "ALLOWED_HOSTS")))
    assert dados["CSRF_TRUSTED_ORIGINS"] == ["https://homolog.exemplo.fly.dev"]
    assert dados["ALLOWED_HOSTS"] == ["homolog.exemplo.fly.dev"]


@pytest.mark.parametrize(
    ("url", "mensagem"),
    [
        (f"postgres://u:{SENHA}@ep-x.sa-east-1.aws.neon.tech/d", MENSAGEM_DE_TLS),
        (f"postgres://u:{SENHA}@ep-x.sa-east-1.aws.neon.tech/d?sslmode=disable", MENSAGEM_DE_TLS),
        (
            f"postgres://u:{SENHA}@ep-x-pooler.sa-east-1.aws.neon.tech/d?sslmode=require",
            MENSAGEM_DO_POOL,
        ),
    ],
)
def test_banco_sem_tls_ou_com_pool_e_recusado(url: str, mensagem: str) -> None:  # A-7
    resultado = carregar({"DATABASE_URL": url})
    assert resultado.returncode != 0
    assert "ImproperlyConfigured" in resultado.stderr
    assert mensagem in resultado.stderr
    assert SENHA not in resultado.stderr
    assert url not in resultado.stderr


@pytest.mark.parametrize("modo", ["require", "verify-full"])
def test_banco_com_tls_carrega(modo: str) -> None:  # A-8
    url = f"postgres://u:p@ep-x.sa-east-1.aws.neon.tech/d?sslmode={modo}"
    dados = lido(carregar({"DATABASE_URL": url}, atributos=("DATABASES",)))
    padrao = dados["DATABASES"]["default"]
    assert padrao["CONN_MAX_AGE"] == 60
    assert padrao["CONN_HEALTH_CHECKS"] is True
    assert padrao["OPTIONS"]["sslmode"] == modo


def test_a_recusa_do_simulador_em_producao_continua() -> None:  # A-9
    resultado = carregar({"AMBIENTE": "producao"})
    assert resultado.returncode != 0
    assert "O simulador de pagamentos não pode ser usado em produção." in resultado.stderr


def test_estaticos_pelo_whitenoise_so_em_producao() -> None:  # A-10
    dados = lido(carregar(atributos=("STORAGES", "MIDDLEWARE")))
    assert dados["STORAGES"]["staticfiles"]["BACKEND"] == (
        "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )
    middleware = dados["MIDDLEWARE"]
    posicao = middleware.index("django.middleware.security.SecurityMiddleware")
    assert middleware[posicao + 1] == "whitenoise.middleware.WhiteNoiseMiddleware"
    de_teste = lido(carregar(modulo="config.settings.test", atributos=("STORAGES", "MIDDLEWARE")))
    assert "whitenoise" not in json.dumps(de_teste)


def test_check_deploy_passa_sem_aviso() -> None:  # A-11
    base = {k: v for k, v in os.environ.items() if k not in AF}
    resultado = subprocess.run(
        [
            sys.executable,
            "manage.py",
            "check",
            "--deploy",
            "--fail-level",
            "WARNING",
        ],
        cwd=RAIZ,
        env={**base, **AF, "DJANGO_SETTINGS_MODULE": "config.settings.prod"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    codigo = (
        "import re, pathlib;"
        "t = pathlib.Path('config/settings/prod.py').read_text(encoding='utf-8');"
        "m = re.search(r'SILENCED_SYSTEM_CHECKS = \\[(.*?)\\]', t, re.S);"
        "print(m.group(1) if m else '')"
    )
    bloco = subprocess.run(  # noqa: S603
        [sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout
    linhas = bloco.splitlines()
    for indice, linha in enumerate(linhas):
        if '"' in linha and "#" not in linha:
            anterior = linhas[indice - 1] if indice else ""
            assert anterior.strip().startswith("#"), f"verificação silenciada sem motivo: {linha}"


# --- E16-02: arquivos enviados no R2 (A-1 a A-3) ------------------------------------------------

VARIAVEIS_DO_R2 = ("R2_ENDPOINT", "R2_BUCKET_ARQUIVOS", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")


def test_o_armazenamento_padrao_e_o_r2() -> None:  # A-1
    dados = lido(carregar(atributos=("STORAGES",)))
    padrao = dados["STORAGES"]["default"]
    assert padrao["BACKEND"] == "storages.backends.s3.S3Storage"
    opcoes = padrao["OPTIONS"]
    assert opcoes["bucket_name"] == AF["R2_BUCKET_ARQUIVOS"]
    assert opcoes["endpoint_url"] == AF["R2_ENDPOINT"]
    assert opcoes["region_name"] == "auto"
    assert opcoes["default_acl"] is None
    assert opcoes["querystring_auth"] is True
    assert opcoes["querystring_expire"] == 300
    assert opcoes["file_overwrite"] is False


@pytest.mark.parametrize("variavel", VARIAVEIS_DO_R2)
def test_cada_variavel_do_r2_e_obrigatoria(variavel: str) -> None:  # A-2
    resultado = carregar(sem=(variavel,))
    assert resultado.returncode != 0
    assert variavel in resultado.stderr
    for nome in VARIAVEIS_DO_R2:
        assert AF[nome] not in resultado.stderr


def test_o_armazenamento_de_teste_e_o_local() -> None:  # A-3
    from django.conf import settings

    # `config.settings.test` roda esta suíte: o armazenamento padrão é o do Django, em disco
    assert settings.SETTINGS_MODULE == "config.settings.test"
    assert settings.STORAGES["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"


# --- E16-03: observabilidade (A-1, A-2 e A-13) --------------------------------------------------


def test_o_sentry_e_obrigatorio_em_homologacao() -> None:  # A-1
    resultado = carregar(sem=("SENTRY_DSN",))
    assert resultado.returncode != 0
    assert "SENTRY_DSN" in resultado.stderr


def test_as_opcoes_do_sentry_em_homologacao() -> None:  # A-2
    codigo = (
        "import json, importlib, environ, sentry_sdk;"
        "environ.Env.read_env = classmethod(lambda cls, *a, **k: None);"
        "importlib.import_module('config.settings.prod');"
        "o = sentry_sdk.get_client().options;"
        "r = {k: o.get(k) for k in ('environment', 'send_default_pii', 'include_local_variables',"
        " 'max_request_body_size', 'traces_sample_rate')};"
        "r['before_send'] = getattr(o.get('before_send'), '__name__', None);"
        "r['before_breadcrumb'] = getattr(o.get('before_breadcrumb'), '__name__', None);"
        "print(json.dumps(r))"
    )
    base = {k: v for k, v in os.environ.items() if k not in AF}
    resultado = subprocess.run(  # noqa: S603
        [sys.executable, "-c", codigo],
        cwd=RAIZ,
        env={**base, **AF, "PYTHONPATH": str(RAIZ)},
        capture_output=True,
        text=True,
        check=False,
    )
    opcoes = lido(resultado)
    assert opcoes["environment"] == "homologacao"
    assert not opcoes["send_default_pii"]
    assert not opcoes["include_local_variables"]
    assert opcoes["max_request_body_size"] == "never"
    assert opcoes["traces_sample_rate"] == 0
    assert opcoes["before_send"] == "antes_de_enviar"
    assert opcoes["before_breadcrumb"] == "antes_do_breadcrumb"


def test_a_suite_nao_envia_nada_ao_sentry() -> None:  # A-13
    from django.conf import settings

    assert settings.SETTINGS_MODULE == "config.settings.test"
    assert settings.SENTRY_DSN == ""
    assert not os.environ.get("SENTRY_DSN")
    fluxo = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "SENTRY_DSN" not in fluxo
