"""E08-07: tela do simulador de pagamentos (acceptance A-1 a A-7; A-8 em
`test_pagamentos_fronteiras.py`)."""

import re
from dataclasses import dataclass
from typing import Any

import pytest
from django.test import Client
from django.urls import resolve

from apps.contas.permissoes import Politica, politica_da_view, rotas_sem_politica
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.chamadas import processar_chamadas
from apps.pedidos.models import Pedido, SituacaoDoPedido
from apps.simulador_pagamentos.models import AvisoSimulado, CobrancaSimulada
from tests.apoio.admin_fluxos import administrador_logado
from tests.apoio.pedidos import (
    T0,
    Arranjo,
    pedido_aberto,
    pedido_avulso,
    pedido_de,
    tentativa_criada,
)
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

BASE = "/administracao/simulador-pagamentos/"


@dataclass
class Cenario:
    arranjo: Arranjo
    x: Pedido
    p: str  # cobrança pendente do pedido X
    q: str  # cobrança já aprovada (do pedido Y)
    sim: Any
    cliente: Client


@pytest.fixture
def cenario(
    client: Client, webauthn: Any, relogio: RelogioControlado, simulador_pagamentos: Any
) -> Cenario:
    relogio.congelar(T0)
    administrador_logado(client)
    arranjo, x = pedido_aberto(relogio)
    p = tentativa_criada(x).id_externo
    q = tentativa_criada(pedido_de(arranjo.b)).id_externo
    assert p is not None
    assert q is not None
    simulador_pagamentos.aprovar(q)
    return Cenario(arranjo, x, p, q, simulador_pagamentos, client)


def _linha(html: str, id_externo: str) -> str:
    for linha in re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL):
        if f">{id_externo}<" in linha:
            return str(linha)
    raise AssertionError(f"sem linha para {id_externo}")


def _situacao(id_externo: str) -> str:
    return CobrancaSimulada.objects.get(pk=int(id_externo.removeprefix("sim-"))).situacao


def test_a_lista_mostra_as_cobrancas_e_os_botoes(cenario: Cenario) -> None:  # A-1
    c = cenario
    resposta = c.cliente.get(BASE)
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Simulador de pagamentos" in html
    assert "Ambiente de teste. Nenhum dinheiro real é movimentado." in html
    linha_p = _linha(html, c.p)
    assert c.x.referencia_externa in linha_p
    assert "R$ 94,35" in linha_p
    assert "Pendente" in linha_p
    assert "02/11/2026 11:00" in linha_p  # criada às 14:00 UTC
    assert "03/11/2026 10:00" in linha_p  # vence em T0 + 24h
    for acao in ("aprovar", "recusar", "expirar"):
        assert f'action="{BASE}{c.p}/{acao}/"' in linha_p
    linha_q = _linha(html, c.q)
    assert "Aprovada" in linha_q
    assert "02/11/2026 11:00" in linha_q
    assert "<form" not in linha_q
    assert "Entregar avisos pendentes (1)" in html


def test_aprovar_e_entregar_quita_o_pedido(cenario: Cenario) -> None:  # A-2
    c = cenario
    resposta = c.cliente.post(f"{BASE}{c.p}/aprovar/", follow=True)
    assert resposta.redirect_chain[-1][0] == BASE
    assert f"Cobrança {c.p} aprovada." in resposta.content.decode()
    resposta = c.cliente.post(f"{BASE}avisos/entregar/", follow=True)
    assert "2 aviso(s) entregue(s)." in resposta.content.decode()
    processar_chamadas()
    assert SituacaoDoPedido.objects.get(pedido=c.x).situacao == "pago"
    (aprovou,) = EntradaAuditoria.objects.filter(acao="simulador.aprovar")
    assert aprovou.alteracoes == {"id_externo": c.p}
    assert aprovou.autor_id == str(c.arranjo.admin.pk)
    (entregou,) = EntradaAuditoria.objects.filter(acao="simulador.entregar_avisos")
    assert entregou.alteracoes == {"avisos": 2}


