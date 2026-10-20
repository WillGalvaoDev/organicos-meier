"""E08-02: tela e rota da abertura do pagamento (acceptance A-12, A-18 e A-19)."""

import re
from typing import Any

import pytest
from django.test import Client
from django.urls import resolve, reverse

from apps.contas.permissoes import Politica, politica_da_view, rotas_sem_politica
from apps.pedidos.models import ItemDoPedido, Pedido
from apps.rodadas.models import Etapa, Rodada
from tests.apoio.admin_fluxos import administrador_logado
from tests.apoio.pedidos import T0, Arranjo, abrir, montar_arranjo
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

ROTAS_DE_PEDIDOS_PERMITIDAS = {
    "pedidos_lista",
    "pedidos_detalhe",
    "pedidos_pagar",
    "rodadas_pagamento_abrir",
}


@pytest.fixture
def admin_client(client: Client, webauthn: Any, relogio: RelogioControlado) -> Client:
    relogio.congelar(T0)
    administrador_logado(client)
    return client


@pytest.fixture
def arranjo(admin_client: Client) -> Arranjo:
    return montar_arranjo()


def estoque_url(arranjo: Arranjo) -> str:
    return f"/administracao/rodadas/{arranjo.rodada.pk}/estoque/"


def abrir_url(arranjo: Arranjo) -> str:
    return f"/administracao/rodadas/{arranjo.rodada.pk}/pagamento/abrir/"


def _etapa(arranjo: Arranjo) -> str:
    return str(Rodada.objects.get(pk=arranjo.rodada.pk).etapa)


def test_o_bloco_oferece_o_formulario_do_frete(admin_client: Client, arranjo: Arranjo) -> None:
    # A-18 (parte 1)
    html = admin_client.get(estoque_url(arranjo)).content.decode()
    assert f'action="{abrir_url(arranjo)}"' in html
    assert "Frete total (R$)" in html
    assert "Abrir pagamento" in html


def test_abrir_pelo_formulario_redireciona_com_o_prazo(
    admin_client: Client, arranjo: Arranjo
) -> None:  # A-18 (parte 2)
    resposta = admin_client.post(abrir_url(arranjo), {"frete": "22,00"}, follow=True)
    assert resposta.redirect_chain, resposta.status_code
    assert resposta.redirect_chain[-1][0] == estoque_url(arranjo)
    html = resposta.content.decode()
    assert "Pagamento aberto. Prazo: 03/11/2026 às 10:00 (horário de Brasília)." in html
    assert _etapa(arranjo) == Etapa.PAGAMENTO
    assert Pedido.objects.count() == 2


@pytest.mark.parametrize("frete", ["abc", "22,001", "", "-1", "22,00,00"])
def test_frete_invalido_volta_com_o_erro_do_campo(
    admin_client: Client, arranjo: Arranjo, frete: str
) -> None:  # A-18 (parte 3)
    resposta = admin_client.post(abrir_url(arranjo), {"frete": frete})
    assert resposta.status_code == 400
    assert (
        "Informe o frete em reais, com até duas casas decimais, por exemplo 40,00."
        in resposta.content.decode()
    )
    assert _etapa(arranjo) == Etapa.FECHAMENTO_ENCERRADO
    assert Pedido.objects.count() == 0


def test_em_pagamento_mostra_t0_prazo_e_margem_sem_formulario(
    admin_client: Client, arranjo: Arranjo
) -> None:  # A-18 (parte 4)
    abrir(arranjo)
    html = admin_client.get(estoque_url(arranjo)).content.decode()
    assert "02/11/2026 10:00" in html  # T0 em Brasília
    assert "03/11/2026 10:00" in html  # fim do prazo de pagamento
    assert "04/11/2026 10:00" in html  # fim da margem
    assert abrir_url(arranjo) not in html
    assert "Frete total (R$)" not in html


def test_retorno_por_minimo_redireciona_com_o_aviso(
    admin_client: Client, arranjo: Arranjo
) -> None:  # A-18, A-7
    from apps.catalogo.servicos import editar_produto
    from tests.apoio.pedidos import administrador

    editar_produto(administrador(), arranjo.p1, preco="1.00")
    resposta = admin_client.post(abrir_url(arranjo), {"frete": "22,00"}, follow=True)
    assert (
        "O mínimo não foi atingido na abertura do pagamento. "
        "A rodada voltou para a fase de interesse."
    ) in resposta.content.decode()
    assert _etapa(arranjo) == Etapa.INTERESSE


