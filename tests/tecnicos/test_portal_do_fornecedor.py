"""E13-07: o portal do fornecedor, consultas com lista fechada de campos (acceptance A-1 a A-18)."""

import csv
import io
import re
from datetime import date
from typing import Any

import pytest
from django.conf import settings
from django.test import Client

from tests.apoio.pedido_formal import arranjo_af
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = pytest.mark.django_db

PAINEL_FORNECEDOR = {"nome"}
PAINEL_PRODUTO = {"nome", "unidade", "preco_unitario", "multiplo"}
PAINEL_RODADA = {"numero", "etapa", "aberta_em"}
RODADA = {"etapa", "progresso_percentual"}
RODADA_PRODUTO = {
    "nome",
    "unidade",
    "preco_unitario",
    "total_em_interesse",
    "caixas_completas",
    "faltam_para_proxima_caixa",
    "excedente",
    "valor_total",
}
CABECALHO = "produto;unidade;quantidade;multiplo;caixas;preco_unitario;valor_total"


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _texto(resposta: Any) -> str:
    html = resposta.content.decode()
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _conta_do_fornecedor(a: Any) -> Any:
    return ContaFactory.create(nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk)


def _af(relogio: RelogioControlado, sim: Any, **opcoes: Any) -> tuple[Any, Any, Any, Any, Any]:
    a, x, y, pedido = arranjo_af(relogio, sim, **opcoes)
    return a, x, y, pedido, _conta_do_fornecedor(a)


def _g() -> Any:
    """O segundo fornecedor G, com um produto Q e uma rodada em interesse."""
    g = FornecedorFactory.create(nome="G")
    rodada = RodadaFactory.create(fornecedor=g, etapa="interesse")
    q = ProdutoFactory.create(fornecedor=g, nome="Q")
    EstoqueDaRodadaFactory.create(rodada=rodada, produto=q, limite=None)
    return rodada


def _em_interesse(relogio: RelogioControlado) -> tuple[Any, Any]:
    """Uma rodada de F em `interesse` com as parcelas do AP, antes da abertura do pagamento."""
    from apps.rodadas.models import Rodada
    from tests.apoio.pedidos import montar_arranjo

    relogio.congelar(T0)
    a = montar_arranjo(minimo="50.00")
    Rodada.objects.filter(pk=a.rodada.pk).update(etapa="interesse")
    return a, _conta_do_fornecedor(a)


