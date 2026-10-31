"""E11-02: perda dos itens do fornecedor pelos inadimplentes (acceptance A-1 a A-10)."""

from decimal import Decimal
from typing import Any

import pytest

from apps.catalogo.models import Produto
from apps.interesses.models import ParcelaDeInteresse
from apps.interesses.servicos import RemocaoAcimaDoPendente, remover_pendente
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pedidos.models import ItemDoPedido, ParcelaNoPedido
from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.pedidos import T0, cancelar_direto
from tests.conftest import RelogioControlado
from tests.fabricas import (
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ParcelaFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _iniciar(a: Any) -> Any:
    from apps.pedidos.apuracao import iniciar_apuracao

    return iniciar_apuracao(a.admin, a.rodada)


def _parcelas(comprador: Any) -> list[ParcelaDeInteresse]:
    return list(ParcelaDeInteresse.objects.filter(comprador=comprador).order_by("sequencia"))


def _campos(parcelas: list[ParcelaDeInteresse]) -> list[tuple[Any, ...]]:
    return [
        (
            p.pk,
            p.sequencia,
            p.quantidade_original,
            p.quantidade_reservada,
            p.quantidade_pendente,
            p.situacao,
        )
        for p in parcelas
    ]


def _avisos(conta: Any, chave_com: str = "itens_cancelados") -> list[Notificacao]:
    return list(Notificacao.objects.filter(conta=conta, evento=chave_com).order_by("pk"))


def _apurada_com_so_x_pago(relogio: RelogioControlado, sim: Any) -> tuple[Any, Any, Any]:
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    return a, x, y


def _com_pendente_antigo_de_b(a: Any) -> ParcelaDeInteresse:
    """B tem 3 unidades pendentes de P3, do mesmo fornecedor e fora do estoque da rodada."""
    p3 = ProdutoFactory.create(fornecedor=a.fornecedor, nome="P3", unidade="un")
    return ParcelaFactory.create(
        comprador=a.b,
        produto=p3,
        quantidade_original=D("3"),
        quantidade_reservada=D("0"),
        quantidade_pendente=D("3"),
        situacao="pendente",
    )


def test_inadimplente_perde_as_parcelas_do_fornecedor(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    a, _x, _y = _apurada_com_so_x_pago(relogio, sim)
    antes = _parcelas(a.b)
    assert [p.situacao for p in antes] == ["em_pedido"] * 3
    _iniciar(a)
    depois = _parcelas(a.b)
    assert [p.situacao for p in depois] == ["removida"] * 3
    for velha, nova in zip(antes, depois, strict=True):
        assert (nova.pk, nova.sequencia, nova.quantidade_original) == (
            velha.pk,
            velha.sequencia,
            velha.quantidade_original,
        )
        assert (nova.quantidade_reservada, nova.quantidade_pendente) == (D("0"), D("0"))


def test_pendente_antigo_de_outro_produto_do_fornecedor_tambem_sai(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    a, _x, _y = _apurada_com_so_x_pago(relogio, sim)
    antigo = _com_pendente_antigo_de_b(a)
    _iniciar(a)
    antigo.refresh_from_db()
    assert (antigo.situacao, antigo.quantidade_pendente) == ("removida", D("0"))
    na_fila = ParcelaDeInteresse.objects.filter(
        comprador=a.b,
        produto__fornecedor=a.fornecedor,
        situacao__in=("ativa", "em_pedido", "pendente"),
    )
    assert not na_fila.exists()


def test_parcelas_de_outro_fornecedor_nao_mudam(relogio: RelogioControlado, sim: Any) -> None:
    # A-3
    a, _x, _y = _apurada_com_so_x_pago(relogio, sim)
    g = FornecedorFactory.create(nome="G")
    rodada_g = RodadaFactory.create(fornecedor=g)
    produto_g = ProdutoFactory.create(fornecedor=g, nome="PG")
    EstoqueDaRodadaFactory.create(rodada=rodada_g, produto=produto_g, limite=None)
    de_g = ParcelaFactory.create(
        comprador=a.b,
        produto=produto_g,
        quantidade_original=D("2"),
        quantidade_reservada=D("2"),
    )
    antes = _campos([de_g])
    _iniciar(a)
    de_g.refresh_from_db()
    assert _campos([de_g]) == antes


def test_parcelas_de_quem_pagou_ficam_como_estavam(relogio: RelogioControlado, sim: Any) -> None:
    # A-4
    a, _x, _y = _apurada_com_so_x_pago(relogio, sim)
    antes = _campos(_parcelas(a.a))
    _iniciar(a)
    depois = _parcelas(a.a)
    assert _campos(depois) == antes
    assert [p.situacao for p in depois] == ["em_pedido", "em_pedido"]


def test_composicao_do_pedido_do_inadimplente_nao_muda(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    a, _x, y = _apurada_com_so_x_pago(relogio, sim)
    antes = (
        list(ItemDoPedido.objects.filter(pedido=y).order_by("pk").values()),
        list(ParcelaNoPedido.objects.filter(item__pedido=y).order_by("pk").values()),
    )
    _iniciar(a)
    depois = (
        list(ItemDoPedido.objects.filter(pedido=y).order_by("pk").values()),
        list(ParcelaNoPedido.objects.filter(item__pedido=y).order_by("pk").values()),
    )
    assert depois == antes


def test_aviso_de_cancelamento_ao_inadimplente(relogio: RelogioControlado, sim: Any) -> None:
    # A-6
    a, _x, y = _apurada_com_so_x_pago(relogio, sim)
    _iniciar(a)
    (aviso,) = _avisos(a.b)
    assert aviso.titulo == "Pedido cancelado: F"
    assert aviso.corpo == (
        f"Seu pedido {y.pk} da rodada de F foi cancelado porque o pagamento não foi identificado "
        "até o fim do prazo. Os itens desse fornecedor saíram do seu carrinho, inclusive reservas "
        "e quantidades pendentes. Nada foi cobrado neste pedido."
    )
    assert aviso.link == f"/pedidos/{y.pk}/"
    assert aviso.chave == f"itens_cancelados:inadimplencia:{y.pk}:{a.b.pk}"
    assert _avisos(a.a) == []


def test_cancelado_por_suspensao_perde_as_parcelas_sem_novo_aviso(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    cancelar_direto(y, "suspensao", T0 + 10 * H)
    relogio.congelar(PRAZO)
    _iniciar(a)
    assert [p.situacao for p in _parcelas(a.b)] == ["removida"] * 3
    assert _avisos(a.b) == []


def test_auditoria_lista_as_parcelas_removidas_por_inadimplente(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    a, _x, _y = _apurada_com_so_x_pago(relogio, sim)
    antigo = _com_pendente_antigo_de_b(a)
    antes = _parcelas(a.b)
    _iniciar(a)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.apuracao_final")
    (do_b,) = auditoria.alteracoes["inadimplentes"]
    assert do_b["comprador"] == a.b.pk
    esperadas = [
        [p.pk, str(p.quantidade_reservada), str(p.quantidade_pendente)]
        for p in sorted([*antes], key=lambda p: p.pk)
        if p.pk != antigo.pk
    ]
    esperadas.append([antigo.pk, "0.000", "3.000"])
    assert sorted(do_b["parcelas"]) == sorted(esperadas)
    assert len(do_b["parcelas"]) == 4


def test_apurar_de_novo_nao_avisa_de_novo(relogio: RelogioControlado, sim: Any) -> None:  # A-9
    from apps.pedidos.apuracao import ApuracaoRecusada

    a, _x, _y = _apurada_com_so_x_pago(relogio, sim)
    _iniciar(a)
    with pytest.raises(ApuracaoRecusada):
        _iniciar(a)
    assert len(_avisos(a.b)) == 1


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])
def test_remover_pendente_espera_a_apuracao(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-10
    from apps.pedidos import apuracao
    from tests.apoio.corrida import Corrida

    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    relogio.congelar(PRAZO)
    antigo = _com_pendente_antigo_de_b(a)
    produto: Produto = antigo.produto
    corrida = Corrida()
    corrida.depois_de(monkeypatch, apuracao, "_remover_as_parcelas_dos_inadimplentes")
    ra, rb = corrida.rodar(
        lambda: apuracao.iniciar_apuracao(a.admin, a.rodada),
        lambda: remover_pendente(a.b, produto, D("1")),
        a_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert corrida.b_esperou
    assert isinstance(rb.excecao, RemocaoAcimaDoPendente), rb.excecao
    antigo.refresh_from_db()
    assert (antigo.situacao, antigo.quantidade_pendente, antigo.quantidade_reservada) == (
        "removida",
        D("0"),
        D("0"),
    )
