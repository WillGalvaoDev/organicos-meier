"""`python manage.py conferir_restauracao`: o que o operador confere depois de restaurar (E16-05).

Só leitura. Código de saída 1 com alguma `FALHA`; 0 sem `FALHA`, mesmo com `ATENÇÃO`; 2 para
instante inválido em `--antes-de`.
"""

import sys
from datetime import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.nucleo.tempo import FUSO_DA_OPERACAO, agora
from apps.operacao.conferencia import conferir, formatar

MENSAGEM_DO_INSTANTE = "Instante inválido: use AAAA-MM-DDTHH:MM."


class Command(BaseCommand):
    help = "Confere o estado da aplicação depois de restaurar o banco (só leitura)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--antes-de",
            dest="antes_de",
            help="AAAA-MM-DDTHH:MM (Brasília): limita os movimentos a reconferir ao que veio antes",
        )

    def handle(self, *args: Any, **opcoes: Any) -> None:
        antes_de = None
        if opcoes["antes_de"] is not None:
            try:
                antes_de = datetime.strptime(opcoes["antes_de"], "%Y-%m-%dT%H:%M").replace(
                    tzinfo=FUSO_DA_OPERACAO
                )
            except ValueError:
                self.stderr.write(MENSAGEM_DO_INSTANTE)
                sys.exit(2)
        linhas, falhas, _atencoes = formatar(conferir(agora(), antes_de))
        self.stdout.write("\n".join(linhas))
        if falhas:
            sys.exit(1)