def test_o_painel_do_fornecedor(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    a, _x, _y, _pedido, conta = _af(relogio, sim)
    _g()
    client.force_login(conta)
    resposta = client.get("/fornecedor/")
    assert resposta.status_code == 200
    texto = _texto(resposta)
    assert "F" in texto
    assert "P1" in texto
    assert "P2" in texto
    assert "R$ 10,00" in texto
    assert "R$ 5,00" in texto
    assert "Aguardando fornecedor" in texto
    assert f"Rodada {a.rodada.pk}" in texto
    assert not re.search(r"Q", texto)


def test_as_chaves_do_painel(relogio: RelogioControlado, sim: Any) -> None:  # A-2
    from apps.fornecedores.portal import dados_do_painel

    a, _x, _y, _pedido, _conta = _af(relogio, sim)
    dados = dados_do_painel(a.fornecedor)
    assert set(dados["fornecedor"]) == PAINEL_FORNECEDOR
    assert all(set(p) == PAINEL_PRODUTO for p in dados["produtos"])
    assert all(set(r) == PAINEL_RODADA for r in dados["rodadas"])
    assert set(dados) == {"fornecedor", "produtos", "rodadas"}


def test_a_rodada_em_interesse_mostra_o_progresso_agregado(
    client: Client, relogio: RelogioControlado
) -> None:  # A-3
    a, conta = _em_interesse(relogio)
    client.force_login(conta)
    resposta = client.get(f"/fornecedor/rodadas/{a.rodada.pk}/")
    assert resposta.status_code == 200
    texto = _texto(resposta)
    assert "Interesse" in texto
    assert "R$ 110,00" in texto  # P1: 11 a R$ 10,00
    assert "R$ 60,00" in texto  # P2: 12 a R$ 5,00
    assert "Faltam para a próxima caixa" in texto
    assert "Comprador" not in texto
    assert "R$ 50,00" not in texto  # o mínimo em valor não é do fornecedor


def test_as_chaves_da_rodada_em_interesse(relogio: RelogioControlado) -> None:  # A-4
    from apps.fornecedores.portal import dados_da_rodada
    from apps.rodadas.models import Rodada

    a, _conta = _em_interesse(relogio)
    dados = dados_da_rodada(Rodada.objects.get(pk=a.rodada.pk))
    assert set(dados["rodada"]) == RODADA
    assert all(set(p) == RODADA_PRODUTO for p in dados["produtos"])
    p2 = next(p for p in dados["produtos"] if p["nome"] == "P2")
    assert (p2["total_em_interesse"], p2["caixas_completas"]) == (12, 2)
    assert (p2["faltam_para_proxima_caixa"], p2["excedente"]) == (6, 0)  # o valor da E05: 6 − (12 % 6)


def test_em_pagamento_so_o_andamento(client: Client, relogio: RelogioControlado) -> None:  # A-5
    from tests.apoio.apuracao import arranjo_ap

    a, _x, _y = arranjo_ap(relogio)
    client.force_login(_conta_do_fornecedor(a))
    texto = _texto(client.get(f"/fornecedor/rodadas/{a.rodada.pk}/"))
    assert "Pagamento" in texto
    assert "As quantidades finais serão informadas no pedido formal, depois da apuração." in texto
    for proibido in ("94,35", "106,15", "Comprador", "11 unidade", "R$ 110,00"):
        assert proibido not in texto


def test_o_pedido_formal_e_a_previsao_para_o_fornecedor(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    a, _x, _y, pedido, conta = _af(relogio, sim)
    client.force_login(conta)
    texto = _texto(client.get(f"/fornecedor/rodadas/{a.rodada.pk}/"))
    assert f"Pedido formal nº {pedido.pk}" in texto
    assert "Emitido em 04/11/2026 10:00" in texto
    assert "P1" in texto
    assert "R$ 110,00" in texto
    assert "P2" in texto
    assert "R$ 60,00" in texto
    assert "Total dos produtos: R$ 170,00" in texto
    assert "Previsão de entrega: 11/11/2026" in texto
    for proibido in ("Tentativa", "pedidos@f.example", "Frete", "serviço", "Repasse"):
        assert proibido not in texto


def test_a_previsao_ajustada(client: Client, relogio: RelogioControlado, sim: Any) -> None:  # A-7
    from apps.pedidos.previsao_de_entrega import ajustar_previsao_de_entrega

    a, _x, _y, _pedido, conta = _af(relogio, sim)
    ajustar_previsao_de_entrega(a.admin, a.rodada, date(2026, 11, 14))
    client.force_login(conta)
    texto = _texto(client.get(f"/fornecedor/rodadas/{a.rodada.pk}/"))
    assert "Previsão de entrega: 14/11/2026" in texto


def test_rodada_cancelada_mostra_o_pedido_formal_sem_previsao(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    a, _x, _y, pedido, conta = _af(relogio, sim)
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    client.force_login(conta)
    texto = _texto(client.get(f"/fornecedor/rodadas/{a.rodada.pk}/"))
    assert "Cancelada" in texto
    assert f"Pedido formal nº {pedido.pk}" in texto
    assert "Previsão de entrega" not in texto


def test_a_exportacao_do_pedido_formal(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    a, _x, _y, pedido, conta = _af(relogio, sim)
    client.force_login(conta)
    resposta = client.get(f"/fornecedor/rodadas/{a.rodada.pk}/pedido-formal.csv")
    assert resposta.status_code == 200
    assert resposta["Content-Type"].startswith("text/csv")
    assert "utf-8" in resposta["Content-Type"].lower()
    assert f"pedido-formal-{pedido.pk}.csv" in resposta["Content-Disposition"]
    linhas = resposta.content.decode().splitlines()
    assert linhas == [
        CABECALHO,
        "P1;unidade;11;;;10,00;110,00",
        "P2;unidade;12;6;2;5,00;60,00",
    ]
    assert len(next(iter(csv.reader(io.StringIO(resposta.content.decode()), delimiter=";")))) == 7


def test_sem_pedido_formal_a_exportacao_da_404(
    client: Client, relogio: RelogioControlado
) -> None:  # A-10
    from tests.apoio.apuracao import arranjo_ap

    a, _x, _y = arranjo_ap(relogio)
    client.force_login(_conta_do_fornecedor(a))
    assert client.get(f"/fornecedor/rodadas/{a.rodada.pk}/pedido-formal.csv").status_code == 404


def test_rodada_de_outro_fornecedor_ou_inexistente_da_o_mesmo_404(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-11
    a, _x, _y, _pedido, conta = _af(relogio, sim)
    de_g = _g()
    client.force_login(conta)
    respostas = [
        client.get(f"/fornecedor/rodadas/{de_g.pk}/"),
        client.get(f"/fornecedor/rodadas/{de_g.pk}/pedido-formal.csv"),
        client.get("/fornecedor/rodadas/999999/"),
    ]
    assert [r.status_code for r in respostas] == [404, 404, 404]
    assert len({r.content for r in respostas}) == 1
    assert a.rodada.pk


def test_o_fornecedor_nao_alcanca_o_que_nao_e_dele(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    a, x, _y, _pedido, conta = _af(relogio, sim)
    client.force_login(conta)
    recusas = [
        client.get(f"/pedidos/{x.pk}/"),
        client.post(f"/pedidos/{x.pk}/pagar/"),
        client.get("/administracao/financeiro/"),
        client.get("/administracao/financeiro/reserva/"),
        client.get("/administracao/financeiro/movimentos/"),
        client.get("/administracao/financeiro/devolucoes/1/"),
        client.get("/administracao/usuarios/"),
        client.get(f"/administracao/rodadas/{a.rodada.pk}/pedido-formal/"),
        client.get(f"/administracao/rodadas/{a.rodada.pk}/saidas/"),
    ]
    assert [r.status_code for r in recusas] == [403] * 9
    for resposta in recusas:
        texto = resposta.content.decode()
        assert "Comprador A" not in texto
        assert "8,50" not in texto


def test_o_fornecedor_nao_compra(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-13
    a, _x, _y, _pedido, conta = _af(relogio, sim)
    client.force_login(conta)
    recusas = [
        client.get("/carrinho/"),
        client.post("/interesses/"),
        client.get("/catalogo/"),
        client.get(f"/catalogo/{a.fornecedor.pk}/"),
    ]
    assert [r.status_code for r in recusas] == [403] * 4


def test_o_comprador_nao_entra_no_portal(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-14
    a, _x, _y, _pedido, _conta = _af(relogio, sim)
    client.force_login(a.a)
    recusas = [
        client.get("/fornecedor/"),
        client.get(f"/fornecedor/rodadas/{a.rodada.pk}/"),
        client.get(f"/fornecedor/rodadas/{a.rodada.pk}/pedido-formal.csv"),
    ]
    assert [r.status_code for r in recusas] == [403] * 3


def test_administrador_e_anonimo_nao_entram_no_portal(
    client: Client, relogio: RelogioControlado, sim: Any, webauthn: Any
) -> None:  # A-15
    from tests.apoio.admin_fluxos import administrador_com_passkey
    from tests.apoio.devolucoes import entrar_de_novo

    relogio.congelar(T0)
    _conta, credencial = administrador_com_passkey(client)
    a, _x, _y, _pedido, _conta_f = _af(relogio, sim)
    anonimo = client.get("/fornecedor/")
    assert anonimo.status_code == 302
    assert settings.LOGIN_URL in anonimo["Location"]
    entrar_de_novo(client, credencial, a.admin)
    assert client.get("/fornecedor/").status_code == 403


def test_nenhuma_resposta_do_fornecedor_traz_dado_de_comprador_ou_cobranca(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-16
    a, x, y, _pedido, conta = _af(relogio, sim)
    client.force_login(conta)
    respostas = [
        client.get("/fornecedor/"),
        client.get(f"/fornecedor/rodadas/{a.rodada.pk}/"),
        client.get(f"/fornecedor/rodadas/{a.rodada.pk}/pedido-formal.csv"),
    ]
    for resposta in respostas:
        corpo = resposta.content.decode()
        for proibido in (
            a.a.nome,
            a.a.email_normalizado,
            a.b.nome,
            a.b.email_normalizado,
            "R$ 8,50",
            "R$ 22,00",
            f"/pedidos/{x.pk}/",
            f"/pedidos/{y.pk}/",
        ):
            assert proibido not in corpo, proibido


def test_o_link_na_pagina_inicial(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-17
    a, _x, _y, _pedido, conta = _af(relogio, sim)
    client.force_login(conta)
    resposta = client.get("/inicio/")
    assert 'href="/fornecedor/"' in resposta.content.decode()
    assert "Minhas rodadas" in _texto(resposta)
    client.force_login(a.a)
    assert "Minhas rodadas" not in _texto(client.get("/inicio/"))


def test_o_fornecedor_nao_escreve(
    client: Client, relogio: RelogioControlado, sim: Any
) -> None:  # A-18
    a, _x, _y, _pedido, conta = _af(relogio, sim)
    client.force_login(conta)
    rotas = [
        "/fornecedor/",
        f"/fornecedor/rodadas/{a.rodada.pk}/",
        f"/fornecedor/rodadas/{a.rodada.pk}/pedido-formal.csv",
    ]
    assert [client.post(rota).status_code for rota in rotas] == [405] * 3
