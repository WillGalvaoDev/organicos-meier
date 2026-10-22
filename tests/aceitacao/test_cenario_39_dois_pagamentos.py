"""Cenário 39 (E09-04, A-3 e A-4): o pagamento que não quita nunca vira receita nem custódia."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from apps.financeiro.livro import saldo
from apps.financeiro.models import (
    AlertaFinanceiro,
    Componente,
    ContaFinanceira,
    Despesa,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    TipoDeMovimento,
)
from apps.pedidos.models import DestinoDoPagamento
from tests.apoio.financeiro import custodia, pedido_composto
from tests.apoio.pedidos import T0, sincronizar, tentativa_criada
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal
H = timedelta(hours=1)
T = TipoDeMovimento


def _um(itens: Any) -> Any:
    achados = list(itens)
    assert len(achados) == 1, f"esperava 1 registro, há {len(achados)}"
    return achados[0]


@pytest.fixture
def ambiente(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    relogio.congelar(T0 + H)
    simulador_pagamentos.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    comprador = ContaFactory.create()
    return comprador, pedido_composto(comprador), simulador_pagamentos, relogio


def _custodia_total(comprador: Any, pedido: Any) -> Decimal:
    rodada, ciclo = pedido.abertura.rodada, pedido.abertura.ciclo
    return sum(
        (
            saldo(custodia(rodada, ciclo, comprador, componente))
            for componente in (Componente.PRODUTOS, Componente.SERVICO, Componente.FRETE)
        ),
        D("0.00"),
    )


def test_dois_pagamentos_do_mesmo_pedido_um_quita_e_o_outro_vira_obrigacao(
    ambiente: Any,
) -> None:  # A-3
    comprador, pedido, sim, relogio = ambiente
    primeira = tentativa_criada(pedido).id_externo
    assert primeira is not None
    sim.expirar(primeira)
    sincronizar(primeira)
    relogio.congelar(T0 + 2 * H)
    segunda = tentativa_criada(pedido).id_externo
    assert segunda is not None
    sim.aprovar(primeira, em=T0 + H)
    sim.aprovar(segunda, em=T0 + 2 * H)
    sincronizar(primeira)
    sincronizar(segunda)
    destinos = {d.pagamento.id_externo: d for d in DestinoDoPagamento.objects.all()}
    assert (destinos[primeira].destino, destinos[segunda].destino) == ("quita", "devolucao")
    assert destinos[segunda].motivo == "duplicidade"
    assert MovimentoFinanceiro.objects.filter(tipo=T.ENTRADA_DE_PAGAMENTO).count() == 1
    assert _custodia_total(comprador, pedido) == D("125.00")
    obrigacao = _um(ObrigacaoComComprador.objects.all())
    assert (obrigacao.integral, obrigacao.motivo) == (D("125.00"), "duplicidade")
    conta_da_obrigacao = ContaFinanceira.objects.get(destinacao="obrigacao_comprador")
    assert saldo(conta_da_obrigacao) == D("125.00")
    assert AlertaFinanceiro.objects.filter(tipo="duplicidade", resolvido_em=None).count() == 1
    assert Despesa.objects.filter(tipo="tarifa").count() == 2
    assert not ContaFinanceira.objects.filter(destinacao="receita_servico").exists()


def test_pagamento_aprovado_depois_da_margem_vira_obrigacao_e_alerta(ambiente: Any) -> None:  # A-4
    comprador, pedido, sim, relogio = ambiente
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    relogio.congelar(T0 + 48 * H + timedelta(seconds=1))
    sim.aprovar(id_externo)
    sincronizar(id_externo)
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=id_externo)
    assert (destino.destino, destino.motivo) == ("devolucao", "aprovado_apos_a_margem")
    obrigacao = _um(ObrigacaoComComprador.objects.all())
    assert obrigacao.integral == D("125.00")
    assert saldo(ContaFinanceira.objects.get(destinacao="obrigacao_comprador")) == D("125.00")
    alerta = _um(AlertaFinanceiro.objects.all())
    assert (alerta.tipo, alerta.chave, alerta.resolvido_em) == (
        "aprovado_apos_a_margem",
        id_externo,
        None,
    )
    assert _custodia_total(comprador, pedido) == D("0.00")
    assert MovimentoFinanceiro.objects.filter(tipo=T.ENTRADA_DE_PAGAMENTO).count() == 0
