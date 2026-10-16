"""Recuperação do administrador sem passkey (E02-03): só pela linha de comando do servidor."""

from typing import Any

from allauth.mfa.models import Authenticator
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.contas.models import Conta, Papel
from apps.contas.sessoes import encerrar_sessoes
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria


class Command(BaseCommand):
    help = "Remove todas as passkeys do administrador e encerra as sessões dele."

    def handle(self, *args: Any, **options: Any) -> None:
        with transaction.atomic():
            administrador = Conta.objects.filter(papel=Papel.ADMINISTRADOR).first()
            if administrador is None:
                raise CommandError("não existe administrador")
            removidas, _ = Authenticator.objects.filter(user=administrador).delete()
            encerradas = encerrar_sessoes(administrador)
            registrar_auditoria(
                SISTEMA,
                "conta.redefinir_passkeys",
                administrador,
                {"conta": administrador.pk, "removidas": removidas},
            )
        self.stdout.write(
            f"Passkeys removidas: {removidas}. Sessões encerradas: {encerradas}. "
            "O próximo login por senha exige cadastrar a primeira passkey."
        )
