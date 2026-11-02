"""E12-04: pagamento informado depois do cancelamento da rodada (acceptance A-1 a A-8)."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction

from apps.financeiro.models import AlertaFinanceiro, ObrigacaoComComprador, ParcelaDeDevolucao
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.provedor import NovaCobranca, obter_provedor
from apps.pedidos.models import DestinoDoPagamento, ItemDoPedido, Pedido, SituacaoDoPedido
from tests.apoio.apuracao import H, arranjo_ap, cobranca, pagar
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
ALERTA = "pagamento_depois_do_cancelamento"
PRAZO = T0 + 48 * H


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _cancelar(a: Any, **kwargs: Any) -> Any:
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    kwargs.setdefault("com_reembolso", False)
    return cancelar_rodada(a.admin, a.rodada, **kwargs)


def _receber(sim: Any) -> None:
    sim.entregar_avisos()
    processar_chamadas()


def _destino(id_externo: str) -> DestinoDoPagamento:
    return DestinoDoPagamento.objects.get(pagamento__id_externo=id_externo)


def _alertas(tipo: str = ALERTA) -> list[AlertaFinanceiro]:
    return list(AlertaFinanceiro.objects.filter(tipo=tipo).order_by("pk"))


def _composicao() -> tuple[Any, ...]:
    return (
        list(Pedido.objects.order_by("pk").values()),
        list(ItemDoPedido.objects.order_by("pk").values()),
    )


def _aprovado_depois_do_cancelamento(
    relogio: RelogioControlado, sim: Any
) -> tuple[Any, Pedido, str, tuple[Any, ...]]:
    """O arranjo do A-1: cobrança de Y criada em T0+1h, cancelamento sem reembolso em T0+3h e a
    aprovação em T0+4h, antes de o cancelamento no provedor ser processado."""
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    relogio.congelar(T0 + 3 * H)
    _cancelar(a)
    composicao = _composicao()
    relogio.congelar(T0 + 4 * H)
    sim.aprovar(id_y, em=T0 + 4 * H)
    _receber(sim)
    return a, y, id_y, composicao


def test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    a, y, id_y, composicao = _aprovado_depois_do_cancelamento(relogio, sim)
    situacao = SituacaoDoPedido.objects.get(pedido=y)
    assert (situacao.situacao, situacao.motivo_do_cancelamento, situacao.quitado_em) == (
        "cancelado",
        "cancelamento_da_rodada",
        None,
    )
    destino = _destino(id_y)
    assert (destino.destino, destino.motivo) == ("devolucao", "pedido_cancelado")
    obrigacao = ObrigacaoComComprador.objects.get(pedido=y, origem_id=str(destino.pk))
    assert obrigacao.integral == D("106.15")
    (alerta,) = _alertas()
    assert (alerta.gravidade, alerta.chave) == ("critico", id_y)
    assert alerta.dados == {
        "pagamento": id_y,
        "pedido": y.pk,
        "comprador": a.b.pk,
        "valor": "106.15",
        "aprovado_em": (T0 + 4 * H).isoformat(),
        "cancelada_em": (T0 + 3 * H).isoformat(),
    }
    assert _composicao() == composicao


def test_aprovacao_anterior_ao_cancelamento_tambem_nao_quita(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    relogio.congelar(T0 + 2 * H)
    sim.aprovar(id_y, em=T0 + 2 * H)
    relogio.congelar(T0 + 3 * H)
    _cancelar(a)
    _receber(sim)
    assert SituacaoDoPedido.objects.get(pedido=y).situacao == "cancelado"
    destino = _destino(id_y)
    assert (destino.destino, destino.motivo) == ("devolucao", "pedido_cancelado")
    assert ObrigacaoComComprador.objects.get(pedido=y, origem_id=str(destino.pk)).integral == D(
        "106.15"
    )
    assert len(_alertas()) == 1


def test_segunda_cobranca_de_pedido_pago_e_duplicidade_e_alerta(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-3
    from apps.financeiro.models import Reembolso

    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    _cancelar(a, com_reembolso=True)
    reembolso = Reembolso.objects.get(pedido=x, motivo="cancelamento_da_rodada")
    relogio.congelar(T0 + 3 * H)
    dup = obter_provedor().criar_cobranca(
        NovaCobranca("dup-x", x.referencia_externa, x.total, "Pedido", T0 + 25 * H)
    )
    sim.aprovar(dup.pagamento.id_externo, em=T0 + 3 * H)
    _receber(sim)
    destino = _destino(dup.pagamento.id_externo)
    assert (destino.destino, destino.motivo) == ("devolucao", "duplicidade")
    assert len(_alertas("duplicidade")) == 1
    assert len(_alertas()) == 1
    assert Reembolso.objects.get(pedido=x, motivo="cancelamento_da_rodada") == reembolso


def test_pagamento_no_prazo_informado_depois_da_apuracao_e_do_cancelamento(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    from apps.pedidos.apuracao import iniciar_apuracao

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    assert SituacaoDoPedido.objects.get(pedido=y).motivo_do_cancelamento == "inadimplencia"
    _cancelar(a)
    sim.aprovar(id_y, em=T0 + 47 * H)
    _receber(sim)
    destino = _destino(id_y)
    assert (destino.destino, destino.motivo) == ("devolucao", "pedido_cancelado")
    assert len(_alertas("aprovado_no_prazo_depois_da_apuracao")) == 1
    assert len(_alertas()) == 1


def test_reentregar_o_aviso_e_registrar_de_novo_nao_duplica(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    from apps.financeiro.entradas import registrar_entrada
    from apps.pagamentos.consulta import travar_pagamento

    _a, y, id_y, _ = _aprovado_depois_do_cancelamento(relogio, sim)
    sim.reemitir_aviso(id_y)
    _receber(sim)
    destino = _destino(id_y)
    with transaction.atomic():
        travar_pagamento(destino.pagamento_id)
        registrar_entrada(destino)
    assert DestinoDoPagamento.objects.filter(pagamento__id_externo=id_y).count() == 1
    assert ObrigacaoComComprador.objects.filter(pedido=y, origem_id=str(destino.pk)).count() == 1
    assert len(_alertas()) == 1


def test_alerta_resolvido_nao_reabre(relogio: RelogioControlado, sim: Any) -> None:  # A-6
    from apps.financeiro.alertas import resolver_alerta

    _a, _y, id_y, _ = _aprovado_depois_do_cancelamento(relogio, sim)
    with transaction.atomic():
        resolver_alerta(ALERTA, id_y, motivo="conferido")
    sim.reemitir_aviso(id_y)
    _receber(sim)
    (alerta,) = _alertas()
    assert alerta.resolvido_em is not None


def test_a_tarefa_do_cancelamento_nao_autoriza_a_devolucao_do_destino(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    from apps.pedidos.cancelamento_da_rodada import autorizar_devolucoes_do_cancelamento_agora

    _a, y, id_y, _ = _aprovado_depois_do_cancelamento(relogio, sim)
    autorizar_devolucoes_do_cancelamento_agora()
    destino = _destino(id_y)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=y, origem_id=str(destino.pk))
    assert not ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).exists()


def test_rodada_nao_cancelada_quita_como_antes(relogio: RelogioControlado, sim: Any) -> None:
    # A-8 (regressão)
    _a, _x, y = arranjo_ap(relogio)
    id_y = pagar(relogio, sim, y)
    assert SituacaoDoPedido.objects.get(pedido=y).situacao == "pago"
    assert _destino(id_y).destino == "quita"
    assert _alertas() == []
