"""E09-07: liquidez por destinação e saídas da conta do provedor (acceptance A-1 a A-6)."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from apps.financeiro.liquidez import (
    Liquidez,
    LiquidezInsuficiente,
    SaidaRepetida,
    liquidez,
    registrar_saida,
)
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.financeiro.alertas import abrir_alerta
from apps.financeiro.livro import (
    MovimentoInvalido,
    MovimentoProibido,
    saldo,
)
from apps.financeiro.models import MovimentoFinanceiro, TipoDeMovimento
from apps.financeiro.reserva import InvarianteViolado
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.financeiro import (
    ItemPago,
    Rodada1,
    montar_l,
    obrigacao_de,
    pedidos_pagos_e_apurados,
    receita_de,
)
from tests.apoio.pedidos import T0, administrador
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)
T = TipoDeMovimento


@dataclass
class L:
    a: Rodada1
    b: Rodada1
    sim: Any
    relogio: RelogioControlado


@pytest.fixture
def ambiente(relogio: RelogioControlado, simulador_pagamentos: Any) -> L:
    """O arranjo L: XA aprovado às `T0 + 1h` e XB às `T0 - 30h`, liberação em 24h e tarifa zero;
    o relógio em `T0 + 2h`."""
    a, b = montar_l(simulador_pagamentos, relogio)
    return L(a, b, simulador_pagamentos, relogio)


def _repasse(
    l_: L, valor: str, identificacao: str = "sim-mov-9", **extra: Any
) -> MovimentoFinanceiro:
    campos: dict[str, Any] = {
        "tipo": "repasse",
        "conta": obrigacao_de(l_.a.fornecedor, l_.a.rodada),
        "valor": D(valor),
        "identificacao": identificacao,
        "justificativa": "Repasse manual por Pix",
        **extra,
    }
    return registrar_saida(administrador(), **campos)


def test_liquidez_separa_o_liberado_do_a_liberar(ambiente: L) -> None:  # A-1
    a = liquidez(obrigacao_de(ambiente.a.fornecedor, ambiente.a.rodada))
    b = liquidez(obrigacao_de(ambiente.b.fornecedor, ambiente.b.rodada))
    assert a == Liquidez(D("0.00"), D("100.00"))
    assert b == Liquidez(D("80.00"), D("0.00"))


def test_repasse_de_a_nao_usa_o_dinheiro_liberado_de_b(ambiente: L) -> None:  # A-2, T-11
    antes = (
        MovimentoFinanceiro.objects.count(),
        saldo(obrigacao_de(ambiente.b.fornecedor, ambiente.b.rodada)),
    )
    with pytest.raises(LiquidezInsuficiente) as erro:
        _repasse(ambiente, "50.00")
    assert "0,00" in str(erro.value) or "0.00" in str(erro.value)
    assert (
        MovimentoFinanceiro.objects.count(),
        saldo(obrigacao_de(ambiente.b.fornecedor, ambiente.b.rodada)),
    ) == antes


def test_repasse_liberado_baixa_so_a_obrigacao_daquele_fornecedor(ambiente: L) -> None:  # A-3
    ambiente.relogio.congelar(T0 + 25 * H)
    movimento = _repasse(ambiente, "50.00")
    assert movimento.tipo == T.REPASSE
    assert movimento.chave == "saida:sim-mov-9"
    assert saldo(obrigacao_de(ambiente.a.fornecedor, ambiente.a.rodada)) == D("50.00")
    assert saldo(obrigacao_de(ambiente.b.fornecedor, ambiente.b.rodada)) == D("80.00")
    assert EntradaAuditoria.objects.filter(acao="financeiro.movimento").count() == 1


def test_o_que_ja_saiu_ou_financiou_desconta_do_liberado(ambiente: L) -> None:  # A-4
    ambiente.relogio.congelar(T0 + 25 * H)
    _repasse(ambiente, "50.00")
    a = ambiente.a
    from apps.financeiro.obrigacoes import registrar_obrigacao_com_comprador

    with transaction.atomic():
        registrar_obrigacao_com_comprador(
            origem=a.pedido.abertura,
            rodada=a.rodada,
            ciclo=a.ciclo,
            comprador=a.comprador,
            pedido=a.pedido,
            motivo="devolucao_de_teste",
            produtos=D("20.00"),
            servico=D("0.00"),
            frete=D("0.00"),
        )
    assert liquidez(obrigacao_de(a.fornecedor, a.rodada)) == Liquidez(D("30.00"), D("0.00"))


def test_dois_pedidos_da_mesma_rodada_um_liberado_e_outro_nao(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-5
    rodada = pedidos_pagos_e_apurados(
        simulador_pagamentos,
        relogio,
        nome="A",
        t0=T0,
        itens=[
            ItemPago("100.00", "5.00", T0 + H, 24),
            ItemPago("60.00", "0.00", T0 + H, 48),  # XA2: liberação em 48h
        ],
    )
    relogio.congelar(T0 + 25 * H)
    conta = obrigacao_de(rodada.fornecedor, rodada.rodada)
    assert liquidez(conta) == Liquidez(D("100.00"), D("60.00"))


def test_saidas_proibidas_repetidas_ou_sem_justificativa(ambiente: L) -> None:  # A-6
    ambiente.relogio.congelar(T0 + 25 * H)
    a = ambiente.a
    antes = MovimentoFinanceiro.objects.count()
    with pytest.raises(MovimentoProibido):
        registrar_saida(
            administrador(),
            tipo="repasse",
            conta=receita_de(a.rodada),
            valor=D("1.00"),
            identificacao="x-1",
            justificativa="Repasse",
        )
    with pytest.raises(MovimentoProibido):
        registrar_saida(
            administrador(),
            tipo="retirada_de_receita",
            conta=obrigacao_de(a.fornecedor, a.rodada),
            valor=D("1.00"),
            identificacao="x-2",
            justificativa="Retirada",
        )
    with pytest.raises(MovimentoInvalido) as erro:
        _repasse(ambiente, "1.00", "x-3", justificativa="  ")
    assert erro.value.codigo == "justificativa"
    assert MovimentoFinanceiro.objects.count() == antes
    _repasse(ambiente, "1.00", "sim-mov-9")
    with pytest.raises(SaidaRepetida):
        _repasse(ambiente, "1.00", "sim-mov-9")
    assert MovimentoFinanceiro.objects.count() == antes + 1


def test_so_o_administrador_registra_saida(ambiente: L) -> None:
    ambiente.relogio.congelar(T0 + 25 * H)
    antes = MovimentoFinanceiro.objects.count()
    for autor in (ambiente.a.comprador, None):
        with pytest.raises(PermissionDenied):
            registrar_saida(
                autor,  # type: ignore[arg-type]
                tipo="repasse",
                conta=obrigacao_de(ambiente.a.fornecedor, ambiente.a.rodada),
                valor=D("1.00"),
                identificacao="x-9",
                justificativa="Repasse",
            )
    assert MovimentoFinanceiro.objects.count() == antes


def test_retirada_de_receita_so_do_liberado_e_bloqueada_pelo_invariante(ambiente: L) -> None:
    ambiente.relogio.congelar(T0 + 25 * H)
    receita = receita_de(ambiente.a.rodada)
    assert liquidez(receita).liberado == D("5.00")
    with transaction.atomic():
        abrir_alerta("invariante_violado", "geral", {"diferenca": "-1.00"})
    with pytest.raises(InvarianteViolado):
        registrar_saida(
            administrador(),
            tipo="retirada_de_receita",
            conta=receita,
            valor=D("1.00"),
            identificacao="x-ret",
            justificativa="Retirada",
        )
    movimento = _repasse(ambiente, "10.00", "x-rep")  # o repasse continua permitido
    assert movimento.tipo == T.REPASSE
    assert saldo(receita) == D("5.00")
