"""E08-03: telas do comprador para pagar (acceptance A-14 a A-17)."""

from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.urls import resolve

from apps.contas.models import Situacao
from apps.contas.permissoes import Politica, politica_da_view, rotas_sem_politica
from apps.pagamentos.chamadas import processar_chamadas
from apps.pedidos.models import Pedido, TentativaDePagamento
from apps.pedidos.pagamento import pedir_pagamento
from tests.apoio.pedidos import (
    T0,
    Arranjo,
    cancelar_direto,
    marcar_pago,
    pedido_aberto,
    pedido_avulso,
)
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario(relogio: RelogioControlado, simulador_pagamentos: Any) -> tuple[Arranjo, Pedido]:
    return pedido_aberto(relogio)


def _cliente(conta: Any) -> Client:
    cliente = Client()
    if conta is not None:
        cliente.force_login(conta)
    return cliente


def _detalhe(x: Pedido) -> str:
    return f"/pedidos/{x.pk}/"


def _pagar(x: Pedido) -> str:
    return f"/pedidos/{x.pk}/pagar/"


def test_lista_e_detalhe_com_tentativa_aberta(cenario: tuple[Arranjo, Pedido]) -> None:  # A-14
    arranjo, x = cenario
    pedir_pagamento(arranjo.a, x)
    processar_chamadas()
    cliente = _cliente(arranjo.a)
    lista = cliente.get("/pedidos/")
    assert lista.status_code == 200
    html = lista.content.decode()
    assert "F" in html
    assert "R$ 94,35" in html
    assert "Aguardando pagamento até 03/11/2026 às 10:00" in html
    assert f'href="{_detalhe(x)}"' in html
    detalhe = cliente.get(_detalhe(x))
    assert detalhe.status_code == 200
    html = detalhe.content.decode()
    for esperado in (
        "P1",
        "P2",
        "R$ 60,00",  # 6 a R$ 10,00
        "R$ 20,00",  # 4 a R$ 5,00
        "Produtos",
        "R$ 80,00",
        "Serviço",
        "R$ 4,00",
        "Frete",
        "R$ 10,35",
        "Total",
        "R$ 94,35",
        "Esse prazo de 24 horas não é prorrogado.",
        "03/11/2026 às 10:00",
        "SIMULADO-",
        "Pague pelo aplicativo do seu banco. A confirmação pode levar alguns minutos.",
    ):
        assert esperado in html, esperado
    assert "Pagar com Pix" not in html
    assert "Estamos gerando a sua cobrança" not in html


def test_sem_tentativa_o_botao_gera_a_cobranca(cenario: tuple[Arranjo, Pedido]) -> None:  # A-15
    arranjo, x = cenario
    cliente = _cliente(arranjo.a)
    html = cliente.get(_detalhe(x)).content.decode()
    assert "Pagar com Pix" in html
    assert f'action="{_pagar(x)}"' in html
    resposta = cliente.post(_pagar(x))
    assert resposta.status_code == 302
    assert resposta["Location"] == _detalhe(x)
    html = cliente.get(_detalhe(x)).content.decode()
    assert "Estamos gerando a sua cobrança. Atualize esta página em alguns instantes." in html
    assert "Pagar com Pix" not in html
    assert TentativaDePagamento.objects.filter(pedido=x).count() == 1


def test_pedido_de_outro_comprador_nao_aparece(cenario: tuple[Arranjo, Pedido]) -> None:  # A-16
    arranjo, x = cenario
    cliente = _cliente(arranjo.b)
    assert cliente.get(_detalhe(x)).status_code == 404
    assert cliente.post(_pagar(x)).status_code == 404
    lista = cliente.get("/pedidos/").content.decode()
    assert _detalhe(x) not in lista
    assert TentativaDePagamento.objects.count() == 0


def test_anonimo_fornecedor_e_suspenso_sao_recusados(cenario: tuple[Arranjo, Pedido]) -> None:
    # A-16
    arranjo, x = cenario
    fornecedor = ContaFactory.create(fornecedor=True)
    rotas = [("get", "/pedidos/"), ("get", _detalhe(x)), ("post", _pagar(x))]
    for metodo, caminho in rotas:
        anonimo = getattr(_cliente(None), metodo)(caminho)
        assert anonimo.status_code == 302
        assert "/entrar/" in anonimo["Location"]
        assert getattr(_cliente(fornecedor), metodo)(caminho).status_code == 403
    type(arranjo.a).objects.filter(pk=arranjo.a.pk).update(situacao=Situacao.SUSPENSA)
    arranjo.a.refresh_from_db()
    assert _cliente(arranjo.a).post(_pagar(x)).status_code == 403
    assert TentativaDePagamento.objects.count() == 0


