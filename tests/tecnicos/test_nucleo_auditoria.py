"""E01-04: trilha de auditoria (acceptance A-6 a A-11, A-13, A-14)."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.db import DatabaseError, connection, transaction

from apps.nucleo.auditoria import SISTEMA, EntradaAuditoria, registrar_auditoria
from apps.nucleo.so_insercao import RegistroImutavel
from tests.apoio.models import ModeloValores
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

T = datetime(2026, 10, 14, 15, 0, 0, tzinfo=UTC)


@pytest.fixture
def usuario() -> Any:
    return ContaFactory()


@pytest.fixture
def objeto() -> ModeloValores:
    return ModeloValores.objects.create(preco=Decimal("7.99"), peso=Decimal("1"))


def test_auditoria_registra_autor_acao_momento_motivo_alteracoes_objeto(
    usuario: Any, objeto: ModeloValores, relogio: Any
) -> None:  # A-6
    relogio.congelar(T)
    entrada = registrar_auditoria(
        usuario,
        "rodada.cancelar",
        objeto,
        {"status": {"de": "aberta", "para": "cancelada"}, "preco": Decimal("7.99")},
        motivo="pedido do fornecedor",
    )
    relida = EntradaAuditoria.objects.get(pk=entrada.pk)
    assert relida.autor_tipo == "usuario"
    assert relida.autor_id == str(usuario.pk)
    assert relida.acao == "rodada.cancelar"
    assert relida.momento == T
    assert relida.motivo == "pedido do fornecedor"
    assert relida.alteracoes["status"] == {"de": "aberta", "para": "cancelada"}
    assert relida.alteracoes["preco"] == "7.99"
    assert relida.objeto_tipo == "apoio_testes.modelovalores"
    assert relida.objeto_id == str(objeto.pk)


def test_auditoria_sem_motivo_e_autor_sistema(objeto: ModeloValores) -> None:  # A-7
    entrada = registrar_auditoria(SISTEMA, "pedido.expirar", objeto, {"status": "expirado"})
    relida = EntradaAuditoria.objects.get(pk=entrada.pk)
    assert relida.motivo == ""
    assert relida.autor_tipo == "sistema"
    assert relida.autor_id is None


def test_auditoria_recusa_alterar_ou_apagar(objeto: ModeloValores) -> None:  # A-8
    entrada = registrar_auditoria(SISTEMA, "x.y", objeto, {})
    entrada.motivo = "reescrito"
    with pytest.raises(RegistroImutavel):
        entrada.save()
    with pytest.raises(RegistroImutavel):
        entrada.delete()
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE nucleo_entradaauditoria SET acao = 'z' WHERE id = %s", [entrada.pk])
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM nucleo_entradaauditoria WHERE id = %s", [entrada.pk])
    assert EntradaAuditoria.objects.get(pk=entrada.pk).acao == "x.y"


@pytest.mark.parametrize(
    "alteracoes",
    [
        {"senha": "x"},
        {"password": "x"},
        {"token": "x"},
        {"secret": "x"},
        {"chave_api": "x"},
        {"Token_Pagamento": "x"},
        {"senha_hash": "x"},
        {"externo": {"interno": {"API_SECRET_KEY": "x"}}},
        {"itens": [{"ok": 1}, {"aninhado": [{"Senha": "x"}]}]},
    ],
)
def test_auditoria_recusa_chaves_com_segredo(
    alteracoes: dict[str, Any], objeto: ModeloValores
) -> None:  # A-9
    with pytest.raises(ValueError, match="segredo"):
        registrar_auditoria(SISTEMA, "x.y", objeto, alteracoes)
    assert EntradaAuditoria.objects.count() == 0


def test_auditoria_aceita_chaves_comuns(objeto: ModeloValores) -> None:
    registrar_auditoria(SISTEMA, "x.y", objeto, {"status": "ok", "itens": [{"preco": "1.00"}]})
    assert EntradaAuditoria.objects.count() == 1


def test_auditoria_sobrevive_a_remocao_do_usuario(usuario: Any, objeto: ModeloValores) -> None:
    # A-10
    entrada = registrar_auditoria(usuario, "x.y", objeto, {})
    identificador = str(usuario.pk)
    usuario.delete()
    relida = EntradaAuditoria.objects.get(pk=entrada.pk)
    assert relida.autor_tipo == "usuario"
    assert relida.autor_id == identificador


def test_auditoria_desfeita_junto_com_a_transacao(objeto: ModeloValores) -> None:  # A-11
    def auditar_e_falhar() -> None:
        with transaction.atomic():
            registrar_auditoria(SISTEMA, "x.y", objeto, {})
            raise RuntimeError("falha depois de auditar")

    with pytest.raises(RuntimeError):
        auditar_e_falhar()
    assert EntradaAuditoria.objects.count() == 0


def test_auditoria_bulk_create_funciona() -> None:  # A-12
    EntradaAuditoria.objects.bulk_create(
        [
            EntradaAuditoria(
                autor_tipo="sistema", acao=f"a.{i}", momento=T, objeto_tipo="x.y", objeto_id="1"
            )
            for i in range(3)
        ]
    )
    assert EntradaAuditoria.objects.count() == 3


@pytest.mark.parametrize(
    ("tipo", "autor_id"),
    [("usuario", None), ("sistema", "7"), ("outro", None)],
)
def test_auditoria_banco_recusa_combinacoes_invalidas_de_autor(
    tipo: str, autor_id: str | None
) -> None:  # A-13
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO nucleo_entradaauditoria "
            "(autor_tipo, autor_id, acao, momento, motivo, alteracoes, objeto_tipo, objeto_id) "
            "VALUES (%s, %s, 'a.b', now(), '', '{}', 'x.y', '1')",
            [tipo, autor_id],
        )
    assert EntradaAuditoria.objects.count() == 0


def test_auditoria_recusa_autor_ausente(objeto: ModeloValores) -> None:  # A-14
    with pytest.raises(ValueError, match="autor"):
        registrar_auditoria(None, "x.y", objeto, {})
    assert EntradaAuditoria.objects.count() == 0


@pytest.mark.parametrize("acao", ["", "   "])
def test_auditoria_recusa_acao_vazia(acao: str, objeto: ModeloValores) -> None:  # A-14
    with pytest.raises(ValueError, match="ação"):
        registrar_auditoria(SISTEMA, acao, objeto, {})
    assert EntradaAuditoria.objects.count() == 0


def test_auditoria_recusa_usuario_nao_salvo(objeto: ModeloValores) -> None:
    with pytest.raises(ValueError, match="autor"):
        registrar_auditoria(ContaFactory.build(), "x.y", objeto, {})


@pytest.mark.parametrize("autor_id", ["", "   ", "\t"])
def test_auditoria_banco_recusa_usuario_com_identificador_vazio_por_sql(
    autor_id: str,
) -> None:  # R04
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO nucleo_entradaauditoria "
            "(autor_tipo, autor_id, acao, momento, motivo, alteracoes, objeto_tipo, objeto_id) "
            "VALUES ('usuario', %s, 'a.b', now(), '', '{}', 'x.y', '1')",
            [autor_id],
        )
    assert EntradaAuditoria.objects.count() == 0


@pytest.mark.parametrize("autor_id", ["", "  "])
def test_auditoria_banco_recusa_usuario_com_identificador_vazio_pelo_modelo(
    autor_id: str,
) -> None:  # R04
    entrada = EntradaAuditoria(
        autor_tipo="usuario",
        autor_id=autor_id,
        acao="a.b",
        momento=T,
        objeto_tipo="x.y",
        objeto_id="1",
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        entrada.save()
    with pytest.raises(DatabaseError), transaction.atomic():
        EntradaAuditoria.objects.bulk_create([entrada])
    assert EntradaAuditoria.objects.count() == 0
