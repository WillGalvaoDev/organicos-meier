"""Cenário 62 (E02-10, A-12 e A-13): a conta de comprador não ganha o perfil de fornecedor."""

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest
from django import forms
from django.db import DatabaseError, connection, transaction
from django.test import Client

import apps
from apps.contas.models import Conta
from tests.fabricas import ContaFactory, FornecedorFactory

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

RAIZ_DE_APPS = Path(apps.__file__).resolve().parent


def test_banco_recusa_trocar_o_papel_mesmo_com_fornecedor_preenchido() -> None:  # A-12
    comprador = ContaFactory.create(email_normalizado="ana@x.com")
    fornecedor = FornecedorFactory.create()
    with (
        pytest.raises(DatabaseError, match="papel"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "UPDATE contas_conta SET papel = 'fornecedor', fornecedor_id = %s WHERE id = %s",
            [fornecedor.pk, comprador.pk],
        )
    comprador.refresh_from_db()
    assert comprador.papel == "comprador"
    assert comprador.fornecedor is None


@pytest.mark.parametrize("novo", ["administrador", "comprador"])
def test_banco_recusa_qualquer_troca_de_papel(novo: str) -> None:
    conta = ContaFactory.create(fornecedor=True)
    with (
        pytest.raises(DatabaseError, match="papel"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute("UPDATE contas_conta SET papel = %s WHERE id = %s", [novo, conta.pk])


def test_atualizacao_sem_mudar_o_papel_continua_permitida() -> None:
    conta = ContaFactory.create(nome="Ana")
    conta.nome = "Ana Souza"
    conta.save()  # o UPDATE do Django inclui a coluna papel, com o mesmo valor
    conta.refresh_from_db()
    assert conta.nome == "Ana Souza"
    assert Conta.objects.filter(pk=conta.pk, papel="comprador").exists()


def test_orm_tambem_nao_troca_o_papel() -> None:
    conta = ContaFactory.create()
    with pytest.raises(DatabaseError), transaction.atomic():
        Conta.objects.filter(pk=conta.pk).update(papel="administrador")


def _formularios_do_projeto() -> list[type[forms.BaseForm]]:
    encontrados: list[type[forms.BaseForm]] = []
    for modulo_info in pkgutil.walk_packages([str(RAIZ_DE_APPS)], prefix="apps."):
        if ".migrations" in modulo_info.name or ".management" in modulo_info.name:
            continue
        modulo = importlib.import_module(modulo_info.name)
        for _, classe in inspect.getmembers(modulo, inspect.isclass):
            if issubclass(classe, forms.BaseForm) and classe.__module__.startswith("apps."):
                if classe not in encontrados:
                    encontrados.append(classe)
    return encontrados


def test_nenhum_formulario_edita_o_papel_da_propria_conta() -> None:  # A-13
    formularios = _formularios_do_projeto()
    assert len(formularios) >= 6  # sanidade: a varredura encontrou os formulários da E02
    com_papel = []
    for classe in formularios:
        campos = (
            classe.base_fields
            if hasattr(classe, "base_fields")
            else getattr(classe, "declared_fields", {})
        )
        if "papel" in campos:
            com_papel.append(classe.__name__)
        meta = getattr(classe, "_meta", None)
        if meta is not None and meta.model is Conta:
            assert "papel" not in (meta.fields or [])
    # o único campo de papel do projeto é o da emissão de convite (E02-04)
    assert com_papel == ["FormularioConvite"]


def test_nenhum_codigo_do_projeto_altera_o_papel_de_uma_conta() -> None:
    suspeitos: list[str] = []
    for arquivo in RAIZ_DE_APPS.rglob("*.py"):
        if "migrations" in arquivo.parts:
            continue
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Assign) and any(
                isinstance(a, ast.Attribute) and a.attr == "papel" for a in no.targets
            ):
                suspeitos.append(f"{arquivo.name}:{no.lineno}: atribui .papel")
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
                if no.func.attr == "update" and any(k.arg == "papel" for k in no.keywords):
                    suspeitos.append(f"{arquivo.name}:{no.lineno}: update(papel=...)")
    assert suspeitos == []


def test_post_no_perfil_com_papel_e_ignorado() -> None:
    conta = ContaFactory.create(email_normalizado="ana@x.com")
    conta.set_password("senha-forte-9271!")
    conta.save()
    cliente = Client()
    cliente.post("/entrar/", {"login": "ana@x.com", "password": "senha-forte-9271!"})
    cliente.post("/perfil/", {"nome": "Ana", "papel": "fornecedor", "fornecedor": "1"})
    conta.refresh_from_db()
    assert conta.papel == "comprador"
    assert conta.fornecedor is None
