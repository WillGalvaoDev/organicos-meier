"""E02-01: modelo de conta e restrições do banco (acceptance A-6 a A-12, A-18, A-19)."""

import threading
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import Client
from django.urls import Resolver404, resolve

from apps.contas.models import Conta, EmailEmUso, Papel, Situacao
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ContaFactory, FornecedorFactory

pytestmark = pytest.mark.django_db


def _inserir(
    email: str, papel: str = "comprador", situacao: str = "ativa", fornecedor: Any = None
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO contas_conta "
            "(email_normalizado, nome, papel, situacao, fornecedor_id, criada_em, password) "
            "VALUES (%s, 'N', %s, %s, %s, now(), '!')",
            [email, papel, situacao, fornecedor],
        )


def test_conta_recusa_email_em_uso_com_variacao_de_caixa_e_espacos() -> None:  # A-6
    ContaFactory.create(email_normalizado="ana@exemplo.com")
    for papel_extra in ({}, {"fornecedor": True}):
        with pytest.raises(EmailEmUso), transaction.atomic():
            ContaFactory.create(email_normalizado="  Ana@Exemplo.com ", **papel_extra)
    assert Conta.objects.count() == 1


def test_conta_grava_email_normalizado() -> None:
    conta = ContaFactory.create(email_normalizado="  Ana@Exemplo.com ")
    conta.refresh_from_db()
    assert conta.email_normalizado == "ana@exemplo.com"


def test_conta_nova_tem_senha_inutilizavel_e_situacao_ativa() -> None:
    conta = ContaFactory.create()
    assert not conta.has_usable_password()
    assert conta.situacao == Situacao.ATIVA


@pytest.mark.parametrize("email", ["Ana@x.com", " ana@x.com"])
def test_banco_recusa_email_nao_normalizado(email: str) -> None:  # A-7
    with pytest.raises(IntegrityError, match="conta_email_ja_normalizado"), transaction.atomic():
        _inserir(email)
    assert Conta.objects.count() == 0


def test_banco_recusa_email_vazio() -> None:
    with pytest.raises(IntegrityError, match="conta_email_ja_normalizado"), transaction.atomic():
        _inserir("")


@pytest.mark.django_db(transaction=True)
@pytest.mark.concorrencia
def test_conta_corrida_mesmo_email_normalizado_com_papeis_diferentes() -> None:  # A-8
    fornecedor = FornecedorFactory.create()
    for _ in range(10):
        Conta.objects.all().delete()

        def criar_comprador(barreira: threading.Barrier) -> None:
            barreira.wait(timeout=5)
            Conta.objects.create(email_normalizado="Ana@x.com", nome="A", papel=Papel.COMPRADOR)

        def criar_fornecedor(barreira: threading.Barrier, fornecedor: Any = fornecedor) -> None:
            barreira.wait(timeout=5)
            Conta.objects.create(
                email_normalizado=" ana@x.com ",
                nome="F",
                papel=Papel.FORNECEDOR,
                fornecedor=fornecedor,
            )

        resultados = executar_em_paralelo(criar_comprador, criar_fornecedor)
        erros = [r.excecao for r in resultados if r.excecao is not None]
        assert len(erros) == 1
        assert isinstance(erros[0], IntegrityError | EmailEmUso)
        assert Conta.objects.count() == 1


def test_banco_recusa_fornecedor_sem_fornecedor_e_comprador_com_fornecedor() -> None:  # A-9
    fornecedor = FornecedorFactory.create()
    with pytest.raises(IntegrityError, match="conta_fornecedor_vinculado"), transaction.atomic():
        _inserir("a@x.com", papel="fornecedor")
    with pytest.raises(IntegrityError, match="conta_fornecedor_vinculado"), transaction.atomic():
        _inserir("b@x.com", papel="comprador", fornecedor=fornecedor.pk)
    with pytest.raises(IntegrityError, match="conta_fornecedor_vinculado"), transaction.atomic():
        _inserir("c@x.com", papel="administrador", fornecedor=fornecedor.pk)


