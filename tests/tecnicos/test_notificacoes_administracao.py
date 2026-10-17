"""E04-07: consulta administrativa dos envios e falhas (acceptance A-1 a A-9)."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.notificacoes.models import Envio, TentativaDeEnvio
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, EnvioFactory

pytestmark = pytest.mark.django_db

LISTA = "/administracao/envios/"
BASE = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
CONCLUIDO = {"concluido_em": BASE}


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def _ids(html: str) -> list[int]:
    return [int(i) for i in re.findall(r"/administracao/envios/(\d+)/", html)]


class Massa:
    """55 envios: 20 e-mails aceitos, 10 com falha, 10 pendentes, 6 de WhatsApp cancelados,
    8 de WhatsApp aceitos e um convite."""

    def __init__(self) -> None:
        self.conta = ContaFactory.create(nome="Compradora Teste")
        self.ordem: list[Envio] = []
        n = 0

        def novo(**campos: Any) -> Envio:
            nonlocal n
            n += 1
            campos.setdefault("notificacao__conta", self.conta)
            envio = EnvioFactory.create(criado_em=BASE + timedelta(minutes=n), **campos)
            self.ordem.append(envio)
            return envio

        for _ in range(20):
            novo(situacao="enviado", tentativas=1, **CONCLUIDO)
        for _ in range(10):
            novo(situacao="falhou", tentativas=3, **CONCLUIDO)
        for _ in range(10):
            novo()
        for _ in range(6):
            novo(
                canal="whatsapp",
                situacao="cancelado",
                motivo_cancelamento="sem_consentimento",
                **CONCLUIDO,
            )
        for _ in range(8):
            novo(canal="whatsapp", situacao="enviado", tentativas=1, **CONCLUIDO)
        self.convite = EnvioFactory.create(
            notificacao=None,
            conta=None,
            tipo="acesso:convite",
            destino="novo@x.com",
            assunto="Convite",
            corpo="",
            chave="acesso:convite:1",
            situacao="enviado",
            tentativas=1,
            criado_em=BASE + timedelta(minutes=n + 1),
            **CONCLUIDO,
        )
        self.ordem.append(self.convite)

    def esperados(self, **filtros: Any) -> list[int]:
        escolhidos = [
            e
            for e in sorted(self.ordem, key=lambda e: (e.criado_em, e.pk), reverse=True)
            if all(getattr(e, campo) == valor for campo, valor in filtros.items())
        ]
        return [e.pk for e in escolhidos]


def test_lista_paginada_e_ordenada(admin_client: Client) -> None:  # A-1
    massa = Massa()
    pagina1 = admin_client.get(LISTA).content.decode()
    todos = massa.esperados()
    assert _ids(pagina1) == todos[:50]
    assert _ids(admin_client.get(LISTA + "?pagina=2").content.decode()) == todos[50:]
    assert len(todos) == 55
    assert "Aceito pelo serviço" in pagina1
    assert "Compradora Teste" in pagina1
    assert "novo@x.com" in pagina1  # destinatário do convite
    assert "Convite" in pagina1
    assert "E-mail" in pagina1
    assert "WhatsApp" in pagina1


@pytest.mark.parametrize(
    ("consulta", "filtros"),
    [
        ("situacao=falhou", {"situacao": "falhou"}),
        ("canal=whatsapp", {"canal": "whatsapp"}),
        ("tipo=acesso:convite", {"tipo": "acesso:convite"}),
        ("situacao=falhou&canal=email", {"situacao": "falhou", "canal": "email"}),
        ("situacao=xyz", {}),
        ("canal=sms&tipo=inexistente", {}),
    ],
)
def test_filtros_combinaveis_e_valores_invalidos_sao_ignorados(
    admin_client: Client, consulta: str, filtros: dict[str, str]
) -> None:  # A-2
    massa = Massa()
    resposta = admin_client.get(f"{LISTA}?{consulta}")
    assert resposta.status_code == 200
    assert _ids(resposta.content.decode()) == massa.esperados(**filtros)[:50]


def test_detalhe_com_tentativas(admin_client: Client) -> None:  # A-3
    envio = EnvioFactory.create(
        situacao="falhou",
        tentativas=3,
        concluido_em=BASE,
        assunto="Orgânicos Méier: Estorno",
        corpo="Corpo do estorno",
        notificacao__titulo="Estorno de teste",
        notificacao__lida_em=BASE,
    )
    for numero in (1, 2, 3):
        inicio = BASE + timedelta(minutes=numero)
        TentativaDeEnvio.objects.create(
            envio=envio,
            numero=numero,
            iniciada_em=inicio,
            concluida_em=inicio + timedelta(seconds=2),
            resultado="falha",
            erro="ConnectionError",
        )
    html = admin_client.get(f"{LISTA}{envio.pk}/").content.decode()
    assert "Orgânicos Méier: Estorno" in html
    assert "Corpo do estorno" in html
    assert "Estorno de teste" in html
    assert "Estorno" in html  # rótulo do evento
    assert "lida" in html
    assert html.count("ConnectionError") == 3
    assert (
        html.index("16/10/2026 09:01")
        < html.index("16/10/2026 09:02")
        < html.index("16/10/2026 09:03")
    )


def test_corpo_de_email_de_acesso_nao_e_armazenado(admin_client: Client) -> None:  # A-4
    envio = EnvioFactory.create(
        notificacao=None,
        conta=ContaFactory.create(),
        tipo="acesso:link_de_acesso",
        destino="ana@x.com",
        assunto="Seu link",
        corpo="",
        chave="acesso:link_de_acesso:1",
        situacao="enviado",
        tentativas=1,
        concluido_em=BASE,
    )
    html = admin_client.get(f"{LISTA}{envio.pk}/").content.decode()
    assert "(não armazenado: contém link de acesso)" in html


def test_detalhe_de_whatsapp_cancelado(admin_client: Client) -> None:
    envio = EnvioFactory.create(
        canal="whatsapp",
        destino="",
        situacao="cancelado",
        motivo_cancelamento="sem_consentimento",
        concluido_em=BASE,
    )
    html = admin_client.get(f"{LISTA}{envio.pk}/").content.decode()
    assert "sem_consentimento" in html
    assert "Cancelado" in html


def test_indicador_de_falhas_na_pagina_inicial(admin_client: Client) -> None:  # A-5
    EnvioFactory.create(situacao="falhou", tentativas=3, concluido_em=BASE)
    EnvioFactory.create(situacao="falhou", tentativas=3, concluido_em=BASE)
    EnvioFactory.create(situacao="enviado", tentativas=1, concluido_em=BASE)
    html = admin_client.get("/administracao/").content.decode()
    assert "Envios com falha: 2" in html
    assert 'href="/administracao/envios/?situacao=falhou"' in html


def test_sem_falhas_o_indicador_nao_aparece(admin_client: Client) -> None:  # A-5
    EnvioFactory.create(situacao="enviado", tentativas=1, concluido_em=BASE)
    assert "Envios com falha" not in admin_client.get("/administracao/").content.decode()


def _consultas(cliente: Client) -> int:
    with CaptureQueriesContext(connection) as consultas:
        assert cliente.get(LISTA).status_code == 200
    return len(consultas)


def test_a_lista_nao_cai_em_n_mais_um(admin_client: Client) -> None:  # A-6
    conta = ContaFactory.create()
    EnvioFactory.create(notificacao__conta=conta)
    um = _consultas(admin_client)
    for n in range(49):
        envio = EnvioFactory.create(
            notificacao__conta=conta,
            canal="whatsapp" if n % 2 else "email",
            situacao="falhou" if n % 3 == 0 else "enviado",
            tentativas=1,
            concluido_em=BASE,
        )
        TentativaDeEnvio.objects.create(
            envio=envio,
            numero=1,
            iniciada_em=BASE,
            concluida_em=BASE,
            resultado="falha" if n % 3 == 0 else "sucesso",
            erro="ConnectionError" if n % 3 == 0 else "",
        )
    cinquenta = _consultas(admin_client)
    assert um == cinquenta


def test_quem_nao_e_administrador_nao_consulta(client: Client) -> None:  # A-7
    envio = EnvioFactory.create()
    comprador = Client()
    comprador.force_login(ContaFactory.create())
    fornecedor = Client()
    fornecedor.force_login(ContaFactory.create(fornecedor=True))
    for cliente in (comprador, fornecedor):
        assert cliente.get(LISTA).status_code == 403
        assert cliente.get(f"{LISTA}{envio.pk}/").status_code == 403
    for rota in (LISTA, f"{LISTA}{envio.pk}/"):
        resposta = client.get(rota)
        assert resposta.status_code == 302
        assert resposta["Location"].startswith("/entrar/")


def test_so_leitura_e_id_inexistente(admin_client: Client) -> None:  # A-8
    envio = EnvioFactory.create()
    assert admin_client.post(LISTA).status_code == 405
    assert admin_client.post(f"{LISTA}{envio.pk}/").status_code == 405
    assert admin_client.get(f"{LISTA}{envio.pk + 1000}/").status_code == 404


def test_listas_vazias(admin_client: Client) -> None:  # A-9
    assert "Nenhum envio registrado." in admin_client.get(LISTA).content.decode()
    EnvioFactory.create(situacao="enviado", tentativas=1, concluido_em=BASE)
    html = admin_client.get(f"{LISTA}?situacao=cancelado").content.decode()
    assert "Nenhum envio com estes filtros." in html
    assert re.search(r'<option value="cancelado"\s+selected', html)


def test_envio_pendente_mostra_a_proxima_tentativa(admin_client: Client) -> None:
    EnvioFactory.create(proxima_tentativa_em=BASE + timedelta(minutes=1), tentativas=1)
    html = admin_client.get(LISTA).content.decode()
    assert "Próxima tentativa: 16/10/2026 09:01" in html