def test_as_tres_rotas_declaram_a_politica() -> None:  # A-16
    assert rotas_sem_politica() == []
    for caminho, politica in (
        ("/pedidos/", Politica.COMPRADOR),
        ("/pedidos/1/", Politica.COMPRADOR),
        ("/pedidos/1/pagar/", Politica.COMPRADOR_ATIVO),
    ):
        assert politica_da_view(resolve(caminho).func) == politica, caminho
    assert resolve("/pedidos/").url_name == "pedidos_lista"
    assert resolve("/pedidos/1/").url_name == "pedidos_detalhe"
    assert resolve("/pedidos/1/pagar/").url_name == "pedidos_pagar"


def test_pagamento_recusado_responde_409_com_a_mensagem(
    cenario: tuple[Arranjo, Pedido],
) -> None:  # A-7 (tela)
    arranjo, x = cenario
    cancelar_direto(x)
    resposta = _cliente(arranjo.a).post(_pagar(x))
    assert resposta.status_code == 409
    assert "Este pedido foi cancelado e não pode mais ser pago." in resposta.content.decode()
    assert TentativaDePagamento.objects.count() == 0


def test_suspenso_ve_os_pedidos_sem_botao_de_pagar(cenario: tuple[Arranjo, Pedido]) -> None:
    # A-17
    arranjo, x = cenario
    y = pedido_avulso(arranjo.a, "G", "50.00")
    marcar_pago(x)
    cancelar_direto(y)
    type(arranjo.a).objects.filter(pk=arranjo.a.pk).update(situacao=Situacao.SUSPENSA)
    arranjo.a.refresh_from_db()
    cliente = _cliente(arranjo.a)
    lista = cliente.get("/pedidos/")
    assert lista.status_code == 200
    html = lista.content.decode()
    assert "Pago" in html
    assert "Cancelado" in html
    for pedido in (x, y):
        detalhe = cliente.get(_detalhe(pedido))
        assert detalhe.status_code == 200
        pagina = detalhe.content.decode()
        assert "Pagar com Pix" not in pagina
        assert _pagar(pedido) not in pagina
    assert "Pago" in cliente.get(_detalhe(x)).content.decode()
    assert "Cancelado" in cliente.get(_detalhe(y)).content.decode()


def test_prazo_encerrado_na_lista_e_sem_botao(
    cenario: tuple[Arranjo, Pedido], relogio: RelogioControlado
) -> None:
    from datetime import timedelta

    from tests.apoio.pedidos import T0

    arranjo, x = cenario
    relogio.congelar(T0 + timedelta(hours=24))
    cliente = _cliente(arranjo.a)
    assert "Prazo encerrado" in cliente.get("/pedidos/").content.decode()
    assert "Pagar com Pix" not in cliente.get(_detalhe(x)).content.decode()


# --- Correção E08-R02 (A-28) ---------------------------------------------------------------


def test_pedido_cancelado_nao_mostra_mensagem_de_tentativa(
    cenario: tuple[Arranjo, Pedido],
) -> None:  # A-28
    arranjo, x = cenario
    pedir_pagamento(arranjo.a, x)
    cancelar_direto(x, "suspensao")
    cliente = _cliente(arranjo.a)
    for _ in range(2):  # antes e depois de a criação ser recusada
        html = cliente.get(_detalhe(x)).content.decode()
        assert "Cancelado" in html
        assert "Estamos gerando a sua cobrança" not in html
        assert "Não foi possível gerar a cobrança antes do fim do prazo." not in html
        processar_chamadas()
    assert TentativaDePagamento.objects.get(pedido=x).codigo_da_falha == "pedido_cancelado"


def test_a_espera_so_aparece_dentro_do_prazo(
    cenario: tuple[Arranjo, Pedido], relogio: RelogioControlado
) -> None:  # regra da tela, E08-03 correção R02
    arranjo, x = cenario
    pedir_pagamento(arranjo.a, x)
    relogio.congelar(T0 + timedelta(hours=24, minutes=30))
    html = _cliente(arranjo.a).get(_detalhe(x)).content.decode()
    assert "Estamos gerando a sua cobrança" not in html
