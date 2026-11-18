"""Cenários 17 e 25 (E16-07, regra 5: caracterização contra o simulador).

A matriz de rastreabilidade não tinha teste que enviasse o webhook repetido (cenário 17) nem um com
aprovação em `T0 + 30h` e notificação depois de `T0 + 48h` (cenário 25). Os comportamentos já
existem; estes testes os caracterizam, e por isso passam na primeira execução.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest

from apps.financeiro.devolucoes import autorizar_devolucao
from apps.financeiro.models import ObrigacaoComComprador, ParcelaDeDevolucao
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import AvisoRecebido, PagamentoNoProvedor
from apps.pedidos.models import DestinoDoPagamento, Pedido, SituacaoDoPedido
from apps.simulador_pagamentos.models import EstornoSimulado
from tests.apoio.pedidos import T0, Arranjo, pedido_aberto, tentativa_criada
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

H = timedelta(hours=1)
REPETICOES = 5


@dataclass
class Cenario:
    arranjo: Arranjo
    x: Pedido
    sim: Any
    p: str


@pytest.fixture
def cenario(relogio: RelogioControlado, simulador_pagamentos: Any) -> Cenario:
    arranjo, x = pedido_aberto(relogio)
    tentativa = tentativa_criada(x)
    assert tentativa.id_externo is not None
    return Cenario(arranjo, x, simulador_pagamentos, tentativa.id_externo)


def _aprovar_e_receber(c: Cenario, relogio: RelogioControlado, quando: Any, chega: Any) -> None:
    """O provedor aprova em `quando`; o webhook chega em `chega`, repetido `REPETICOES` vezes."""
    relogio.congelar(chega)
    c.sim.aprovar(c.p, em=quando)
    c.sim.entregar_avisos(vezes=REPETICOES)
    processar_chamadas()


def test_cenario_17_webhook_repetido_nao_duplica_pagamento_pedido_e_mensagem(
    cenario: Cenario, relogio: RelogioControlado
) -> None:
    c = cenario
    _aprovar_e_receber(c, relogio, T0 + 2 * H, T0 + 2 * H + timedelta(minutes=1))
    assert AvisoRecebido.objects.count() == 1
    assert PagamentoNoProvedor.objects.filter(id_externo=c.p).count() == 1
    assert DestinoDoPagamento.objects.filter(pagamento__id_externo=c.p).count() == 1
    assert SituacaoDoPedido.objects.get(pedido=c.x).situacao == "pago"
    assert EntradaAuditoria.objects.filter(acao="pedido.quitar").count() == 1
    avisos = Notificacao.objects.filter(conta=c.arranjo.a, evento="pagamento_confirmado")
    assert avisos.count() == 1


def test_cenario_17_webhook_repetido_nao_duplica_estorno(
    cenario: Cenario, relogio: RelogioControlado
) -> None:
    c = cenario
    _aprovar_e_receber(c, relogio, T0 + 49 * H, T0 + 50 * H)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=c.x)
    autorizar_devolucao(obrigacao, autor=c.arranjo.admin)
    processar_chamadas()
    c.sim.reemitir_aviso(c.p)
    c.sim.entregar_avisos(vezes=REPETICOES)
    processar_chamadas()
    assert ObrigacaoComComprador.objects.filter(pedido=c.x).count() == 1
    assert ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).count() == 1
    assert EstornoSimulado.objects.filter(situacao="concluido").count() == 1


def test_cenario_25_aprovado_em_30h_e_avisado_depois_de_48h_quita_o_pedido(
    cenario: Cenario, relogio: RelogioControlado
) -> None:
    c = cenario
    _aprovar_e_receber(c, relogio, T0 + 30 * H, T0 + 50 * H)
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=c.p)
    assert (destino.destino, destino.motivo, destino.pedido) == ("quita", "", c.x)
    situacao = SituacaoDoPedido.objects.get(pedido=c.x)
    assert (situacao.situacao, situacao.quitado_em) == ("pago", T0 + 30 * H)
    assert PagamentoNoProvedor.objects.get(id_externo=c.p).primeiro_aviso_em == T0 + 50 * H
    assert not ObrigacaoComComprador.objects.filter(pedido=c.x).exists()
