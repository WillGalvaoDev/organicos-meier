"""E04-R01: link da notificação é sempre um caminho interno do site.

Critérios A-15 a A-17 da E04-01 e A-15 da E04-02. Os três testes do revisor de `0b52010`
(`test_link_externo_disfarcado_de_relativo_deve_ser_recusado`,
`test_banco_deve_recusar_link_externo_disfarcado` e `test_links_internos_continuam_validos`)
entram aqui com o corpo original.
"""

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import Client
from django.utils.html import escape
from django.utils.http import url_has_allowed_host_and_scheme

from apps.notificacoes.emissao import emitir_evento, emitir_evento_para_varios
from apps.notificacoes.eventos import Evento
from apps.notificacoes.models import Envio, Notificacao
from apps.notificacoes.servicos import NotificacaoInvalida, criar_notificacao
from tests.fabricas import ContaFactory, NotificacaoFactory

pytestmark = pytest.mark.django_db

RECUSADOS = [
    "/\\externo.example/",
    "/\t/externo.example/",
    "/\n/externo.example/",
    "/\r/externo.example/",
    "/\\/externo.example",
    "/x\\y",
    "\\\\externo.example",
    "/\x00",
    "/\x7f",
    "/ /x",
    "/é/",
    "/%zz",
    "/%4",
    "/<x>",
    "/x\n",
    "//x.com",
    "https://x.com",
    "x/",
]

ACEITOS = [
    "/",
    "/historico/",
    "/catalogo/1/?q=abc#x",
    "/catalogo/?q=caf%C3%A9",
    "/rodadas/3/?a=1&b=2",
    "/a/b;c=1/~x/",
    "/x?proximo=//y",
]

NO_BANCO = ["/\\externo.example/", "/\t/externo.example/", "/\n/x", "/ /x", "/é/", "/%zz"]


@pytest.mark.parametrize("link", RECUSADOS)
def test_criar_notificacao_recusa_link_fora_da_regra(link: str) -> None:  # A-15 (E04-01)
    conta = ContaFactory.create()
    with pytest.raises(NotificacaoInvalida) as erro:
        criar_notificacao(conta, Evento.ESTORNO, titulo="t", corpo="c", link=link, chave="k")
    assert erro.value.campo == "link"
    assert Notificacao.objects.count() == 0


@pytest.mark.parametrize("link", NO_BANCO)
def test_check_do_banco_recusa_pela_fabrica(link: str) -> None:  # A-16
    with pytest.raises(IntegrityError, match="notificacao_link_interno"), transaction.atomic():
        NotificacaoFactory.create(link=link)


@pytest.mark.parametrize("link", NO_BANCO)
def test_check_do_banco_recusa_por_sql_direto(link: str) -> None:  # A-16
    conta = ContaFactory.create()
    with (
        pytest.raises(IntegrityError, match="notificacao_link_interno"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "INSERT INTO notificacoes_notificacao"
            " (conta_id, evento, titulo, corpo, link, chave, criada_em)"
            " VALUES (%s, 'estorno', 't', 'c', %s, 'sql:1', now())",
            [conta.pk, link],
        )


@pytest.mark.parametrize("link", ACEITOS)
def test_links_internos_sao_gravados_iguais_e_aparecem_na_central(link: str) -> None:  # A-17
    conta = ContaFactory.create()
    notificacao = criar_notificacao(
        conta, Evento.ESTORNO, titulo="t", corpo="c", link=link, chave="k"
    )
    assert Notificacao.objects.get(pk=notificacao.pk).link == link
    assert url_has_allowed_host_and_scheme(link, allowed_hosts={"om.test"})
    cliente = Client()
    cliente.force_login(conta)
    html = cliente.get("/notificacoes/").content.decode()
    assert f'href="{escape(link)}"' in html


@pytest.mark.parametrize("link", RECUSADOS)
def test_emissao_recusa_link_fora_da_regra(link: str) -> None:  # A-15 (E04-02)
    a, b = ContaFactory.create(), ContaFactory.create()
    with pytest.raises(NotificacaoInvalida) as erro, transaction.atomic():
        emitir_evento(Evento.ESTORNO, a, titulo="t", corpo="c", link=link, chave="e:1")
    assert erro.value.campo == "link"
    with pytest.raises(NotificacaoInvalida) as erro, transaction.atomic():
        emitir_evento_para_varios(
            Evento.ESTORNO, [a, b], titulo="t", corpo="c", link=link, chave_base="l"
        )
    assert erro.value.campo == "link"
    assert Notificacao.objects.count() == 0
    assert Envio.objects.count() == 0


def test_emissao_aceita_link_interno() -> None:  # A-15 (E04-02)
    a, b = ContaFactory.create(), ContaFactory.create()
    link = "/catalogo/1/?q=abc#x"
    with transaction.atomic():
        emitir_evento(Evento.ESTORNO, a, titulo="t", corpo="c", link=link, chave="e:1")
        assert (
            emitir_evento_para_varios(
                Evento.ESTORNO, [a, b], titulo="t", corpo="c", link=link, chave_base="l"
            )
            == 2
        )
    assert set(Notificacao.objects.values_list("link", flat=True)) == {link}


# --- probes do revisor de 0b52010 (corpo original) ---


@pytest.mark.parametrize(
    "link", ["/\\externo.example/", "/\t/externo.example/"], ids=["barra_invertida", "tabulacao"]
)
@pytest.mark.parametrize("modo", ["criar", "emitir", "lote"])
def test_link_externo_disfarcado_de_relativo_deve_ser_recusado(link: str, modo: str) -> None:
    conta = ContaFactory.create()
    with pytest.raises(NotificacaoInvalida), transaction.atomic():  # noqa: PT012
        if modo == "criar":
            criar_notificacao(
                conta, Evento.ESTORNO, titulo="t", corpo="c", link=link, chave="probe"
            )
        elif modo == "emitir":
            emitir_evento(Evento.ESTORNO, conta, titulo="t", corpo="c", link=link, chave="probe")
        else:
            emitir_evento_para_varios(
                Evento.ESTORNO, [conta], titulo="t", corpo="c", link=link, chave_base="probe"
            )


@pytest.mark.parametrize(
    "link", ["/\\externo.example/", "/\t/externo.example/"], ids=["barra_invertida", "tabulacao"]
)
def test_banco_deve_recusar_link_externo_disfarcado(link: str) -> None:
    conta = ContaFactory.create()
    with pytest.raises(IntegrityError), transaction.atomic():
        NotificacaoFactory.create(conta=conta, link=link)


@pytest.mark.parametrize("link", ["/historico/", "/catalogo/1/?q=abc#x"])
def test_links_internos_continuam_validos(link: str) -> None:
    conta = ContaFactory.create()
    n = criar_notificacao(conta, Evento.ESTORNO, titulo="t", corpo="c", link=link, chave="probe")
    assert n.link == link
    assert url_has_allowed_host_and_scheme(link, allowed_hosts={"om.test"})
