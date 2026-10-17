"""E04-01: modelo, criação interna e proteção no banco (acceptance A-2 a A-5)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from apps.contas.models import Conta
from apps.notificacoes.eventos import Evento
from apps.notificacoes.models import Envio, Notificacao, TentativaDeEnvio
from apps.notificacoes.servicos import NotificacaoInvalida, criar_notificacao
from apps.nucleo.so_insercao import RegistroImutavel
from apps.nucleo.tempo import agora
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, EnvioFactory, NotificacaoFactory

pytestmark = pytest.mark.django_db

INSTANTE = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def test_criar_notificacao_grava_os_valores(relogio: RelogioControlado) -> None:  # A-2
    relogio.congelar(INSTANTE)
    conta = ContaFactory.create()
    criada = criar_notificacao(
        conta, Evento.ESTORNO, titulo="Estorno", corpo="R$ 10,00", link="/historico/", chave="t:1"
    )
    gravada = Notificacao.objects.get()
    assert gravada.pk == criada.pk
    assert gravada.conta_id == conta.pk
    assert gravada.evento == "estorno"
    assert (gravada.titulo, gravada.corpo, gravada.link, gravada.chave) == (
        "Estorno",
        "R$ 10,00",
        "/historico/",
        "t:1",
    )
    assert gravada.criada_em == INSTANTE
    assert gravada.lida_em is None


@pytest.mark.parametrize(
    ("campo", "ajuste"),
    [
        ("titulo", {"titulo": ""}),
        ("titulo", {"titulo": "x" * 151}),
        ("corpo", {"corpo": "x" * 2001}),
        ("corpo", {"corpo": ""}),
        ("link", {"link": "https://x.com"}),
        ("link", {"link": "//x.com"}),
        ("link", {"link": "x/"}),
        ("link", {"link": "/" + "a" * 500}),
        ("chave", {"chave": ""}),
        ("chave", {"chave": "k" * 201}),
        ("evento", {"evento": "inexistente"}),
        ("conta", {"evento": Evento.FALHA_NO_PEDIDO_FORMAL}),
        ("conta", {"para_administrador": True}),
    ],
)
def test_criar_notificacao_recusa_violacoes(campo: str, ajuste: dict[str, Any]) -> None:  # A-3
    conta = ContaFactory.create()
    administrador = ContaFactory.create(administrador=True)
    dados: dict[str, Any] = {
        "evento": Evento.ESTORNO,
        "titulo": "Estorno",
        "corpo": "Corpo",
        "link": "/historico/",
        "chave": "t:1",
    }
    destinatario: Conta = conta
    for nome, valor in ajuste.items():
        if nome == "para_administrador":
            destinatario = administrador
        else:
            dados[nome] = valor
    evento = dados.pop("evento")
    with pytest.raises(NotificacaoInvalida) as erro:
        criar_notificacao(destinatario, evento, **dados)
    assert erro.value.campo == campo
    assert Notificacao.objects.count() == 0


def test_link_no_limite_de_500_e_aceito() -> None:  # A-3 (limite)
    conta = ContaFactory.create()
    criar_notificacao(conta, Evento.ESTORNO, titulo="t", corpo="c", link="/" + "a" * 499, chave="k")
    assert Notificacao.objects.count() == 1


def _sql(comando: str, parametros: list[Any]) -> int:
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(comando, parametros)
        return int(cursor.rowcount)


@pytest.mark.parametrize(
    ("comando", "da_lida"),
    [
        ("DELETE FROM notificacoes_notificacao WHERE id = %s", False),
        ("DELETE FROM notificacoes_notificacao WHERE id = %s", True),
        ("UPDATE notificacoes_notificacao SET titulo = 'x' WHERE id = %s", False),
        ("UPDATE notificacoes_notificacao SET titulo = 'x' WHERE id = %s", True),
        ("UPDATE notificacoes_notificacao SET lida_em = NULL WHERE id = %s", True),
        ("UPDATE notificacoes_notificacao SET lida_em = now() WHERE id = %s", True),
        (
            "UPDATE notificacoes_notificacao SET lida_em = now(), corpo = 'x' WHERE id = %s",
            False,
        ),
        ("UPDATE notificacoes_notificacao SET criada_em = now() WHERE id = %s", False),
        ("UPDATE notificacoes_notificacao SET conta_id = conta_id WHERE id = %s", True),
    ],
)
def test_banco_recusa_apagar_e_alterar(comando: str, da_lida: bool) -> None:  # A-4
    NotificacaoFactory.create()
    lida = NotificacaoFactory.create(lida_em=INSTANTE)
    alvo = lida if da_lida else Notificacao.objects.exclude(pk=lida.pk).get()
    antes = Notificacao.objects.filter(pk=alvo.pk).values().get()
    with pytest.raises(DatabaseError):
        _sql(comando, [alvo.pk])
    assert Notificacao.objects.filter(pk=alvo.pk).values().get() == antes


def test_aplicacao_recusa_salvar_outros_campos_e_apagar() -> None:  # A-4
    notificacao = NotificacaoFactory.create()
    notificacao.titulo = "outro"
    with pytest.raises(RegistroImutavel):
        notificacao.save()
    with pytest.raises(RegistroImutavel):
        notificacao.save(update_fields=["titulo"])
    with pytest.raises(RegistroImutavel):
        notificacao.delete()
    with pytest.raises(RegistroImutavel):
        Notificacao.objects.all().delete()
    with pytest.raises(RegistroImutavel):
        Notificacao.objects.all().update(titulo="x")
    assert Notificacao.objects.get().titulo != "outro"


def test_banco_aceita_marcar_como_lida() -> None:  # A-5
    notificacao = NotificacaoFactory.create()
    assert (
        _sql(
            "UPDATE notificacoes_notificacao SET lida_em = %s WHERE id = %s",
            [agora(), notificacao.pk],
        )
        == 1
    )
    notificacao.refresh_from_db()
    assert notificacao.lida_em is not None


def test_aplicacao_aceita_marcar_so_lida_em() -> None:  # A-5
    notificacao = NotificacaoFactory.create()
    notificacao.lida_em = INSTANTE
    notificacao.save(update_fields=["lida_em"])
    notificacao.refresh_from_db()
    assert notificacao.lida_em == INSTANTE
    outra = NotificacaoFactory.create()
    assert Notificacao.objects.filter(pk=outra.pk).update(lida_em=agora()) == 1


@pytest.mark.parametrize(
    "campos",
    [
        {"link": "https://x.com"},
        {"link": "//x.com"},
        {"titulo": ""},
        {"corpo": ""},
        {"evento": "inexistente"},
    ],
)
def test_banco_recusa_linhas_invalidas(campos: dict[str, Any]) -> None:  # restrições da spec
    with pytest.raises(IntegrityError), transaction.atomic():
        NotificacaoFactory.create(**campos)
    assert Notificacao.objects.count() == 0


def test_banco_aceita_link_relativo_e_nulo() -> None:
    NotificacaoFactory.create(link="/catalogo/3/")
    NotificacaoFactory.create(link=None)
    assert Notificacao.objects.count() == 2


# --- E04-02: Envio (acceptance A-12 e A-13) ----------------------------------------------------


def _envios() -> tuple[Envio, Envio]:
    pendente = EnvioFactory.create()
    enviado = EnvioFactory.create(situacao="enviado", tentativas=1, concluido_em=INSTANTE)
    return pendente, enviado


@pytest.mark.parametrize(
    ("comando", "do_enviado"),
    [
        ("DELETE FROM notificacoes_envio WHERE id = %s", False),
        ("DELETE FROM notificacoes_envio WHERE id = %s", True),
        ("UPDATE notificacoes_envio SET corpo = 'x' WHERE id = %s", False),
        ("UPDATE notificacoes_envio SET destino = 'x@y.com' WHERE id = %s", False),
        ("UPDATE notificacoes_envio SET chave = 'nova' WHERE id = %s", False),
        ("UPDATE notificacoes_envio SET assunto = 'x' WHERE id = %s", False),
        ("UPDATE notificacoes_envio SET canal = 'whatsapp' WHERE id = %s", False),
        ("UPDATE notificacoes_envio SET tipo = 'x' WHERE id = %s", False),
        ("UPDATE notificacoes_envio SET criado_em = now() WHERE id = %s", False),
        ("UPDATE notificacoes_envio SET situacao = 'pendente' WHERE id = %s", True),
        ("UPDATE notificacoes_envio SET tentativas = 2 WHERE id = %s", True),
        ("UPDATE notificacoes_envio SET tentativas = 4 WHERE id = %s", False),
        ("UPDATE notificacoes_envio SET situacao = 'enviado' WHERE id = %s", False),
    ],
)
def test_banco_recusa_apagar_e_alterar_envios(comando: str, do_enviado: bool) -> None:  # A-12
    pendente, enviado = _envios()
    alvo = enviado if do_enviado else pendente
    antes = Envio.objects.filter(pk=alvo.pk).values().get()
    with pytest.raises(DatabaseError):
        _sql(comando, [alvo.pk])
    assert Envio.objects.filter(pk=alvo.pk).values().get() == antes


def test_banco_aceita_atualizar_o_estado_de_um_envio_pendente() -> None:  # A-13
    pendente, _ = _envios()
    _sql(
        "UPDATE notificacoes_envio SET tentativas = 1, proxima_tentativa_em = %s, "
        "situacao = 'falhou', concluido_em = %s WHERE id = %s",
        [INSTANTE, INSTANTE, pendente.pk],
    )
    pendente.refresh_from_db()
    assert pendente.situacao == "falhou"
    assert pendente.tentativas == 1


def test_banco_aceita_reagendar_um_envio_pendente() -> None:  # A-13
    pendente, _ = _envios()
    _sql(
        "UPDATE notificacoes_envio SET tentativas = 1, proxima_tentativa_em = %s WHERE id = %s",
        [INSTANTE, pendente.pk],
    )
    pendente.refresh_from_db()
    assert (pendente.tentativas, pendente.situacao) == (1, "pendente")


@pytest.mark.parametrize(
    "campos",
    [
        {"tentativas": 4},
        {"tentativas": -1},
        {"situacao": "enviado"},  # concluído sem concluido_em
        {"concluido_em": INSTANTE},  # pendente com concluido_em
        {"situacao": "outra", "concluido_em": INSTANTE},
        {
            "notificacao": None,
            "tipo": "estorno",
            "assunto": "a",
            "corpo": "c",
            "chave": "k",
            "conta": ContaFactory.create,
        },
        {"conta": None, "destino": "x@y.com"},
    ],
)
def test_banco_recusa_envios_invalidos(campos: dict[str, Any]) -> None:  # restrições da spec
    dados = {k: (v() if callable(v) else v) for k, v in campos.items()}
    with pytest.raises(IntegrityError), transaction.atomic():
        EnvioFactory.create(**dados)
    assert Envio.objects.count() == 0


def test_banco_recusa_chave_repetida_de_envio() -> None:
    primeiro = EnvioFactory.create()
    with pytest.raises(IntegrityError), transaction.atomic():
        EnvioFactory.create(chave=primeiro.chave)


# --- E04-03: TentativaDeEnvio (acceptance A-9) -------------------------------------------------


def _tentativa() -> TentativaDeEnvio:
    return TentativaDeEnvio.objects.create(
        envio=EnvioFactory.create(),
        numero=1,
        iniciada_em=INSTANTE,
        concluida_em=INSTANTE,
        resultado="falha",
        erro="ConnectionError",
    )


def test_tentativa_so_aceita_insercao_na_aplicacao() -> None:  # A-9
    tentativa = _tentativa()
    tentativa.erro = "outro"
    with pytest.raises(RegistroImutavel):
        tentativa.save()
    with pytest.raises(RegistroImutavel):
        tentativa.delete()
    with pytest.raises(RegistroImutavel):
        TentativaDeEnvio.objects.all().update(erro="x")


@pytest.mark.parametrize(
    "comando",
    [
        "UPDATE notificacoes_tentativadeenvio SET erro = 'x' WHERE id = %s",
        "DELETE FROM notificacoes_tentativadeenvio WHERE id = %s",
    ],
)
def test_banco_recusa_alterar_e_apagar_tentativa(comando: str) -> None:  # A-9
    tentativa = _tentativa()
    with pytest.raises(DatabaseError):
        _sql(comando, [tentativa.pk])
    assert TentativaDeEnvio.objects.get().erro == "ConnectionError"


def test_banco_recusa_numero_repetido_na_tentativa() -> None:  # A-9
    tentativa = _tentativa()
    with pytest.raises(IntegrityError), transaction.atomic():
        TentativaDeEnvio.objects.create(
            envio=tentativa.envio,
            numero=1,
            iniciada_em=INSTANTE,
            concluida_em=INSTANTE,
            resultado="falha",
        )
    assert TentativaDeEnvio.objects.count() == 1
