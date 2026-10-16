"""E02-01: comando criar_administrador (acceptance A-16 e A-17)."""

import io
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.contas.models import Conta, EmailBanido, Papel, Situacao
from apps.nucleo.auditoria import EntradaAuditoria
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db


def _rodar(*argumentos: str) -> str:
    saida = io.StringIO()
    call_command("criar_administrador", *argumentos, stdout=saida)
    return saida.getvalue()


def test_comando_cria_administrador_com_email_normalizado_e_audita() -> None:  # A-16
    _rodar("--email", " Admin@x.com ", "--nome", "Adm")
    conta = Conta.objects.get()
    assert conta.email_normalizado == "admin@x.com"
    assert conta.papel == Papel.ADMINISTRADOR
    assert conta.situacao == Situacao.ATIVA
    assert not conta.has_usable_password()
    entrada = EntradaAuditoria.objects.get()
    assert entrada.acao == "conta.criar_administrador"
    assert entrada.autor_tipo == "sistema"
    assert entrada.alteracoes == {"conta": conta.pk}
    assert entrada.objeto_id == str(conta.pk)


def _administrador_existente() -> None:
    ContaFactory.create(administrador=True, email_normalizado="existente@x.com")


def _email_em_uso() -> None:
    ContaFactory.create(email_normalizado="novo@x.com")


def _email_banido() -> None:
    EmailBanido.objects.create(
        email_normalizado="novo@x.com",
        banido_por=ContaFactory.create(email_normalizado="quem.baniu@x.com"),
    )


@pytest.mark.parametrize(
    ("preparar", "email"),
    [
        (_administrador_existente, "novo@x.com"),
        (_email_em_uso, "novo@x.com"),
        (_email_banido, "novo@x.com"),
        (lambda: None, "lixo"),
    ],
    ids=["ja_existe_administrador", "email_em_uso", "email_banido", "email_invalido"],
)
def test_comando_recusa_sem_criar_nem_auditar(preparar: Any, email: str) -> None:  # A-17
    preparar()
    contas_antes = Conta.objects.count()
    with pytest.raises(CommandError):
        _rodar("--email", email, "--nome", "Adm")
    assert Conta.objects.count() == contas_antes
    assert EntradaAuditoria.objects.count() == 0


def test_comando_termina_com_codigo_de_saida_diferente_de_zero_na_recusa() -> None:  # A-17
    from apps.contas.management.commands.criar_administrador import Command

    _administrador_existente()
    with pytest.raises(SystemExit) as saida:
        Command().run_from_argv(
            ["manage.py", "criar_administrador", "--email", "n@x.com", "--nome", "A"]
        )
    assert saida.value.code != 0


def test_comando_nao_aceita_senha_por_argumento() -> None:
    with pytest.raises(CommandError):
        _rodar("--email", "n@x.com", "--nome", "A", "--senha", "x")