def test_recusar_e_expirar(cenario: Cenario) -> None:  # A-3
    c = cenario
    r = tentativa_criada(pedido_avulso(ContaFactory.create(), "G", "50.00")).id_externo
    e = tentativa_criada(pedido_avulso(ContaFactory.create(), "H", "60.00")).id_externo
    assert r is not None
    assert e is not None
    antes = AvisoSimulado.objects.count()
    resposta = c.cliente.post(f"{BASE}{r}/recusar/", follow=True)
    assert f"Cobrança {r} recusada." in resposta.content.decode()
    resposta = c.cliente.post(f"{BASE}{e}/expirar/", follow=True)
    assert f"Cobrança {e} expirada." in resposta.content.decode()
    assert (_situacao(r), _situacao(e)) == ("recusado", "expirado")
    assert AvisoSimulado.objects.count() == antes + 2
    assert EntradaAuditoria.objects.filter(acao="simulador.recusar").count() == 1
    assert EntradaAuditoria.objects.filter(acao="simulador.expirar").count() == 1


def test_acao_que_a_situacao_nao_permite_responde_409(cenario: Cenario) -> None:  # A-4
    c = cenario
    avisos = AvisoSimulado.objects.count()
    for acao, texto in (("recusar", "recusada"), ("expirar", "expirada")):
        resposta = c.cliente.post(f"{BASE}{c.q}/{acao}/")
        assert resposta.status_code == 409
        assert (
            f"A cobrança {c.q} não pode ser {texto} na situação atual." in resposta.content.decode()
        )
    assert _situacao(c.q) == "aprovado"
    assert AvisoSimulado.objects.count() == avisos
    assert not EntradaAuditoria.objects.filter(acao__in=("simulador.recusar",)).exists()


def test_desconhecida_e_metodo_errado(cenario: Cenario) -> None:  # A-5
    c = cenario
    assert c.cliente.post(f"{BASE}sim-999/aprovar/").status_code == 404
    assert c.cliente.get(f"{BASE}{c.p}/aprovar/").status_code == 405
    assert _situacao(c.p) == "pendente"


def test_outros_papeis_e_anonimos_sao_recusados(cenario: Cenario) -> None:  # A-6
    c = cenario
    fornecedor = ContaFactory.create(fornecedor=True)
    alvos = [
        ("get", BASE),
        ("post", f"{BASE}{c.p}/aprovar/"),
        ("post", f"{BASE}{c.p}/recusar/"),
        ("post", f"{BASE}{c.p}/expirar/"),
        ("post", f"{BASE}avisos/entregar/"),
    ]
    for conta in (c.arranjo.a, fornecedor, None):
        cliente = Client()
        if conta is not None:
            cliente.force_login(conta)
        for metodo, caminho in alvos:
            resposta = getattr(cliente, metodo)(caminho)
            assert resposta.status_code in (302, 403), (metodo, caminho)
    assert _situacao(c.p) == "pendente"
    assert not EntradaAuditoria.objects.filter(acao__startswith="simulador.").exists()


def test_as_cinco_rotas_declaram_a_politica_de_administrador(cenario: Cenario) -> None:  # A-6
    c = cenario
    assert rotas_sem_politica() == []
    esperadas = {
        BASE: "simulador_pagamentos_lista",
        f"{BASE}{c.p}/aprovar/": "simulador_pagamentos_aprovar",
        f"{BASE}{c.p}/recusar/": "simulador_pagamentos_recusar",
        f"{BASE}{c.p}/expirar/": "simulador_pagamentos_expirar",
        f"{BASE}avisos/entregar/": "simulador_pagamentos_entregar",
    }
    for caminho, nome in esperadas.items():
        achada = resolve(caminho)
        assert achada.url_name == nome
        assert politica_da_view(achada.func) == Politica.ADMINISTRADOR, caminho


def test_sem_o_simulador_configurado_as_rotas_nao_existem(
    cenario: Cenario, settings: Any
) -> None:  # A-7, AGENTS.md §7
    c = cenario
    settings.PROVEDOR_PAGAMENTOS = "mercado_pago"
    assert c.cliente.get(BASE).status_code == 404
    assert c.cliente.post(f"{BASE}{c.p}/aprovar/").status_code == 404
    assert c.cliente.post(f"{BASE}avisos/entregar/").status_code == 404
    assert _situacao(c.p) == "pendente"
