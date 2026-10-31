"""E11-04: rodada viável, estorno proporcional e restauração na fila (acceptance A-1 a A-14)."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction

from apps.contas.moderacao import suspender
from apps.financeiro.devolucoes import situacao_da_devolucao
from apps.financeiro.devolucoes_views import GRUPO_DA_SITUACAO
from apps.financeiro.models import ItemReembolsado, ObrigacaoComComprador, Reembolso
from apps.financeiro.reserva import sem_cobertura_da_obrigacao
from apps.interesses.consultas import total_reservado
from apps.interesses.fila import alocar_pendentes
from apps.interesses.models import ParcelaDeInteresse
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pedidos.models import (
    AberturaDoPagamento,
    ItemDoPedido,
    ParcelaNoPedido,
    Pedido,
    SituacaoDePagamento,
    SituacaoDoPedido,
)
from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.pedidos import T0, pedido_de
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _iniciar(a: Any) -> Any:
    from apps.pedidos.apuracao import iniciar_apuracao

    return iniciar_apuracao(a.admin, a.rodada)


def _viavel(relogio: RelogioControlado, sim: Any, **arranjo: Any) -> tuple[Any, Any, Any, Any]:
    """AP-viável com X pago e Y sem pagamento, apurado em `T0 + 48h`."""
    a, x, y = arranjo_ap(relogio, **arranjo)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    return a, x, y, _iniciar(a)


def _parcela(comprador: Any, produto: Any) -> list[ParcelaDeInteresse]:
    return list(
        ParcelaDeInteresse.objects.filter(comprador=comprador, produto=produto).order_by(
            "sequencia"
        )
    )


def _restauracoes() -> list[Any]:
    from apps.pedidos.models import RestauracaoDeCaixa

    return list(RestauracaoDeCaixa.objects.order_by("pk"))


def _reembolsos(pedido: Pedido) -> list[Reembolso]:
    return list(Reembolso.objects.filter(pedido=pedido, motivo="caixa_invalidada").order_by("pk"))


def _nao_pagos() -> set[int]:
    return {
        s.pedido_id
        for s in SituacaoDoPedido.objects.all()
        if s.situacao != SituacaoDePagamento.PAGO
    }


def test_estorno_proporcional_das_unidades_em_caixa_invalidada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    a, x, _y, apuracao = _viavel(relogio, sim)
    item = ItemDoPedido.objects.get(pedido=x, produto=a.p2)
    (reembolso,) = _reembolsos(x)
    assert reembolso.chave == f"caixa:{apuracao.pk}:{item.pk}"
    assert (reembolso.tipo, reembolso.autor) == ("parcial", None)
    assert (reembolso.produtos, reembolso.servico, reembolso.frete) == (
        D("20.00"),
        D("1.00"),
        D("2.59"),
    )
    (linha,) = ItemReembolsado.objects.filter(reembolso=reembolso)
    assert (linha.item_id, linha.quantidade, linha.valor) == (item.pk, D("4.000"), D("20.00"))
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x)
    assert obrigacao.devido == D("23.59")
    assert sem_cobertura_da_obrigacao(obrigacao) == D("0.00")


def test_o_estorno_espera_a_autorizacao_na_lista_de_devolucoes(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    from apps.financeiro.models import ParcelaDeDevolucao

    _a, x, _y, _ = _viavel(relogio, sim)
    assert ParcelaDeDevolucao.objects.count() == 0
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x)
    assert GRUPO_DA_SITUACAO[situacao_da_devolucao(obrigacao)] == "pendentes"


def test_unidades_da_caixa_invalidada_voltam_para_a_fila(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-3
    a, x, _y, apuracao = _viavel(relogio, sim)
    antes = ParcelaNoPedido.objects.filter(item__pedido=x, item__produto=a.p2, caixa=1).get()
    (parcela,) = _parcela(a.a, a.p2)
    assert (parcela.situacao, parcela.quantidade_pendente, parcela.quantidade_reservada) == (
        "pendente",
        D("4.000"),
        D("0.000"),
    )
    (restauracao,) = _restauracoes()
    assert restauracao.apuracao_id == apuracao.pk
    assert (restauracao.parcela_no_pedido_id, restauracao.parcela_id) == (antes.pk, parcela.pk)
    assert restauracao.quantidade == D("4.000")
    (de_p1,) = _parcela(a.a, a.p1)
    assert (de_p1.situacao, de_p1.quantidade_reservada) == ("em_pedido", D("6.000"))


def test_a_fila_nao_reserva_na_rodada_apurada(relogio: RelogioControlado, sim: Any) -> None:
    # A-4
    a, _x, _y, _ = _viavel(relogio, sim)
    (antes,) = _parcela(a.a, a.p2)
    with transaction.atomic():
        assert alocar_pendentes(a.fornecedor) == D("0.000")
    assert total_reservado(a.p2) == D("0.000")
    (depois,) = _parcela(a.a, a.p2)
    assert (depois.situacao, depois.quantidade_reservada, depois.sequencia) == (
        "pendente",
        D("0.000"),
        antes.sequencia,
    )


def test_a_restauracao_nao_espera_a_autorizacao_da_devolucao(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    from apps.financeiro.models import ParcelaDeDevolucao

    a, _x, _y, _ = _viavel(relogio, sim)
    assert ParcelaDeDevolucao.objects.count() == 0
    (parcela,) = _parcela(a.a, a.p2)
    assert parcela.situacao == "pendente"


def test_o_pedido_congelado_nao_muda(relogio: RelogioControlado, sim: Any) -> None:  # A-6
    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    antes = (
        list(Pedido.objects.order_by("pk").values()),
        list(ItemDoPedido.objects.order_by("pk").values()),
        list(ParcelaNoPedido.objects.order_by("pk").values()),
    )
    _iniciar(a)
    depois = (
        list(Pedido.objects.order_by("pk").values()),
        list(ItemDoPedido.objects.order_by("pk").values()),
        list(ParcelaNoPedido.objects.order_by("pk").values()),
    )
    assert depois == antes


def test_so_a_parte_da_caixa_invalidada_e_estornada_e_restaurada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    a, x, _y = arranjo_ap(relogio, parcelas_de_p2=(("a", 4), ("c", 2), ("a", 2), ("b", 4)))
    assert a.c is not None
    z = pedido_de(a.c)
    pagar(relogio, sim, x)
    pagar(relogio, sim, z)
    relogio.congelar(PRAZO)
    _iniciar(a)
    (reembolso,) = _reembolsos(x)
    (linha,) = ItemReembolsado.objects.filter(reembolso=reembolso)
    assert linha.quantidade == D("2.000")
    primeira, segunda = _parcela(a.a, a.p2)
    assert (primeira.situacao, primeira.quantidade_reservada) == ("em_pedido", D("4.000"))
    assert (segunda.situacao, segunda.quantidade_pendente, segunda.quantidade_reservada) == (
        "pendente",
        D("2.000"),
        D("0.000"),
    )
    assert _reembolsos(z) == []
    assert [r.parcela_id for r in _restauracoes()] == [segunda.pk]


def test_parcela_que_cruza_as_caixas_fica_pendente_so_com_a_parte_invalidada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    a, x, _y = arranjo_ap(relogio, parcelas_de_p2=(("c", 4), ("a", 4), ("b", 4)))
    assert a.c is not None
    z = pedido_de(a.c)
    pagar(relogio, sim, x)
    pagar(relogio, sim, z)
    relogio.congelar(PRAZO)
    _iniciar(a)
    (parcela,) = _parcela(a.a, a.p2)
    assert (parcela.situacao, parcela.quantidade_pendente, parcela.quantidade_reservada) == (
        "pendente",
        D("2.000"),
        D("0.000"),
    )
    assert parcela.quantidade_reservada + parcela.quantidade_pendente <= parcela.quantidade_original
    (restauracao,) = _restauracoes()
    assert (restauracao.parcela_id, restauracao.quantidade) == (parcela.pk, D("2.000"))
    assert ParcelaNoPedido.objects.filter(parcela=parcela, caixa=1).get().quantidade == D("2.000")


def test_repetir_o_passo_nao_restaura_nem_estorna_de_novo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    from apps.pedidos import apuracao as modulo

    a, x, _y, apuracao = _viavel(relogio, sim)
    abertura = AberturaDoPagamento.objects.get()
    calculo = modulo._calcular_o_resultado(abertura, _nao_pagos())
    (antes,) = _parcela(a.a, a.p2)
    with transaction.atomic():
        modulo._estornar_e_restaurar(apuracao, calculo)
    assert len(_restauracoes()) == 1
    (depois,) = _parcela(a.a, a.p2)
    assert (depois.quantidade_pendente, depois.sequencia) == (D("4.000"), antes.sequencia)
    assert len(_reembolsos(x)) == 1
    assert ObrigacaoComComprador.objects.filter(pedido=x).count() == 1


def test_comprador_suspenso_tem_o_estorno_mas_nao_a_restauracao(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-10
    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    suspender(a.admin, a.a)
    relogio.congelar(PRAZO)
    _iniciar(a)
    (reembolso,) = _reembolsos(x)
    assert reembolso.produtos + reembolso.servico + reembolso.frete == D("23.59")
    assert _restauracoes() == []
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.apuracao_final")
    (do_pedido,) = [p for p in auditoria.alteracoes["pedidos"] if p["pedido"] == x.pk]
    (nao,) = do_pedido["nao_restauradas"]
    assert nao["motivo"] == "conta_suspensa"
    assert do_pedido["restauracoes"] == []


def test_aviso_de_caixa_incompleta_ao_comprador_afetado(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-11
    a, x, _y, apuracao = _viavel(relogio, sim)
    avisos = list(
        Notificacao.objects.filter(conta=a.a, evento="itens_cancelados", chave__contains="caixa")
    )
    (aviso,) = avisos
    assert aviso.titulo == "Itens em caixa incompleta: F"
    assert "4 un de P2" in aviso.corpo
    assert "caixa que ficou incompleta por falta de pagamento de outro comprador" in aviso.corpo
    assert "R$ 23,59" in aviso.corpo
    assert "autorização do administrador" in aviso.corpo
    assert "fila de pendentes do fornecedor, na posição original" in aviso.corpo
    assert aviso.link == f"/pedidos/{x.pk}/"
    assert aviso.chave == f"itens_cancelados:caixa:{apuracao.pk}:{a.a.pk}"


def test_resultado_de_retorno_nao_estorna_nem_restaura_caixa(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    a, x, _y = arranjo_ap(relogio, minimo="100.00")
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert apuracao.resultado == "retorno_para_interesse"
    assert Reembolso.objects.filter(motivo="caixa_invalidada").count() == 0
    assert _restauracoes() == []
    assert not Notificacao.objects.filter(chave__startswith="itens_cancelados:caixa:").exists()


def test_pedido_inteiro_invalidado_recebe_exatamente_o_que_pagou(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-13
    a, x, _y = arranjo_ap(
        relogio,
        parcelas_de_p1=(("b", 5), ("c", 6)),
        parcelas_de_p2=(("a", 4), ("b", 2), ("c", 6)),
    )
    assert a.c is not None
    pagar(relogio, sim, x)
    pagar(relogio, sim, pedido_de(a.c))
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert apuracao.resultado == "valida"
    reembolsos = _reembolsos(x)
    assert sum((r.produtos for r in reembolsos), D("0.00")) == x.produtos
    assert sum((r.servico for r in reembolsos), D("0.00")) == x.servico
    assert sum((r.frete for r in reembolsos), D("0.00")) == x.frete


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])
def test_suspensao_espera_a_apuracao_e_remove_a_parcela_restaurada(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-14
    from apps.pedidos import apuracao
    from tests.apoio.corrida import Corrida

    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    relogio.congelar(PRAZO)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, apuracao, "_estornar_e_restaurar")
    ra, rb = corrida.rodar(
        lambda: apuracao.iniciar_apuracao(a.admin, a.rodada),
        lambda: suspender(a.admin, a.a),
        a_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    (parcela,) = _parcela(a.a, a.p2)
    assert (parcela.situacao, parcela.quantidade_pendente) == ("removida", D("0.000"))
    assert len(_reembolsos(x)) == 1
