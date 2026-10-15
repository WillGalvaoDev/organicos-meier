"""E01-04: registros só de inserção, na aplicação e no banco (acceptance A-1 a A-5, A-12)."""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.nucleo.so_insercao import RegistroImutavel
from tests.apoio.models import ModeloSoInsercao

pytestmark = pytest.mark.django_db


def _valor_no_banco(pk: int) -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT nome FROM apoio_testes_modelosoinsercao WHERE id = %s", [pk])
        linha = cursor.fetchone()
    assert linha is not None
    return str(linha[0])


def test_aplicacao_salva_objeto_novo() -> None:  # A-1
    objeto = ModeloSoInsercao(nome="original")
    objeto.save()
    assert _valor_no_banco(objeto.pk) == "original"


def test_aplicacao_recusa_alterar_objeto_gravado() -> None:  # A-2
    objeto = ModeloSoInsercao.objects.create(nome="original")
    objeto.nome = "alterado"
    with pytest.raises(RegistroImutavel):
        objeto.save()
    assert _valor_no_banco(objeto.pk) == "original"


def test_aplicacao_recusa_alterar_objeto_relido() -> None:
    criado = ModeloSoInsercao.objects.create(nome="original")
    relido = ModeloSoInsercao.objects.get(pk=criado.pk)
    relido.nome = "alterado"
    with pytest.raises(RegistroImutavel):
        relido.save()
    assert _valor_no_banco(criado.pk) == "original"


def test_aplicacao_recusa_delete_de_instancia() -> None:  # A-3
    objeto = ModeloSoInsercao.objects.create(nome="original")
    with pytest.raises(RegistroImutavel):
        objeto.delete()
    assert ModeloSoInsercao.objects.filter(pk=objeto.pk).exists()


def test_aplicacao_recusa_operacoes_em_lote() -> None:  # A-4
    objetos = [ModeloSoInsercao.objects.create(nome=f"n{i}") for i in range(2)]
    with pytest.raises(RegistroImutavel):
        ModeloSoInsercao.objects.all().update(nome="x")
    with pytest.raises(RegistroImutavel):
        ModeloSoInsercao.objects.all().delete()
    with pytest.raises(RegistroImutavel):
        ModeloSoInsercao.objects.bulk_update(objetos, ["nome"])
    assert sorted(ModeloSoInsercao.objects.values_list("nome", flat=True)) == ["n0", "n1"]


def test_aplicacao_bulk_create_funciona() -> None:  # A-12 (modelo de apoio)
    ModeloSoInsercao.objects.bulk_create([ModeloSoInsercao(nome=f"b{i}") for i in range(3)])
    assert ModeloSoInsercao.objects.count() == 3


def test_trigger_recusa_update_e_delete_por_sql_direto() -> None:  # A-5
    objeto = ModeloSoInsercao.objects.create(nome="original")
    with (
        pytest.raises(DatabaseError, match="só aceita inserção"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "UPDATE apoio_testes_modelosoinsercao SET nome = 'x' WHERE id = %s", [objeto.pk]
        )
    with (
        pytest.raises(DatabaseError, match="só aceita inserção"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute("DELETE FROM apoio_testes_modelosoinsercao WHERE id = %s", [objeto.pk])
    assert _valor_no_banco(objeto.pk) == "original"


def test_trigger_permite_insercao_por_sql_direto() -> None:
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO apoio_testes_modelosoinsercao (nome) VALUES ('sql')")
    assert ModeloSoInsercao.objects.filter(nome="sql").exists()
