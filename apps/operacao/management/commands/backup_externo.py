"""`python manage.py backup_externo`: o backup externo na hora (E16-04), como a tarefa."""

import sys
from typing import Any

from django.core.management.base import BaseCommand

from apps.nucleo.tempo import agora
from apps.operacao.backup import BackupFalhou, fazer_backup_externo


class Command(BaseCommand):
    help = "Faz agora o backup externo cifrado do banco no R2."

    def handle(self, *args: Any, **opcoes: Any) -> None:
        try:
            registro = fazer_backup_externo(agora())
        except BackupFalhou as falha:
            self.stdout.write(f"Backup falhou na etapa {falha.etapa}.")
            sys.exit(1)
        self.stdout.write(f"{registro.chave} ({registro.tamanho_bytes} bytes)")
