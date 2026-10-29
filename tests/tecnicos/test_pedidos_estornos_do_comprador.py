"""E10-07: a seção "Estornos" do detalhe do pedido do comprador (acceptance A-13 e A-14)."""

from typing import Any

import pytest
from django.test import Client

from apps.financeiro.models import ObrigacaoComComprador
from tests.apoio.devolucoes import Arranjo, arranjo_da_devolucao, parcela_de_fabrica
from tests.apoio.pedidos import pedido_avulso
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

TEXTOS = {
    "solicitada": "Estorno solicitado à plataforma de pagamento",
    "falha_temporaria": "Estorno solicitado à plataforma de pagamento",
    "em_processamento": "Estorno em processamento na plataforma de pagamento",
    "falha_definitiva": "A plataforma não conseguiu devolver; o administrador fará a devolução",
    "elegivel_excepcional": "A plataforma não conseguiu devolver; o administrador fará a devolução",
    "concluida": "Estorno concluído pela plataforma de pagamento",
    "concluida_fora_da_plataforma": "Devolução feita pelo administrador por Pix ou transferência",
}


@pytest.fixture
def a(relogio: RelogioControlado, simulador_pagamentos: Any) -> Arranjo:
    return arranjo_da_devolucao(simulador_pagamentos, relogio)


def test_a_secao_lista_uma_linha_por_obrigacao_do_pedido(a: Arranjo) -> None:  # A-13
    for situacao in TEXTOS:
        parcela_de_fabrica(a, situacao, "7.00", do_pedido=True)
    c = ContaFactory.create(nome="Comprador C")
    pedido_c = pedido_avulso(c)
    ObrigacaoComComprador.objects.create(
        rodada=pedido_c.abertura.rodada,
        ciclo=pedido_c.abertura.ciclo,
        pedido=pedido_c,
        comprador=c,
        origem_tipo="teste",
        origem_id="de-c",
        motivo="duplicidade",
        produtos=1,
    )
    cliente = Client()
    cliente.force_login(a.comprador)
    resposta = cliente.get(f"/pedidos/{a.pedido.pk}/")
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Estornos" in html
    assert "Estorno registrado, aguardando processamento" in html  # a O1, ainda devida
    for texto in set(TEXTOS.values()):
        assert texto in html
    assert html.count('class="estorno"') == len(TEXTOS) + 1
    assert "Ocorrência na entrega" in html
    assert "31,25" in html
    for proibido in ("indisponivel", "evidencia", "E2E", "Pagamento em duplicidade"):
        assert proibido not in html


def test_outro_comprador_nao_ve_os_estornos(a: Arranjo) -> None:  # A-14
    c = ContaFactory.create(nome="Comprador C")
    cliente = Client()
    cliente.force_login(c)
    resposta = cliente.get(f"/pedidos/{a.pedido.pk}/")
    assert resposta.status_code == 404
    assert "Estornos" not in resposta.content.decode()
