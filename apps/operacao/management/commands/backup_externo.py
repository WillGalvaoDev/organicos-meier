"""`python manage.py backup_externo`: o backup externo na hora (E16-04), como a tarefa."""

import sys
from typing import Any

from django.core.management.base import BaseCommand

from apps.nucleo.tempo import agora
from apps.operacao.backup import BackupFalhou, fazer_backup_externo

MENSAGENS_DA_RESERVA = {
    "EmAndamento": "Outro backup está em andamento.",
    "ChaveExistente": "Já existe um backup com esta chave; nada foi substituído.",
}


class Command(BaseCommand):
    help = "Faz agora o backup externo cifrado do banco no R2."

    def handle(self, *args: Any, **opcoes: Any) -> None:
        try:
            registro = fazer_backup_externo(agora())
        except BackupFalhou as falha:
            self.stdout.write(f"Backup falhou na etapa {falha.etapa}.")
            if falha.etapa == "reserva" and falha.causa in MENSAGENS_DA_RESERVA:
                self.stdout.write(MENSAGENS_DA_RESERVA[falha.causa])
            sys.exit(1)
        self.stdout.write(f"{registro.chave} ({registro.tamanho_bytes} bytes)")
