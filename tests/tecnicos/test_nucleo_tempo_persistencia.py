"""E01-03: instante gravado e relido do Postgres (acceptance A-9)."""

from datetime import UTC, datetime

import pytest

from tests.apoio.models import ModeloInstante


@pytest.mark.django_db
def test_persistencia_instante_com_microssegundos_volta_igual() -> None:  # A-9
    original = datetime(2026, 10, 14, 15, 0, 0, 123456, tzinfo=UTC)
    criado = ModeloInstante.objects.create(momento=original)
    relido = ModeloInstante.objects.get(pk=criado.pk)
    assert relido.momento == original
    assert relido.momento.utcoffset() is not None
