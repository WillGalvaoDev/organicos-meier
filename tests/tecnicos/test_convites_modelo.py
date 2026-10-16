"""E02-04: restrições do banco para convites (acceptance A-16)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction

from apps.contas.models import Convite
from tests.fabricas import ContaFactory, ConviteFactory, FornecedorFactory

pytestmark = pytest.mark.django_db

T = datetime(2026, 10, 14, 15, 0, 0, tzinfo=UTC)


def _inserir(
    admin_id: int,
    *,
    email: str = "a@x.com",
    papel: str = "comprador",
    fornecedor_id: Any = None,
    token_hash: str = "a" * 64,
    expira_em: datetime = T + timedelta(hours=24),
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO contas_convite (email_normalizado, papel, fornecedor_id, token_hash, "
            "emitido_por_id, emitido_em, expira_em) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [email, papel, fornecedor_id, token_hash, admin_id, T, expira_em],
        )


@pytest.fixture
def admin_id() -> int:
    return ContaFactory.create(administrador=True).pk


def test_banco_recusa_convite_de_administrador(admin_id: int) -> None:  # A-16
    with pytest.raises(IntegrityError, match="convite_papel_valido"), transaction.atomic():
        _inserir(admin_id, papel="administrador")


def test_banco_recusa_convite_de_fornecedor_sem_fornecedor(admin_id: int) -> None:  # A-16
    with pytest.raises(IntegrityError, match="convite_fornecedor_vinculado"), transaction.atomic():
        _inserir(admin_id, papel="fornecedor")


def test_banco_recusa_convite_de_comprador_com_fornecedor(admin_id: int) -> None:
    fornecedor = FornecedorFactory.create()
    with pytest.raises(IntegrityError, match="convite_fornecedor_vinculado"), transaction.atomic():
        _inserir(admin_id, papel="comprador", fornecedor_id=fornecedor.pk)


def test_banco_aceita_convite_valido(admin_id: int) -> None:
    fornecedor = FornecedorFactory.create()
    _inserir(admin_id, papel="fornecedor", fornecedor_id=fornecedor.pk, token_hash="b" * 64)
    _inserir(admin_id, token_hash="c" * 64)
    assert Convite.objects.count() == 2


@pytest.mark.parametrize("email", ["Ana@x.com", " ana@x.com", ""])
def test_banco_recusa_email_nao_normalizado(admin_id: int, email: str) -> None:
    with pytest.raises(IntegrityError, match="convite_email_ja_normalizado"), transaction.atomic():
        _inserir(admin_id, email=email)


def test_banco_recusa_validade_diferente_de_24h(admin_id: int) -> None:
    with pytest.raises(IntegrityError, match="convite_validade_24h"), transaction.atomic():
        _inserir(admin_id, expira_em=T + timedelta(hours=25))


def test_banco_recusa_token_repetido(admin_id: int) -> None:
    _inserir(admin_id, token_hash="d" * 64)
    with pytest.raises(IntegrityError), transaction.atomic():
        _inserir(admin_id, email="b@x.com", token_hash="d" * 64)


def test_fabrica_gera_convites_validos() -> None:
    for convite in (ConviteFactory.create(), ConviteFactory.create(fornecedor=True)):
        convite.full_clean()
