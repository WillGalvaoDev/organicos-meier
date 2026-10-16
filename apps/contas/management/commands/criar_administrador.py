"""Cria o único administrador (E02-01). Não recebe senha: ela nasce inutilizável."""

from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import IntegrityError, transaction

from apps.contas.emails import EmailInvalido, email_banido, normalizar_email
from apps.contas.models import Conta, EmailEmUso, Papel, Situacao
from apps.nucleo.auditoria import SISTEMA, registrar_auditoria


class Command(BaseCommand):
    help = "Cria o único administrador da plataforma."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--nome", required=True)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            email = normalizar_email(options["email"])
        except EmailInvalido as erro:
            raise CommandError(str(erro)) from None
        try:
            with transaction.atomic():
                if Conta.objects.filter(papel=Papel.ADMINISTRADOR).exists():
                    raise CommandError("já existe um administrador")
                if Conta.objects.filter(email_normalizado=email).exists():
                    raise CommandError("este e-mail já está em uso")
                if email_banido(email):
                    raise CommandError("este e-mail está banido")
                conta = Conta(
                    email_normalizado=email,
                    nome=options["nome"],
                    papel=Papel.ADMINISTRADOR,
                    situacao=Situacao.ATIVA,
                )
                conta.full_clean()
                conta.save()
                registrar_auditoria(
                    SISTEMA, "conta.criar_administrador", conta, {"conta": conta.pk}
                )
        except ValidationError as erro:
            raise CommandError("; ".join(erro.messages)) from None
        except (EmailEmUso, IntegrityError):
            raise CommandError("não foi possível criar o administrador") from None
        self.stdout.write(f"Administrador criado (conta {conta.pk}).")
