"""E14-03: o endereço no carrinho, a página de regras e a página do administrador
(acceptance A-5 a A-12)."""

import re
from typing import Any

import pytest
from django.conf import settings
from django.test import Client

from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.pedidos import T0, montar_arranjo
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

ENDERECO = "Rua das Hortas, 100 — Méier, Rio de Janeiro/RJ"
PAGINA = "/administracao/retirada/endereco/"
RECUSA = "Informe o endereço de retirada, com até 500 caracteres."


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _como(conta: Any) -> Client:
    cliente = Client()
    cliente.force_login(conta)
    return cliente


def _mundo(client: Client, relogio: RelogioControlado) -> tuple[Any, Any, Any]:
    """O arranjo com A em `interesse`, o administrador logado no `client`, o fornecedor e um
    comprador suspenso. Devolve o arranjo, a conta de fornecedor e a suspensa."""
    from apps.rodadas.models import Rodada

    relogio.congelar(T0)
    _conta, credencial = administrador_com_passkey(client)
    a = montar_arranjo(minimo="50.00")
    Rodada.objects.filter(pk=a.rodada.pk).update(etapa="interesse")
    conta_f = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    suspensa = ContaFactory.create(nome="Suspensa", situacao="suspensa")
    entrar_de_novo(client, credencial, a.admin)
    return a, conta_f, suspensa


def _definir(admin: Any, texto: str) -> None:
    from apps.pedidos.endereco_de_retirada import definir_endereco_de_retirada

    definir_endereco_de_retirada(admin, texto)


def _enderecos() -> int:
    from apps.pedidos.models import EnderecoDeRetirada

    return EnderecoDeRetirada.objects.count()


def test_o_carrinho_mostra_o_endereco(client: Client, relogio: RelogioControlado) -> None:  # A-5
    a, _f, _s = _mundo(client, relogio)
    _definir(a.admin, ENDERECO)
    resposta = _como(a.a).get("/carrinho/")
    assert resposta.status_code == 200
    assert f"Retirada: {ENDERECO}" in _texto(resposta)


def test_o_carrinho_sem_endereco(client: Client, relogio: RelogioControlado) -> None:  # A-6
    a, _f, _s = _mundo(client, relogio)
    assert "Retirada: endereço ainda não informado." in _texto(_como(a.a).get("/carrinho/"))


def test_a_pagina_de_regras(client: Client, relogio: RelogioControlado) -> None:  # A-7
    a, _f, suspensa = _mundo(client, relogio)
    _definir(a.admin, ENDERECO)
    for cliente in (_como(a.a), _como(suspensa), client):
        resposta = cliente.get("/regras/")
        assert resposta.status_code == 200
        texto = _texto(resposta)
        assert f"Endereço: {ENDERECO}" in texto
        assert 'href="/comunicados/"' in resposta.content.decode()
        assert "o prazo para retirar é de sete dias" in texto
        assert "Não há substituição de produtos." in texto


def test_regras_recusadas_ao_fornecedor_e_ao_anonimo(
    client: Client, relogio: RelogioControlado
) -> None:  # A-8
    a, conta_f, _s = _mundo(client, relogio)
    _definir(a.admin, ENDERECO)
    resposta = _como(conta_f).get("/regras/")
    assert resposta.status_code == 403
    assert "Rua das Hortas" not in resposta.content.decode()
    anonimo = Client().get("/regras/")
    assert anonimo.status_code == 302
    assert anonimo["Location"].startswith(settings.LOGIN_URL)
    assert "Rua das Hortas" not in anonimo.content.decode()


def test_o_link_das_regras_na_pagina_inicial(
    client: Client, relogio: RelogioControlado
) -> None:  # A-9
    a, conta_f, _s = _mundo(client, relogio)
    assert "Regras de funcionamento" in _texto(_como(a.a).get("/inicio/"))
    assert "Regras de funcionamento" in _texto(client.get("/inicio/"))
    assert "Regras de funcionamento" not in _texto(_como(conta_f).get("/inicio/"))


def test_a_pagina_do_administrador(client: Client, relogio: RelogioControlado) -> None:  # A-10
    a, _f, _s = _mundo(client, relogio)
    assert "Nenhum endereço registrado." in _texto(client.get(PAGINA))
    _definir(a.admin, ENDERECO)
    _definir(a.admin, "Rua Nova, 5")
    texto = _texto(client.get(PAGINA))
    assert "Rua Nova, 5" in texto
    assert texto.index("Rua Nova, 5") < texto.rindex("Rua das Hortas, 100")
    resposta = client.post(PAGINA, {"texto": "Rua Outra, 9"}, follow=True)
    assert resposta.redirect_chain[-1][0] == PAGINA
    assert "Endereço de retirada atualizado." in _texto(resposta)
    recusada = client.post(PAGINA, {"texto": ""})
    assert recusada.status_code == 400
    assert RECUSA in _texto(recusada)
    assert _enderecos() == 3


def test_a_pagina_do_administrador_e_recusada_aos_demais(
    client: Client, relogio: RelogioControlado
) -> None:  # A-11
    a, conta_f, _s = _mundo(client, relogio)
    for conta in (a.a, conta_f):
        cliente = _como(conta)
        assert cliente.get(PAGINA).status_code == 403
        assert cliente.post(PAGINA, {"texto": ENDERECO}).status_code == 403
    anonimo = Client()
    assert anonimo.get(PAGINA).status_code == 302
    assert anonimo.post(PAGINA, {"texto": ENDERECO}).status_code == 302
    assert _enderecos() == 0


def test_quebras_de_linha_e_html_escapado(
    client: Client, relogio: RelogioControlado
) -> None:  # A-12
    a, _f, _s = _mundo(client, relogio)
    _definir(a.admin, "Rua A, 1\r\nFundos <b>")
    for html in (
        _como(a.a).get("/regras/").content.decode(),
        _como(a.a).get("/carrinho/").content.decode(),
    ):
        assert "Rua A, 1<br>Fundos &lt;b&gt;" in html
        assert "<b>" not in html
