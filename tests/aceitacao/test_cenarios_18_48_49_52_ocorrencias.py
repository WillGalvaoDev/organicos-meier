"""Cenários 18, 48, 49 e 52 da especificação funcional, pelo serviço de ocorrências (E14-02)."""

from decimal import Decimal
from typing import Any

import pytest

from apps.pedidos.models import ItemDoPedido, Pedido
from apps.rodadas.models import Rodada
from tests.apoio.entrega import arranjo_ae, arranjo_unico, item_de, ocorrer
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _componentes(resultado: Any) -> tuple[Decimal, Decimal, Decimal]:
    reembolso = resultado.reembolso.reembolso
    return reembolso.produtos, reembolso.servico, reembolso.frete


def test_cenario_18_reembolso_pontual_com_servico_e_frete_proporcionais(
    relogio: RelogioControlado, sim: Any
) -> None:
    a, pedido, _pf = arranjo_unico(relogio, sim, preco="12.50", quantidade=8)
    resultado = ocorrer(a.admin, item_de(pedido, a.p1), D("2"), "faltante")
    assert _componentes(resultado) == (D("25.00"), D("1.25"), D("5.00"))
    assert resultado.reembolso.obrigacao.devido == D("31.25")


def test_cenarios_48_e_52_a_ocorrencia_nao_muda_pedido_nem_rodada(
    relogio: RelogioControlado, sim: Any
) -> None:
    a, pedido, _pf = arranjo_unico(relogio, sim)
    antes = (list(Pedido.objects.values()), list(ItemDoPedido.objects.values()))
    resultado = ocorrer(a.admin, item_de(pedido, a.p1), D("2"), "faltante")
    assert _componentes(resultado) == (D("20.00"), D("1.00"), D("4.00"))
    assert (list(Pedido.objects.values()), list(ItemDoPedido.objects.values())) == antes
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "aguardando_fornecedor"


def test_cenario_49_a_soma_das_ocorrencias_nao_passa_da_quantidade_paga(
    relogio: RelogioControlado, sim: Any
) -> None:
    from apps.pedidos.ocorrencias import OcorrenciaRecusada

    a, x, _y, _pf = arranjo_ae(relogio, sim)
    item = item_de(x, a.p1)
    ocorrer(a.admin, item, D("4"), "faltante")
    with pytest.raises(OcorrenciaRecusada) as erro:
        ocorrer(a.admin, item, D("3"), "nao_entregue")
    assert erro.value.codigo == "passa_do_saldo_do_item"


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_t18_duas_ocorrencias_ao_mesmo_tempo_no_mesmo_item(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.financeiro.models import ObrigacaoComComprador, Reembolso
    from apps.pedidos import ocorrencias as modulo
    from apps.pedidos.ocorrencias import OcorrenciaRecusada
    from tests.apoio.corrida import Corrida

    a, x, _y, _pf = arranjo_ae(relogio, simulador_pagamentos)
    item = item_de(x, a.p1)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "registrar_auditoria")
    ra, rb = corrida.rodar(
        lambda: ocorrer(a.admin, item, D("4"), "faltante"),
        lambda: ocorrer(a.admin, item, D("4"), "nao_entregue"),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert isinstance(rb.excecao, OcorrenciaRecusada), repr(rb.excecao)
    assert corrida.b_esperou
    assert (Reembolso.objects.count(), ObrigacaoComComprador.objects.count()) == (1, 1)
