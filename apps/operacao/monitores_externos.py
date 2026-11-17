"""Os monitores de cron do Sentry (E16-03), independentes do worker.

Os alertas internos da E15 dependem do worker: com ele parado por inteiro, só o painel mostra o
atraso. O monitor de cron do Sentry detecta o check-in que não chega, de fora do Fly.io. Só duas
tarefas entram: a verificação operacional (que já acusa o atraso das outras) e o backup diário.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import sentry_sdk.crons

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitorExterno:
    schedule: str  # crontab, em UTC
    checkin_margin: int  # minutos
    max_runtime: int  # minutos


MONITORES_EXTERNOS: dict[str, MonitorExterno] = {
    "verificar_operacao": MonitorExterno("*/5 * * * *", checkin_margin=10, max_runtime=5),
    "backup_diario": MonitorExterno("0 6 * * *", checkin_margin=120, max_runtime=60),
}


def slug_do_monitor(nome: str) -> str:
    return nome.replace("_", "-")


def _enviar(nome: str, monitor: MonitorExterno, status: str, check_in_id: str | None) -> str | None:
    """Um check-in. Erro do SDK ou da rede só vai ao log (a tarefa não depende do Sentry)."""
    try:
        return sentry_sdk.crons.capture_checkin(
            monitor_slug=slug_do_monitor(nome),
            check_in_id=check_in_id,
            status=status,
            monitor_config={
                "schedule": {"type": "crontab", "value": monitor.schedule},
                "checkin_margin": monitor.checkin_margin,
                "max_runtime": monitor.max_runtime,
                "timezone": "UTC",
            },
        )
    except Exception as erro:
        logger.error("check-in do monitor falhou: tarefa=%s erro=%s", nome, type(erro).__name__)
        return check_in_id


@contextmanager
def checkins_da_tarefa(nome: str) -> Iterator[None]:
    """`in_progress` ao começar, `ok` ao concluir e `error` quando o corpo levanta exceção (que
    continua sendo repassada). Tarefa fora de `MONITORES_EXTERNOS`: não envia nada."""
    monitor = MONITORES_EXTERNOS.get(nome)
    if monitor is None:
        yield
        return
    check_in_id = _enviar(nome, monitor, "in_progress", None)
    try:
        yield
    except Exception:
        _enviar(nome, monitor, "error", check_in_id)
        raise
    _enviar(nome, monitor, "ok", check_in_id)