def test_banco_aceita_fornecedor_com_fornecedor() -> None:
    fornecedor = FornecedorFactory.create()
    _inserir("a@x.com", papel="fornecedor", fornecedor=fornecedor.pk)
    assert Conta.objects.filter(papel="fornecedor").count() == 1


def test_banco_recusa_papel_e_situacao_invalidos() -> None:
    with pytest.raises(IntegrityError, match="conta_papel_valido"), transaction.atomic():
        _inserir("a@x.com", papel="gerente")
    with pytest.raises(IntegrityError, match="conta_situacao_valida"), transaction.atomic():
        _inserir("b@x.com", situacao="banida")


def test_banco_recusa_segundo_administrador() -> None:  # A-10
    ContaFactory.create(administrador=True)
    with pytest.raises(IntegrityError, match="conta_administrador_unico"), transaction.atomic():
        _inserir("outro@x.com", papel="administrador")
    assert Conta.objects.filter(papel="administrador").count() == 1


@pytest.mark.parametrize("situacao", ["suspensa", "removida"])
def test_banco_recusa_administrador_inativo(situacao: str) -> None:  # A-11
    admin = ContaFactory.create(administrador=True)
    with pytest.raises(IntegrityError, match="conta_administrador_ativo"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE contas_conta SET situacao = %s WHERE id = %s", [situacao, admin.pk]
            )
    admin.refresh_from_db()
    assert admin.situacao == Situacao.ATIVA
    with pytest.raises(IntegrityError, match="conta_administrador_ativo"), transaction.atomic():
        _inserir("outro@x.com", papel="administrador", situacao=situacao)


def test_is_active_depende_so_de_a_conta_nao_estar_removida() -> None:  # A-12
    ativa = ContaFactory.create()
    suspensa = ContaFactory.create(suspensa=True)
    removida = ContaFactory.create(situacao=Situacao.REMOVIDA)
    assert [ativa.is_active, suspensa.is_active, removida.is_active] == [True, True, False]


def test_admin_do_django_ausente(settings: Any) -> None:  # A-18
    assert "django.contrib.admin" not in settings.INSTALLED_APPS
    with pytest.raises(Resolver404):
        resolve("/admin/")
    assert Client().get("/admin/").status_code == 404


def test_fabricas_geram_contas_validas() -> None:  # A-19
    contas = [
        ContaFactory.create(),
        ContaFactory.create(fornecedor=True),
        ContaFactory.create(administrador=True),
        ContaFactory.create(suspensa=True),
    ]
    for conta in contas:
        conta.full_clean()
    assert [c.papel for c in contas] == ["comprador", "fornecedor", "administrador", "comprador"]
    assert contas[1].fornecedor is not None
    assert contas[0].fornecedor is None
    assert contas[3].situacao == Situacao.SUSPENSA


def test_conta_valida_nome_sem_espacos_nas_pontas_e_nao_vazio() -> None:
    conta = ContaFactory.build(nome="   ")
    with pytest.raises(ValidationError):
        conta.full_clean()
    conta = ContaFactory.build(nome="x" * 151)
    with pytest.raises(ValidationError):
        conta.full_clean()
    conta = ContaFactory.build(nome="  Ana  ")
    conta.full_clean()
    assert conta.nome == "Ana"


def test_conta_papel_fornecedor_exige_fornecedor_na_validacao() -> None:
    conta = ContaFactory.build(papel=Papel.FORNECEDOR)
    with pytest.raises(ValidationError):
        conta.full_clean()


def test_conta_aplicacao_nao_registra_erro_de_banco_silenciado() -> None:
    ContaFactory.create(email_normalizado="ana@x.com")
    with pytest.raises(DatabaseError), transaction.atomic():
        _inserir("ana@x.com")
