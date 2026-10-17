"""E04-06: publicação de comunicados (acceptance A-1, A-2, A-4, A-5, A-13 e A-14)."""

import uuid
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction

from apps.contas.models import Conta
from apps.notificacoes.comunicados import publicar_comunicado
from apps.notificacoes.models import Comunicado, Envio, Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from apps.nucleo.tempo import agora
from tests.fabricas import ComunicadoFactory, ContaFactory

pytestmark = pytest.mark.django_db


class Cenario:
    def __init__(self) -> None:
        self.admin = ContaFactory.create(administrador=True)
        self.a = ContaFactory.create(telefone="+5521999990000", whatsapp_consentido_em=agora())
        self.b = ContaFactory.create()
        self.s = ContaFactory.create(suspensa=True)
        self.r = ContaFactory.create(situacao="removida")
        self.f = ContaFactory.create(fornecedor=True)


@pytest.fixture
def cenario() -> Cenario:
    return Cenario()


def test_publicacao_distribui_para_compradores_ativos_e_suspensos(cenario: Cenario) -> None:  # A-1
    token = uuid.uuid4()
    comunicado, novo = publicar_comunicado(
        cenario.admin, titulo=" Feira ", mensagem="Sábado\nàs 9h", token=token
    )
    assert novo is True
    assert (comunicado.titulo, comunicado.mensagem) == ("Feira", "Sábado\nàs 9h")
    assert (comunicado.destinatarios, comunicado.autor_id, comunicado.token) == (
        3,
        cenario.admin.pk,
        token,
    )
    notificacoes = Notificacao.objects.filter(evento="comunicado")
    assert set(notificacoes.values_list("conta_id", flat=True)) == {
        cenario.a.pk,
        cenario.b.pk,
        cenario.s.pk,
    }
    assert set(notificacoes.values_list("link", flat=True)) == {"/comunicados/"}
    assert set(notificacoes.values_list("chave", flat=True)) == {
        f"comunicado:{comunicado.pk}:{c.pk}" for c in (cenario.a, cenario.b, cenario.s)
    }
    assert Envio.objects.filter(canal="email").count() == 3
    whatsapp = Envio.objects.filter(canal="whatsapp")
    assert [e.conta_id for e in whatsapp] == [cenario.a.pk]
    auditoria = EntradaAuditoria.objects.get(acao="comunicado.publicar")
    assert auditoria.alteracoes == {"comunicado": comunicado.pk, "destinatarios": 3}


def test_token_repetido_nao_publica_de_novo(cenario: Cenario) -> None:  # A-2
    token = uuid.uuid4()
    primeiro, _ = publicar_comunicado(cenario.admin, titulo="Feira", mensagem="m", token=token)
    notificacoes = Notificacao.objects.count()
    envios = Envio.objects.count()
    auditorias = EntradaAuditoria.objects.count()
    for titulo, mensagem in (("Feira", "m"), ("Outro", "outro texto")):
        repetido, novo = publicar_comunicado(
            cenario.admin, titulo=titulo, mensagem=mensagem, token=token
        )
        assert novo is False
        assert repetido.pk == primeiro.pk
    assert Comunicado.objects.count() == 1
    assert Notificacao.objects.count() == notificacoes
    assert Envio.objects.count() == envios
    assert EntradaAuditoria.objects.count() == auditorias


@pytest.mark.parametrize(
    ("campo", "titulo", "mensagem"),
    [
        ("titulo", "", "texto"),
        ("titulo", "   ", "texto"),
        ("titulo", "t" * 151, "texto"),
        ("mensagem", "titulo", "   "),
        ("mensagem", "titulo", "m" * 2001),
    ],
)
def test_validacao_por_campo(
    cenario: Cenario, campo: str, titulo: str, mensagem: str
) -> None:  # A-4
    with pytest.raises(ValidationError) as erro:
        publicar_comunicado(cenario.admin, titulo=titulo, mensagem=mensagem, token=uuid.uuid4())
    assert campo in erro.value.message_dict
    assert Comunicado.objects.count() == 0
    assert Notificacao.objects.count() == 0
    assert Envio.objects.count() == 0


def test_limites_validos(cenario: Cenario) -> None:  # A-4 (limite)
    publicar_comunicado(cenario.admin, titulo="t" * 150, mensagem="m" * 2000, token=uuid.uuid4())
    assert Comunicado.objects.count() == 1


def test_so_o_administrador_publica(cenario: Cenario) -> None:  # A-5
    for conta in (cenario.b, cenario.f):
        with pytest.raises(PermissionDenied):
            publicar_comunicado(conta, titulo="t", mensagem="m", token=uuid.uuid4())
    assert Comunicado.objects.count() == 0
    assert Notificacao.objects.count() == 0


def test_comunicado_so_aceita_insercao(cenario: Cenario) -> None:  # A-13
    comunicado = ComunicadoFactory.create()
    comunicado.titulo = "outro"
    with pytest.raises(RegistroImutavel):
        comunicado.save()
    with pytest.raises(RegistroImutavel):
        comunicado.delete()
    with pytest.raises(RegistroImutavel):
        Comunicado.objects.all().update(titulo="x")
    for comando in (
        "UPDATE notificacoes_comunicado SET titulo = 'x' WHERE id = %s",
        "DELETE FROM notificacoes_comunicado WHERE id = %s",
    ):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(comando, [comunicado.pk])
    assert Comunicado.objects.get().titulo != "x"


def test_sem_compradores_publica_com_zero_destinatarios() -> None:  # A-14
    admin: Conta = ContaFactory.create(administrador=True)
    comunicado, novo = publicar_comunicado(admin, titulo="t", mensagem="m", token=uuid.uuid4())
    assert novo is True
    assert comunicado.destinatarios == 0
    assert Notificacao.objects.count() == 0


def test_o_numero_de_destinatarios_e_o_de_notificacoes(cenario: Cenario) -> None:
    extras: list[Any] = [ContaFactory.create() for _ in range(5)]
    comunicado, _ = publicar_comunicado(cenario.admin, titulo="t", mensagem="m", token=uuid.uuid4())
    assert comunicado.destinatarios == 3 + len(extras)
    assert Notificacao.objects.filter(evento="comunicado").count() == comunicado.destinatarios
