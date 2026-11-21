"""E16-01: a rota de saúde `/saude/` (acceptance A-1 a A-4)."""

import json
import logging
import os
import subprocess
import sys
from typing import Any

import pytest
from django.contrib.sessions.models import Session
from django.db.utils import OperationalError
from django.test import Client

from apps.nucleo.auditoria import EntradaAuditoria
from tests.tecnicos.test_configuracao_producao import _AMBIENTE_MINIMO, RAIZ

pytestmark = pytest.mark.django_db


def test_saude_ok_sem_efeito_colateral(client: Client) -> None:  # A-1
    sessoes, auditorias = Session.objects.count(), EntradaAuditoria.objects.count()
    resposta = client.get("/saude/")
    assert resposta.status_code == 200
    assert resposta.content == b"ok"
    assert resposta["Content-Type"].startswith("text/plain")
    assert "Set-Cookie" not in resposta
    assert not resposta.cookies
    assert (Session.objects.count(), EntradaAuditoria.objects.count()) == (sessoes, auditorias)


def test_saude_com_banco_indisponivel(
    client: Client, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:  # A-2
    from django.db.backends.postgresql.base import DatabaseWrapper

    def quebra(self: Any, *args: Any, **kwargs: Any) -> Any:
        raise OperationalError("detalhe secreto do banco: senha=abc")

    monkeypatch.setattr(DatabaseWrapper, "cursor", quebra)
    with caplog.at_level(logging.ERROR):
        resposta = client.get("/saude/")
    assert resposta.status_code == 503
    assert resposta.content == b"indisponivel"
    assert b"secreto" not in resposta.content
    assert any("OperationalError" in r.getMessage() for r in caplog.records)
    assert not any("secreto" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("metodo", ["post", "put", "delete"])
def test_saude_so_aceita_get(client: Client, metodo: str) -> None:  # A-3
    assert getattr(client, metodo)("/saude/").status_code == 405


def test_saude_fica_fora_do_redirecionamento_https(client: Client, settings: Any) -> None:  # A-4
    codigo = (
        "import json, config.settings.prod as m;print(json.dumps(list(m.SECURE_REDIRECT_EXEMPT)))"
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
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_REDIRECT_EXEMPT = json.loads(resultado.stdout.strip().splitlines()[-1])
    assert client.get("/saude/").status_code == 200
    outra = client.get("/entrar/")
    assert outra.status_code == 301
    assert outra["Location"].startswith("https://")
