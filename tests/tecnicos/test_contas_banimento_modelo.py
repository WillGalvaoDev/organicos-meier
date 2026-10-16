"""E02-01: e-mails banidos (acceptance A-13 a A-15)."""

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from apps.contas.emails import email_banido
from apps.contas.models import EmailBanido
from apps.nucleo.so_insercao import RegistroImutavel
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def banido() -> EmailBanido:
    return EmailBanido.objects.create(
        email_normalizado="ana@x.com", banido_por=ContaFactory.create(administrador=True)
    )


def test_email_banido_normaliza_a_consulta(banido: EmailBanido) -> None:  # A-13
    assert email_banido("  ANA@x.com ") is True
    assert email_banido("ana+1@x.com") is False
    assert email_banido("lixo") is False


def test_email_banido_sem_registro_devolve_falso() -> None:
    assert email_banido("ninguem@x.com") is False


def test_banimento_registra_momento_e_autor(banido: EmailBanido) -> None:
    assert banido.banido_em is not None
    assert banido.banido_por.papel == "administrador"


def test_banimento_normaliza_na_aplicacao_e_recusa_duplicata(banido: EmailBanido) -> None:  # A-14
    with pytest.raises(IntegrityError), transaction.atomic():
        EmailBanido.objects.create(email_normalizado="ANA@x.com", banido_por=banido.banido_por)


def test_banimento_grava_normalizado() -> None:
    novo = EmailBanido.objects.create(
        email_normalizado="  NOVO@x.com ", banido_por=ContaFactory.create(administrador=True)
    )
    novo.refresh_from_db()
    assert novo.email_normalizado == "novo@x.com"


def test_banco_recusa_email_banido_nao_normalizado(banido: EmailBanido) -> None:  # A-14
    with (
        pytest.raises(IntegrityError, match="emailbanido_ja_normalizado"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "INSERT INTO contas_emailbanido (email_normalizado, banido_em, banido_por_id) "
            "VALUES ('Ana@x.com', now(), %s)",
            [banido.banido_por_id],
        )


def test_banimento_e_so_insercao_na_aplicacao_e_no_banco(banido: EmailBanido) -> None:  # A-15
    banido.email_normalizado = "outro@x.com"
    with pytest.raises(RegistroImutavel):
        banido.save()
    with pytest.raises(RegistroImutavel):
        banido.delete()
    with pytest.raises(RegistroImutavel):
        EmailBanido.objects.all().update(email_normalizado="x@x.com")
    for sql in (
        "UPDATE contas_emailbanido SET email_normalizado = 'z@x.com'",
        "DELETE FROM contas_emailbanido",
    ):
        with (
            pytest.raises(DatabaseError, match="só aceita inserção"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(sql)
    assert EmailBanido.objects.get().email_normalizado == "ana@x.com"
