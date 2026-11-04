"""E13-05: a previsão de entrega nas telas (acceptance A-13 a A-18)."""

import re
from datetime import UTC, date, datetime
from typing import Any

import pytest
from django.test import Client

from tests.apoio.admin_fluxos import administrador_com_passkey
from tests.apoio.devolucoes import entrar_de_novo
from tests.apoio.pedido_formal import arranjo_af
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

HOJE = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)  # 09:00 em Brasília
INVALIDA = "Informe uma data válida."


@pytest.fixture(autouse=True)
def _passkey(webauthn: Any) -> None:
    """O dublê do WebAuthn para o login do administrador por passkey."""


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _texto(resposta: Any) -> str:
    html = resposta.content.decode()
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _pagina(a: Any) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/pedido-formal/"


def _rota(a: Any) -> str:
    return f"/administracao/rodadas/{a.rodada.pk}/previsao/"


def _af_logado(client: Client, relogio: RelogioControlado, sim: Any, **opcoes: Any) -> Any:
    relogio.congelar(T0)
    _conta, credencial = administrador_com_passkey(client)
    af = arranjo_af(relogio, sim, **opcoes)
    relogio.congelar(HOJE)
    entrar_de_novo(client, credencial, af[0].admin)
    return af


def test_o_bloco_da_previsao_e_o_ajuste(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-13
    a, _x, _y, _pedido = _af_logado(client, relogio, sim)
    texto = _texto(client.get(_pagina(a)))
    assert "Previsão de entrega" in texto
    assert "11/11/2026" in texto
    assert "Prazo padrão de 7 dias" in texto
    assert "Alterar previsão" in texto
    resposta = client.post(_rota(a), {"data": "2026-11-14"}, follow=True)
    assert resposta.redirect_chain[-1][0] == _pagina(a)
    texto = _texto(resposta)
    assert "Previsão de entrega alterada para 14/11/2026." in texto
    assert "Ajuste" in texto
    assert a.admin.nome in texto


@pytest.mark.parametrize(
    ("campos", "status", "mensagem"),
    [
        ({}, 400, INVALIDA),
        ({"data": "14/11/2026"}, 400, INVALIDA),
        ({"data": "2026-11-04"}, 409, "A previsão não pode ser uma data passada."),
    ],
)
def test_data_ausente_malformada_ou_passada(
    client: Client,
    relogio: RelogioControlado,
    sim: Any,
    campos: dict[str, str],
    status: int,
    mensagem: str,
) -> None:  # A-14
    from apps.pedidos.models import PrevisaoDeEntrega

    a, _x, _y, _pedido = _af_logado(client, relogio, sim)
    resposta = client.post(_rota(a), campos)
    assert resposta.status_code == status
    assert mensagem in _texto(resposta)
    assert PrevisaoDeEntrega.objects.count() == 1


def test_acesso_e_metodo(client: Client, relogio: RelogioControlado, sim: Any) -> None:  # A-15
    a, _x, _y, _pedido = _af_logado(client, relogio, sim)
    assert client.get(_rota(a)).status_code == 405
    fornecedor = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    for conta in (a.a, fornecedor):
        client.force_login(conta)
        assert client.post(_rota(a), {"data": "2026-11-14"}).status_code == 403


def test_sem_pedido_formal_a_rota_da_previsao_da_404(
    client: Client, relogio: RelogioControlado
) -> None:  # A-15
    from tests.apoio.apuracao import arranjo_ap

    relogio.congelar(T0)
    _conta, credencial = administrador_com_passkey(client)
    a, _x, _y = arranjo_ap(relogio)
    entrar_de_novo(client, credencial, a.admin)
    assert client.post(_rota(a), {"data": "2026-11-14"}).status_code == 404


def test_rodada_cancelada_mostra_a_previsao_sem_formulario(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-16
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    a, _x, _y, _pedido = _af_logado(client, relogio, sim)
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    texto = _texto(client.get(_pagina(a)))
    assert "Previsão de entrega" in texto
    assert "11/11/2026" in texto
    assert "Prazo padrão de 7 dias" in texto
    assert "Alterar previsão" not in texto


def test_o_comprador_ve_a_previsao_vigente(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-17
    from apps.pedidos.previsao_de_entrega import ajustar_previsao_de_entrega

    from tests.apoio.pedidos import pedido_de

    a, _x, _y, _pedido = _af_logado(client, relogio, sim)
    ajustar_previsao_de_entrega(a.admin, a.rodada, date(2026, 11, 14))
    client.force_login(a.a)
    resposta = client.get(f"/pedidos/{pedido_de(a.a).pk}/")
    assert "Previsão de entrega: 14/11/2026." in _texto(resposta)


def test_pedido_invalido_ou_rodada_cancelada_nao_mostra_previsao(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-18
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
    from tests.apoio.pedidos import pedido_de

    a, x, y, _pedido = _af_logado(client, relogio, sim, pagar_y=False)
    client.force_login(a.b)
    assert "Previsão de entrega" not in _texto(client.get(f"/pedidos/{y.pk}/"))
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    client.force_login(a.a)
    assert "Previsão de entrega" not in _texto(client.get(f"/pedidos/{x.pk}/"))
    assert pedido_de(a.a).pk == x.pk
