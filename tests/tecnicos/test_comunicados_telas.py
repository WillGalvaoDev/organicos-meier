"""E04-06: telas de comunicados (acceptance A-6 a A-12 e A-14)."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.contas.models import Conta
from apps.notificacoes.comunicados import publicar_comunicado
from apps.notificacoes.models import Comunicado
from apps.notificacoes.processamento import processar_envios
from tests.apoio.admin_fluxos import administrador_logado
from tests.apoio.email_falho import BackendQueFalhaPara
from tests.conftest import RelogioControlado
from tests.fabricas import ComunicadoFactory, ContaFactory

pytestmark = pytest.mark.django_db

ROTA = "/administracao/comunicados/"
T0 = datetime(2026, 10, 16, 15, 30, tzinfo=UTC)


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def _admin() -> Conta:
    return Conta.objects.get(papel="administrador")


def _comprador_logado(**campos: Any) -> tuple[Client, Conta]:
    conta = ContaFactory.create(**campos)
    cliente = Client()
    cliente.force_login(conta)
    return cliente, conta


def _token_do_formulario(html: str) -> str:
    achado = re.search(r'name="token" value="([0-9a-f-]{36})"', html)
    assert achado, html
    return achado.group(1)


def test_publicar_pela_tela_e_repetir_o_envio(admin_client: Client) -> None:  # A-6
    for _ in range(3):
        ContaFactory.create()
    pagina = admin_client.get(ROTA).content.decode()
    assert "Será enviado para 3 compradores." in pagina
    token = _token_do_formulario(pagina)
    dados = {"titulo": "Feira", "mensagem": "Sábado", "token": token}
    primeira = admin_client.post(ROTA, dados, follow=True)
    assert "Comunicado publicado para 3 compradores." in primeira.content.decode()
    segunda = admin_client.post(ROTA, dados, follow=True)
    assert "Este comunicado já tinha sido publicado." in segunda.content.decode()
    assert Comunicado.objects.count() == 1


def test_publicacao_invalida_devolve_os_valores(admin_client: Client) -> None:  # A-7
    token = str(uuid.uuid4())
    resposta = admin_client.post(ROTA, {"titulo": "", "mensagem": "texto", "token": token})
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "texto" in html
    assert token in html
    assert "Este campo é obrigatório." in html
    assert Comunicado.objects.count() == 0


def test_historico_com_contagem_de_envios(
    admin_client: Client, settings: Any, relogio: RelogioControlado
) -> None:  # A-8
    settings.EMAIL_BACKEND = "tests.apoio.email_falho.BackendQueFalhaPara"
    relogio.congelar(T0)
    admin = _admin()
    ContaFactory.create(
        email_normalizado="a@x.com", telefone="+5521999990000", whatsapp_consentido_em=T0
    )
    ContaFactory.create(email_normalizado="b@x.com")
    ContaFactory.create(email_normalizado="s@x.com", suspensa=True)
    BackendQueFalhaPara.configurar(destinos={"b@x.com"})
    comunicado, _ = publicar_comunicado(admin, titulo="Feira", mensagem="m", token=uuid.uuid4())
    for espera in (timedelta(0), timedelta(minutes=1), timedelta(minutes=10)):
        relogio.avancar(espera)
        processar_envios()
    html = admin_client.get(ROTA).content.decode()
    assert "Feira" in html
    assert admin.nome in html
    assert "e-mail: 2 aceitos, 1 com falha" in html
    assert "WhatsApp: 1 aceito" in html
    assert "16/10/2026 12:30" in html
    assert comunicado.destinatarios == 3
    assert "<td>3</td>" in html


def test_comprador_suspenso_le_os_comunicados() -> None:  # A-9
    admin = ContaFactory.create(administrador=True)
    antigo = ComunicadoFactory.create(
        autor=admin, titulo="Antigo", mensagem="<b>x</b>", publicado_em=T0 - timedelta(days=1)
    )
    novo = ComunicadoFactory.create(
        autor=admin, titulo="Novo", mensagem="linha 1\nlinha 2", publicado_em=T0
    )
    cliente, _ = _comprador_logado(suspensa=True)
    resposta = cliente.get("/comunicados/")
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert html.index("Novo") < html.index("Antigo")
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<b>x</b>" not in html
    assert "linha 1<br>linha 2" in html
    assert f'id="c{novo.pk}"' in html
    assert f'id="c{antigo.pk}"' in html
    assert admin.nome not in html
    assert "destinat" not in html.lower()


def test_comprador_novo_ve_o_comunicado_antigo_sem_notificacao() -> None:  # A-10
    admin = ContaFactory.create(administrador=True)
    publicar_comunicado(admin, titulo="Antigo", mensagem="m", token=uuid.uuid4())
    cliente, _ = _comprador_logado()
    assert "Antigo" in cliente.get("/comunicados/").content.decode()
    assert "Você não tem notificações." in cliente.get("/notificacoes/").content.decode()


def test_sem_comunicados() -> None:
    cliente, _ = _comprador_logado()
    assert "Nenhum comunicado publicado." in cliente.get("/comunicados/").content.decode()


def test_quem_nao_e_comprador_nao_le_comunicados(admin_client: Client) -> None:  # A-11
    fornecedor = Client()
    fornecedor.force_login(ContaFactory.create(fornecedor=True))
    assert fornecedor.get("/comunicados/").status_code == 403
    assert admin_client.get("/comunicados/").status_code == 403
    anonimo = Client().get("/comunicados/")
    assert anonimo.status_code == 302
    assert anonimo["Location"].startswith("/entrar/")


def test_o_comprador_nao_publica(admin_client: Client) -> None:
    cliente, _ = _comprador_logado()
    assert cliente.get(ROTA).status_code == 403
    resposta = cliente.post(ROTA, {"titulo": "t", "mensagem": "m", "token": str(uuid.uuid4())})
    assert resposta.status_code == 403
    assert Comunicado.objects.count() == 0


def _consultas_do_historico(cliente: Client) -> int:
    with CaptureQueriesContext(connection) as consultas:
        assert cliente.get(ROTA).status_code == 200
    return len(consultas)


def test_o_historico_nao_cai_em_n_mais_um(admin_client: Client) -> None:  # A-12
    admin = _admin()
    ComunicadoFactory.create(autor=admin)
    um = _consultas_do_historico(admin_client)
    for _ in range(19):
        ComunicadoFactory.create(autor=admin)
    vinte = _consultas_do_historico(admin_client)
    assert um == vinte


def test_publicar_sem_compradores_aparece_na_pagina(admin_client: Client) -> None:  # A-14
    token = _token_do_formulario(admin_client.get(ROTA).content.decode())
    admin_client.post(ROTA, {"titulo": "Aviso", "mensagem": "m", "token": token})
    assert Comunicado.objects.get().destinatarios == 0
    cliente, _ = _comprador_logado()
    assert "Aviso" in cliente.get("/comunicados/").content.decode()


def test_inicio_do_comprador_tem_o_link_de_comunicados() -> None:
    cliente, _ = _comprador_logado()
    assert 'href="/comunicados/"' in cliente.get("/inicio/").content.decode()
