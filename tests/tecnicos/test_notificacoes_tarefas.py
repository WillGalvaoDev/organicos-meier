"""E04-03: tarefa periódica no Procrastinate e configuração (acceptance A-10 e A-11)."""

from typing import Any

import pytest
from django.conf import settings
from django.core.management import call_command
from procrastinate.contrib.django import app

from apps.notificacoes import tarefas


def _periodicas() -> list[Any]:
    return list(app.periodic_registry.periodic_tasks.values())


def test_a_tarefa_esta_registrada_como_periodica() -> None:  # A-10
    candidatas = [p for p in _periodicas() if p.task.name == "processar_envios_pendentes"]
    assert len(candidatas) == 1
    periodica = candidatas[0]
    assert periodica.cron == "* * * * *"
    assert periodica.task.queueing_lock == "processar_envios_pendentes"


def test_a_tarefa_chama_processar_envios(monkeypatch: pytest.MonkeyPatch) -> None:  # A-10
    chamadas: list[int] = []

    def falso() -> int:
        chamadas.append(1)
        return 0

    monkeypatch.setattr(tarefas, "processar_envios", falso)
    tarefas.processar_envios_pendentes(timestamp=0)
    assert chamadas == [1]


def test_configuracao_do_procrastinate_e_do_email() -> None:  # A-11
    assert "procrastinate.contrib.django" in settings.INSTALLED_APPS
    assert settings.EMAIL_TIMEOUT == 10
    assert getattr(settings, "PROCRASTINATE_AUTODISCOVER_MODULE_NAME", None) == "tarefas"


@pytest.mark.django_db
def test_nao_ha_migracoes_pendentes() -> None:  # A-11
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)
