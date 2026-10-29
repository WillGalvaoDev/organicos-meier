"""E10-02: concorrência do cálculo do reembolso (acceptance A-15 e A-16).

As corridas pausam a operação A logo depois de ler o acumulado, e a operação B começa nesse
ponto: sem a trava do pedido, B lê o mesmo acumulado que A e as duas gravam em cima dele."""

from decimal import Decimal
from threading import Barrier
from typing import Any

import pytest
from django.db import transaction

from apps.financeiro import reembolsos as reembolsos_modulo
from apps.financeiro.models import ItemReembolsado, ObrigacaoComComprador, Reembolso
from apps.financeiro.reembolsos import (
    ReembolsoRecusado,
    acumulado_do_item,
    acumulado_do_pedido,
    reembolso_integral_do_pedido,
    reembolso_parcial,
)
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.corrida import Corrida
from tests.apoio.devolucoes import K, N, pedido_pago_com_itens
from tests.apoio.financeiro import chave_nova
from tests.apoio.pedidos import administrador
from tests.conftest import RelogioControlado

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]

D = Decimal
OC = "ocorrencia_de_entrega"


def test_dois_parciais_do_mesmo_item_nunca_passam_do_pago(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-15 (corrida determinística)
    _, (item,) = pedido_pago_com_itens(K)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, reembolsos_modulo, "acumulado_do_item")
    admin = administrador()

    def parcial(quantidade: str) -> Any:
        return lambda: reembolso_parcial(
            item, D(quantidade), chave=chave_nova(), motivo=OC, autor=admin
        )

    a, b = corrida.rodar(parcial("0.5"), parcial("0.75"))
    assert a.excecao is None, a.excecao
    assert isinstance(b.excecao, ReembolsoRecusado), b.excecao
    assert acumulado_do_item(item) == (D("0.500"), D("4.00"))  # 7,99 vezes 0,5, arredondado
    assert Reembolso.objects.count() == ItemReembolsado.objects.count() == 1
    assert ObrigacaoComComprador.objects.count() == 1


def test_tres_parciais_ao_mesmo_tempo_respeitam_o_pago(relogio: RelogioControlado) -> None:  # A-15
    pedido, (item,) = pedido_pago_com_itens(K)
    admin = administrador()

    def parcial(quantidade: str) -> Any:
        def executa(barreira: Barrier) -> Any:
            barreira.wait(timeout=10)
            with transaction.atomic():
                return reembolso_parcial(
                    item, D(quantidade), chave=chave_nova(), motivo=OC, autor=admin
                )

        return executa

    resultados = executar_em_paralelo(parcial("0.5"), parcial("0.5"), parcial("0.25"))
    excecoes = [r.excecao for r in resultados]
    assert all(e is None or isinstance(e, ReembolsoRecusado) for e in excecoes), excecoes
    quantidade, valor = acumulado_do_item(item)
    assert quantidade <= D("1.000")
    assert valor <= D("7.99")
    assert sum(e is None for e in excecoes) == Reembolso.objects.count()
    assert Reembolso.objects.count() == ItemReembolsado.objects.count()
    assert any(isinstance(e, ReembolsoRecusado) for e in excecoes)  # 1,25 não cabe em 1,000
    produtos, servico, frete = acumulado_do_pedido(pedido)
    assert produtos <= D("7.99")
    assert servico <= D("0.40")
    assert frete <= D("1.60")


def test_parcial_e_integral_ao_mesmo_tempo_fecham_exatamente(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-16
    pedido, (_, i2) = pedido_pago_com_itens(N)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, reembolsos_modulo, "acumulado_do_pedido")
    admin = administrador()

    def parcial() -> Any:
        return reembolso_parcial(i2, D("1"), chave=chave_nova(), motivo=OC, autor=admin)

    def integral() -> Any:
        return reembolso_integral_do_pedido(
            pedido, chave=chave_nova(), motivo="cancelamento_da_rodada", autor=admin
        )

    a, b = corrida.rodar(parcial, integral)
    assert a.excecao is None, a.excecao
    assert b.excecao is None, b.excecao
    assert acumulado_do_pedido(pedido) == (D("100.00"), D("5.00"), D("20.00"))
    obrigacoes = ObrigacaoComComprador.objects.all()
    assert len(obrigacoes) == 2
    assert sum((o.devido for o in obrigacoes), D("0.00")) == D("125.00")