@pytest.mark.parametrize("etapa", [Etapa.INTERESSE, Etapa.FECHAMENTO, Etapa.PAGAMENTO])
def test_transicao_recusada_responde_409(
    admin_client: Client, arranjo: Arranjo, etapa: str
) -> None:  # A-9 (tela)
    Rodada.objects.filter(pk=arranjo.rodada.pk).update(etapa=etapa)
    resposta = admin_client.post(abrir_url(arranjo), {"frete": "22,00"})
    assert resposta.status_code == 409
    assert (
        "Só uma rodada com o fechamento encerrado pode abrir o pagamento."
        in resposta.content.decode()
    )
    assert Pedido.objects.count() == 0


def test_rota_so_aceita_post(admin_client: Client, arranjo: Arranjo) -> None:  # A-19
    assert admin_client.get(abrir_url(arranjo)).status_code == 405
    assert Pedido.objects.count() == 0


def test_comprador_fornecedor_e_anonimo_sao_recusados(arranjo: Arranjo) -> None:  # A-19
    fornecedor = ContaFactory.create(fornecedor=True)
    for conta in (arranjo.a, fornecedor, None):
        cliente = Client()
        if conta is not None:
            cliente.force_login(conta)
        resposta = cliente.post(abrir_url(arranjo), {"frete": "22,00"})
        assert resposta.status_code in (302, 403)
        if resposta.status_code == 302:
            assert "/entrar/" in resposta["Location"] or "/seguranca/" in resposta["Location"]
    assert _etapa(arranjo) == Etapa.FECHAMENTO_ENCERRADO
    assert Pedido.objects.count() == 0


def test_a_rota_declara_a_politica_de_administrador(arranjo: Arranjo) -> None:  # A-19
    assert rotas_sem_politica() == []
    chamada = resolve(abrir_url(arranjo))
    assert chamada.url_name == "rodadas_pagamento_abrir"
    assert politica_da_view(chamada.func) == Politica.ADMINISTRADOR
    assert reverse("rodadas_pagamento_abrir", kwargs={"pk": arranjo.rodada.pk}) == abrir_url(
        arranjo
    )


def _nomes_de_rotas() -> list[tuple[str, str | None]]:
    from django.urls import get_resolver

    from apps.contas.permissoes import _rotas

    return [(c, n) for c, n, _ in _rotas(get_resolver().url_patterns)]


@pytest.mark.acceptance
def test_nenhuma_rota_altera_pedido_item_t0_ou_frete(arranjo: Arranjo) -> None:
    # A-12, cenário 47
    assert rotas_sem_politica() == []
    suspeitas = [
        (caminho, nome)
        for caminho, nome in _nomes_de_rotas()
        if re.search(r"pedido|item|t0|frete", f"{caminho} {nome}", re.IGNORECASE)
        and nome not in ROTAS_DE_PEDIDOS_PERMITIDAS
    ]
    assert suspeitas == []


@pytest.mark.acceptance
def test_interesse_depois_da_abertura_e_recusado_com_409(
    arranjo: Arranjo, admin_client: Client
) -> None:  # A-12, cenário 47
    abrir(arranjo)
    antes = (
        list(Pedido.objects.order_by("pk").values()),
        list(ItemDoPedido.objects.order_by("pk").values()),
    )
    assert antes[0]
    cliente = Client()
    cliente.force_login(arranjo.a)
    for quantidade in ("7", "5"):  # aumenta e reduz o interesse de A em P1
        resposta = cliente.post(
            "/interesses/", {"produto": arranjo.p1.pk, "quantidade": quantidade}
        )
        assert resposta.status_code == 409
        assert (
            "Os interesses deste fornecedor não podem ser alterados nesta etapa."
            in resposta.content.decode()
        )
    resposta = admin_client.post("/interesses/", {"produto": arranjo.p1.pk, "quantidade": "7"})
    assert resposta.status_code in (302, 403)  # o administrador nem tem interesses
    assert (
        list(Pedido.objects.order_by("pk").values()),
        list(ItemDoPedido.objects.order_by("pk").values()),
    ) == antes
