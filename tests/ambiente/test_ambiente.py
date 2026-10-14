"""Verificação do andaime técnico: confirma que o ambiente atende às premissas da infraestrutura.

Não testa comportamento de negócio. Os testes de negócio ficam em tests/aceitacao e tests/tecnicos,
escritos antes do código de cada fatia (AGENTS.md).
"""

import pytest
from django.conf import settings
from django.db import connection


@pytest.mark.django_db
def test_banco_e_postgres() -> None:
    assert connection.vendor == "postgresql"
    with connection.cursor() as cursor:
        cursor.execute("SHOW server_version_num")
        (versao,) = cursor.fetchone()
    assert int(versao) >= 160000


def test_instantes_em_utc_exibidos_no_fuso_da_operacao() -> None:
    assert settings.USE_TZ is True
    assert settings.TIME_ZONE == "America/Sao_Paulo"
