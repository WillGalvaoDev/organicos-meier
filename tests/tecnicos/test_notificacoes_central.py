"""E04-01: central de notificações, marcação de lida e contador (acceptance A-6 a A-12)."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import connection
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext

from apps.contas.models import Conta
from apps.notificacoes.contexto import notificacoes_nao_lidas
from apps.notificacoes.models import Notificacao
from tests.apoio.admin_fluxos import administrador_logado
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, NotificacaoFactory

pytestmark = pytest.mark.django_db

BASE = datetime(2026, 10, 16, 15, 30, tzinfo=UTC)


def _entrar(conta: Conta) -> Client:
    cliente = Client()
    cliente.force_login(conta)
    return cliente


def _titulos(html: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", t).strip() for t in re.findall(r"<h2>(.*?)</h2>", html, re.S)]


def test_central_lista_so_as_proprias_em_paginas_de_30() -> None:  # A-6
    c1, c2 = ContaFactory.create(), ContaFactory.create()
    for i in range(35):
        NotificacaoFactory.create(
            conta=c1,
            titulo=f"N{i:02d}",
            corpo="<b>x</b>\nsegunda linha" if i == 34 else f"corpo {i}",
            criada_em=BASE + timedelta(minutes=i),
            lida_em=BASE if i < 3 else None,
        )
    for i in range(2):
        NotificacaoFactory.create(conta=c2, titulo=f"OUTRA{i}")
    cliente = _entrar(c1)
    pagina1 = cliente.get("/notificacoes/").content.decode()
    titulos = _titulos(pagina1)
    assert titulos == [f"N{i:02d}" + (" Nova" if i >= 3 else "") for i in range(34, 4, -1)]
    assert "OUTRA" not in pagina1
    assert "&lt;b&gt;x&lt;/b&gt;<br>segunda linha" in pagina1
    assert "<b>x</b>" not in pagina1
    assert "16/10/2026 13:04" in pagina1  # 15:30 UTC + 34 min = 16:04 UTC = 13:04 em São Paulo
    pagina2 = cliente.get("/notificacoes/?pagina=2").content.decode()
    assert _titulos(pagina2) == [
        "N04 Nova",
        "N03 Nova",
        "N02",
        "N01",
        "N00",
    ]
    assert "OUTRA" not in pagina2


def test_central_vazia_e_pagina_inexistente() -> None:  # A-7
    vazia = _entrar(ContaFactory.create()).get("/notificacoes/")
    assert "Você não tem notificações." in vazia.content.decode()
    conta = ContaFactory.create()
    for i in range(35):
        NotificacaoFactory.create(conta=conta, titulo=f"N{i:02d}", criada_em=BASE + timedelta(i))
    ultima = _entrar(conta).get("/notificacoes/?pagina=99").content.decode()
    assert len(_titulos(ultima)) == 5
    assert "Página 2 de 2" in ultima


def test_marcar_a_notificacao_de_outra_conta_ou_inexistente_e_404() -> None:  # A-8
    c1, c2 = ContaFactory.create(), ContaFactory.create()
    alheia = NotificacaoFactory.create(conta=c2)
    cliente = _entrar(c1)
    de_outra = cliente.post(f"/notificacoes/{alheia.pk}/lida/")
    inexistente = cliente.post(f"/notificacoes/{alheia.pk + 1000}/lida/")
    assert de_outra.status_code == inexistente.status_code == 404
    assert de_outra.content == inexistente.content
    alheia.refresh_from_db()
    assert alheia.lida_em is None


def test_marcar_duas_vezes_mantem_o_primeiro_instante(
    relogio: RelogioControlado,
) -> None:  # A-9
    conta = ContaFactory.create()
    notificacao = NotificacaoFactory.create(conta=conta)
    cliente = _entrar(conta)
    relogio.congelar(BASE)
    primeira = cliente.post(f"/notificacoes/{notificacao.pk}/lida/")
    relogio.avancar(timedelta(minutes=5))
    segunda = cliente.post(f"/notificacoes/{notificacao.pk}/lida/")
    assert primeira.status_code == segunda.status_code == 302
    assert primeira["Location"] == segunda["Location"] == "/notificacoes/"
    notificacao.refresh_from_db()
    assert notificacao.lida_em == BASE
    htmx = cliente.post(f"/notificacoes/{notificacao.pk}/lida/", HTTP_HX_REQUEST="true")
    assert htmx.status_code == 200
    assert "Nova" not in htmx.content.decode()
    assert notificacao.titulo in htmx.content.decode()
    notificacao.refresh_from_db()
    assert notificacao.lida_em == BASE


def test_marcar_com_htmx_devolve_o_fragmento_atualizado() -> None:  # A-9
    conta = ContaFactory.create()
    notificacao = NotificacaoFactory.create(conta=conta)
    resposta = _entrar(conta).post(f"/notificacoes/{notificacao.pk}/lida/", HTTP_HX_REQUEST="true")
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Nova" not in html
    assert "<html" not in html
    notificacao.refresh_from_db()
    assert notificacao.lida_em is not None


def test_marcar_preserva_a_pagina() -> None:
    conta = ContaFactory.create()
    notificacao = NotificacaoFactory.create(conta=conta)
    resposta = _entrar(conta).post(f"/notificacoes/{notificacao.pk}/lida/", {"pagina": "2"})
    assert resposta["Location"] == "/notificacoes/?pagina=2"


def test_marcar_todas_so_marca_as_da_propria_conta() -> None:  # A-10
    c1, c2 = ContaFactory.create(), ContaFactory.create()
    for _ in range(3):
        NotificacaoFactory.create(conta=c1)
    for _ in range(2):
        NotificacaoFactory.create(conta=c2)
    resposta = _entrar(c1).post("/notificacoes/lidas/")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/notificacoes/"
    assert Notificacao.objects.filter(conta=c1, lida_em__isnull=True).count() == 0
    assert Notificacao.objects.filter(conta=c2, lida_em__isnull=True).count() == 2


def test_abrir_a_central_nao_marca_nada() -> None:
    conta = ContaFactory.create()
    NotificacaoFactory.create(conta=conta)
    _entrar(conta).get("/notificacoes/")
    assert Notificacao.objects.filter(conta=conta, lida_em__isnull=True).count() == 1


def test_contador_no_cabecalho_e_consultas_do_processador() -> None:  # A-11
    conta = ContaFactory.create()
    for _ in range(3):
        NotificacaoFactory.create(conta=conta)
    cliente = _entrar(conta)
    assert "Notificações (3)" in cliente.get("/inicio/").content.decode()
    fabrica = RequestFactory()
    requisicao = fabrica.get("/inicio/")
    requisicao.user = conta
    with CaptureQueriesContext(connection) as consultas:
        assert notificacoes_nao_lidas(requisicao) == {"notificacoes_nao_lidas": 3}
    assert len(consultas) == 1
    cliente.post("/notificacoes/lidas/")
    html = cliente.get("/inicio/").content.decode()
    assert "Notificações" in html
    assert "Notificações (" not in html


def test_anonimo_nao_ve_o_link_nem_gera_consulta() -> None:  # A-11
    from django.contrib.auth.models import AnonymousUser

    requisicao = RequestFactory().get("/entrar/")
    requisicao.user = AnonymousUser()
    with CaptureQueriesContext(connection) as consultas:
        assert notificacoes_nao_lidas(requisicao) == {"notificacoes_nao_lidas": 0}
    assert len(consultas) == 0
    html = Client().get("/entrar/").content.decode()
    assert "/notificacoes/" not in html


def test_quem_acessa_a_central_e_o_que_o_anonimo_recebe(webauthn: Any) -> None:  # A-12
    suspenso = ContaFactory.create(suspensa=True)
    fornecedor = ContaFactory.create(fornecedor=True)
    for conta in (suspenso, fornecedor):
        propria = NotificacaoFactory.create(conta=conta)
        cliente = _entrar(conta)
        assert cliente.get("/notificacoes/").status_code == 200
        marcada = cliente.post(f"/notificacoes/{propria.pk}/lida/")
        assert marcada.status_code == 302
        propria.refresh_from_db()
        assert propria.lida_em is not None
    admin_client = Client()
    administrador_logado(admin_client)
    administrador = Conta.objects.get(papel="administrador")
    do_admin = NotificacaoFactory.create(conta=administrador, evento="falha_no_pedido_formal")
    assert admin_client.get("/notificacoes/").status_code == 200
    assert admin_client.post(f"/notificacoes/{do_admin.pk}/lida/").status_code == 302
    anonimo = Client()
    for resposta in (
        anonimo.get("/notificacoes/"),
        anonimo.post(f"/notificacoes/{do_admin.pk}/lida/"),
        anonimo.post("/notificacoes/lidas/"),
    ):
        assert resposta.status_code == 302
        assert resposta["Location"].startswith("/entrar/")
    assert _entrar(suspenso).get(f"/notificacoes/{do_admin.pk}/lida/").status_code == 405
