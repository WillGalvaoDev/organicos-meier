"""E14-05: a retirada por item e o descarte manual (acceptance A-1 a A-20)."""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction

from apps.financeiro.models import MovimentoFinanceiro, ObrigacaoComComprador, Reembolso
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from tests.apoio.apuracao import H
from tests.apoio.entrega import (
    NOVO,
    ae_liberada,
    ae_recebido,
    arranjo_ae,
    descartar,
    item_de,
    liberar,
    ocorrer,
    receber,
    receber_tudo,
    registrar_endereco,
    retirar,
)
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
L = T0 + 72 * H
PRAZO_FINAL = L + timedelta(days=7)
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _retiradas() -> list[Any]:
    from apps.pedidos.models import RetiradaDeItem

    return list(RetiradaDeItem.objects.order_by("pk"))


def _descartes() -> list[Any]:
    from apps.pedidos.models import DescarteDeItem

    return list(DescarteDeItem.objects.order_by("pk"))


def _foto() -> Any:
    return (
        len(_retiradas()),
        len(_descartes()),
        EntradaAuditoria.objects.filter(
            acao__in=["retirada.registrar", "descarte.registrar"]
        ).count(),
    )


def _saldo(item: Any) -> Decimal:
    from apps.pedidos.ocorrencias import saldo_do_item

    return saldo_do_item(item)


def _recusa(funcao: Any, autor: Any, item: Any, quantidade: Any, acionamento: Any = NOVO) -> str:
    from apps.pedidos.retirada import RetiradaRecusada

    antes = _foto()
    with pytest.raises(RetiradaRecusada) as erro:
        funcao(autor, item, quantidade, acionamento)
    assert _foto() == antes
    return str(erro.value.codigo)


def test_a_retirada_reduz_o_saldo(relogio: RelogioControlado, sim: Any) -> None:  # A-1
    a, x, _y, _pf = ae_liberada(relogio, sim)
    item = item_de(x, a.p1)
    relogio.congelar(L + timedelta(days=1))
    resultado = retirar(a.admin, item, D("4"))
    assert resultado.novo is True
    (registro,) = _retiradas()
    assert (registro.item_id, registro.quantidade, registro.autor_id) == (
        item.pk,
        D("4.000"),
        a.admin.pk,
    )
    assert registro.registrada_em == L + timedelta(days=1)
    assert _saldo(item) == D("2")


def test_retiradas_em_momentos_diferentes(relogio: RelogioControlado, sim: Any) -> None:  # A-2
    a, x, _y, _pf = ae_liberada(relogio, sim)
    item = item_de(x, a.p1)
    relogio.congelar(L + timedelta(days=1))
    retirar(a.admin, item, D("4"))
    relogio.congelar(L + timedelta(days=3))
    retirar(a.admin, item, D("2"))
    primeira, segunda = _retiradas()
    assert (primeira.registrada_em, segunda.registrada_em) == (
        L + timedelta(days=1),
        L + timedelta(days=3),
    )
    assert _saldo(item) == D("0")


def test_retirada_acima_do_saldo(relogio: RelogioControlado, sim: Any) -> None:  # A-3
    from apps.pedidos.retirada import RetiradaRecusada

    a, x, _y, _pf = ae_liberada(relogio, sim)
    item = item_de(x, a.p1)
    retirar(a.admin, item, D("4"))
    with pytest.raises(RetiradaRecusada) as erro:
        retirar(a.admin, item, D("3"))
    assert erro.value.codigo == "passa_do_saldo_do_item"
    assert str(erro.value).endswith("(2 unidade).")
    assert len(_retiradas()) == 1


def test_cenario_22_retirada_depois_do_prazo(relogio: RelogioControlado, sim: Any) -> None:  # A-4
    a, _x, y, _pf = ae_liberada(relogio, sim)
    relogio.congelar(L + timedelta(days=10))
    retirar(a.admin, item_de(y, a.p1), D("5"))
    assert len(_retiradas()) == 1


def test_cenario_23_descarte_antes_do_prazo(relogio: RelogioControlado, sim: Any) -> None:  # A-5
    from apps.pedidos.retirada import RetiradaRecusada

    a, x, _y, _pf = ae_liberada(relogio, sim)
    relogio.congelar(PRAZO_FINAL - timedelta(milliseconds=1))
    with pytest.raises(RetiradaRecusada) as erro:
        descartar(a.admin, item_de(x, a.p1), D("6"))
    assert erro.value.codigo == "antes_do_prazo"
    assert "a partir de 12/11/2026 10:00 (horário de Brasília)" in str(erro.value)
    assert not _descartes()


def test_cenario_23_descarte_no_prazo_final(relogio: RelogioControlado, sim: Any) -> None:  # A-6
    a, x, _y, _pf = ae_liberada(relogio, sim)
    item = item_de(x, a.p1)
    relogio.congelar(PRAZO_FINAL)
    descartar(a.admin, item, D("6"))
    assert len(_descartes()) == 1
    assert _saldo(item) == D("0")


def test_cenario_23_o_tempo_nao_descarta(relogio: RelogioControlado, sim: Any) -> None:  # A-7
    from apps.pedidos.retirada import situacao_da_retirada

    a, x, y, _pf = ae_liberada(relogio, sim)
    retirar(a.admin, item_de(x, a.p1), D("4"))
    antes = situacao_da_retirada(a.rodada)
    assert antes.prazo_encerrado is False
    assert antes.vencidos == []
    relogio.congelar(L + timedelta(days=8))
    depois = situacao_da_retirada(a.rodada)
    assert depois.prazo_encerrado is True
    assert [(v.pedido, v.produto, v.saldo) for v in depois.vencidos] == [
        (x.pk, "P1", D("2")),
        (x.pk, "P2", D("4")),
        (y.pk, "P1", D("5")),
        (y.pk, "P2", D("8")),
    ]
    assert not _descartes()
    saldos_antes = [i.saldo for p in antes.pedidos for i in p.itens]
    assert [i.saldo for p in depois.pedidos for i in p.itens] == saldos_antes


@pytest.mark.parametrize("estado", ["recebido", "cancelada"])
def test_fora_de_disponivel_para_retirada(
    relogio: RelogioControlado, sim: Any, estado: str
) -> None:  # A-8
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    a, x, _y, _pf = ae_recebido(relogio, sim)
    if estado == "cancelada":
        cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    item = item_de(x, a.p1)
    assert _recusa(retirar, a.admin, item, D("1")) == "etapa"
    assert _recusa(descartar, a.admin, item, D("1")) == "etapa"


@pytest.mark.parametrize(
    "quantidade", [D("0"), D("-1"), D("0.5"), D("1.0001"), D("NaN"), 1.0], ids=str
)
def test_quantidade_invalida(relogio: RelogioControlado, sim: Any, quantidade: Any) -> None:  # A-9
    a, x, _y, _pf = ae_liberada(relogio, sim)
    assert _recusa(retirar, a.admin, item_de(x, a.p1), quantidade) == "quantidade_invalida"


def test_item_de_pedido_nao_valido(relogio: RelogioControlado, sim: Any) -> None:  # A-9
    a, _x, y, pf = arranjo_ae(relogio, sim, pagar_y=False)
    receber_tudo(a, pf)
    registrar_endereco(a.admin)
    liberar(relogio, a)
    assert _recusa(retirar, a.admin, item_de(y, a.p1), D("1")) == "item_fora_do_pedido_formal"


def test_a_ocorrencia_e_a_retirada_dividem_o_saldo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-10
    a, x, _y, _pf = ae_liberada(relogio, sim)
    item = item_de(x, a.p1)
    retirar(a.admin, item, D("4"))
    ocorrer(a.admin, item, D("2"), "incorreto")
    assert _saldo(item) == D("0")
    assert _recusa(retirar, a.admin, item, D("1")) == "passa_do_saldo_do_item"


def test_a_situacao_da_retirada_com_ocorrencia(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-11
    from apps.pedidos.retirada import situacao_da_retirada

    a, x, _y, _pf = arranjo_ae(relogio, sim)
    registrar_endereco(a.admin)
    receber(a.admin, a.rodada, a.p1, D("9"))
    receber(a.admin, a.rodada, a.p2, D("12"))
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    liberar(relogio, a)
    situacao = situacao_da_retirada(a.rodada)
    pedido_x = situacao.pedidos[0]
    item = pedido_x.itens[0]
    assert (pedido_x.pedido, pedido_x.comprador) == (x.pk, a.a.nome)
    assert (item.produto, item.pedida, item.em_ocorrencias) == ("P1", D("6"), D("2"))
    assert (item.retirada, item.descartada, item.saldo) == (D("0"), D("0"), D("4"))
    assert item.reembolsada_na_apuracao == D("0")
    assert situacao.liberacao.liberada_em == L


def test_o_que_foi_reembolsado_na_apuracao(relogio: RelogioControlado, sim: Any) -> None:  # A-12
    from apps.pedidos.retirada import situacao_da_retirada

    a, x, _y, pf = arranjo_ae(relogio, sim, pagar_y=False)
    receber_tudo(a, pf)
    registrar_endereco(a.admin)
    liberar(relogio, a)
    situacao = situacao_da_retirada(a.rodada)
    item = next(i for i in situacao.pedidos[0].itens if i.produto == "P2")
    assert (item.pedida, item.reembolsada_na_apuracao, item.saldo) == (D("4"), D("4"), D("0"))
    relogio.congelar(L + timedelta(days=8))
    vencidos = situacao_da_retirada(a.rodada).vencidos
    assert all(v.item != item.item for v in vencidos)
    assert x.pk == situacao.pedidos[0].pedido


@pytest.mark.parametrize("situacao", ["suspensa", "removida"])
def test_a_retirada_nao_depende_da_situacao_do_comprador(
    relogio: RelogioControlado, sim: Any, situacao: str
) -> None:  # A-13
    from apps.contas.models import Conta

    a, x, _y, _pf = ae_liberada(relogio, sim)
    Conta.objects.filter(pk=a.a.pk).update(situacao=situacao)
    retirar(a.admin, item_de(x, a.p1), D("6"))
    assert len(_retiradas()) == 1


def test_so_o_administrador_registra(relogio: RelogioControlado, sim: Any) -> None:  # A-14
    a, x, _y, _pf = ae_liberada(relogio, sim)
    conta_f = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    relogio.congelar(PRAZO_FINAL)
    for autor in (a.a, conta_f, None):
        for funcao in (retirar, descartar):
            with pytest.raises(PermissionDenied):
                funcao(autor, item_de(x, a.p1), D("1"))
    assert _foto() == (0, 0, 0)


def test_o_mesmo_acionamento(relogio: RelogioControlado, sim: Any) -> None:  # A-15
    a, x, _y, _pf = ae_liberada(relogio, sim)
    item = item_de(x, a.p1)
    a1 = uuid.uuid4()
    primeiro = retirar(a.admin, item, D("4"), a1)
    segundo = retirar(a.admin, item, D("4"), a1)
    assert (primeiro.novo, segundo.novo) == (True, False)
    assert primeiro.registro.pk == segundo.registro.pk
    assert _foto() == (1, 0, 1)
    assert _recusa(retirar, a.admin, item, D("1"), a1) == "acionamento_invalido"
    assert _recusa(retirar, a.admin, item, D("1"), "abc") == "acionamento_invalido"


def test_a_retirada_nao_tem_efeito_financeiro(relogio: RelogioControlado, sim: Any) -> None:  # A-16
    from apps.pedidos.models import ItemDoPedido, Pedido

    a, x, _y, _pf = ae_liberada(relogio, sim)
    relogio.congelar(PRAZO_FINAL)

    def foto() -> Any:
        return (
            list(Reembolso.objects.values()),
            list(ObrigacaoComComprador.objects.values()),
            list(MovimentoFinanceiro.objects.values()),
            list(Pedido.objects.values()),
            list(ItemDoPedido.objects.values()),
        )

    antes = foto()
    descartar(a.admin, item_de(x, a.p1), D("6"))
    assert foto() == antes


def test_a_auditoria_da_retirada_e_do_descarte(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-17
    a, x, _y, _pf = ae_liberada(relogio, sim)
    item = item_de(x, a.p1)
    a1, a2 = uuid.uuid4(), uuid.uuid4()
    retirar(a.admin, item, D("4"), a1)
    relogio.congelar(PRAZO_FINAL)
    descartar(a.admin, item, D("2"), a2)
    (retirada,) = EntradaAuditoria.objects.filter(acao="retirada.registrar")
    (descarte,) = EntradaAuditoria.objects.filter(acao="descarte.registrar")
    for auditoria, acionamento, quantidade, saldo in (
        (retirada, a1, D("4"), D("2")),
        (descarte, a2, D("2"), D("0")),
    ):
        assert auditoria.autor_id == str(a.admin.pk)
        dados = dict(auditoria.alteracoes)
        assert D(dados.pop("quantidade")) == quantidade
        assert D(dados.pop("saldo")) == saldo
        assert dados == {"pedido": x.pk, "item": item.pk, "acionamento": str(acionamento)}
        assert a.a.nome not in str(auditoria.alteracoes)


def test_retirada_e_descarte_so_aceitam_insercao(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-18
    from apps.pedidos.models import DescarteDeItem, RetiradaDeItem

    a, x, _y, _pf = ae_liberada(relogio, sim)
    item = item_de(x, a.p1)
    retirar(a.admin, item, D("4"))
    relogio.congelar(PRAZO_FINAL)
    descartar(a.admin, item, D("2"))
    for modelo, tabela in (
        (RetiradaDeItem, "pedidos_retiradadeitem"),
        (DescarteDeItem, "pedidos_descartedeitem"),
    ):
        registro = modelo.objects.get()
        with pytest.raises(RegistroImutavel):
            registro.save()
        with pytest.raises(RegistroImutavel):
            registro.delete()
        with pytest.raises(RegistroImutavel):
            modelo.objects.all().update(quantidade=1)
        with pytest.raises(RegistroImutavel):
            modelo.objects.all().delete()
        for comando in (
            f"UPDATE {tabela} SET quantidade = 1",  # noqa: S608
            f"DELETE FROM {tabela}",  # noqa: S608
        ):
            with pytest.raises(IntegrityError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(comando)


# --- concorrência (A-19 e A-20) --------------------------------------------------------------


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_retirada_e_ocorrencia_no_mesmo_item(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-19
    from apps.pedidos import retirada as modulo
    from apps.pedidos.ocorrencias import OcorrenciaRecusada
    from tests.apoio.corrida import Corrida

    a, x, _y, _pf = ae_liberada(relogio, simulador_pagamentos)
    item = item_de(x, a.p1)
    reembolsos = Reembolso.objects.count()
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "registrar_auditoria")
    ra, rb = corrida.rodar(
        lambda: retirar(a.admin, item, D("4")),
        lambda: ocorrer(a.admin, item, D("4"), "incorreto"),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert isinstance(rb.excecao, OcorrenciaRecusada), repr(rb.excecao)
    assert rb.excecao.codigo == "passa_do_saldo_do_item"
    assert corrida.b_esperou
    assert len(_retiradas()) == 1
    assert Reembolso.objects.count() == reembolsos


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_duas_retiradas_no_mesmo_item(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-20
    from apps.pedidos.retirada import RetiradaRecusada

    from apps.pedidos import retirada as modulo
    from tests.apoio.corrida import Corrida

    a, x, _y, _pf = ae_liberada(relogio, simulador_pagamentos)
    item = item_de(x, a.p1)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "registrar_auditoria")
    ra, rb = corrida.rodar(
        lambda: retirar(a.admin, item, D("4")),
        lambda: retirar(a.admin, item, D("4")),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert isinstance(rb.excecao, RetiradaRecusada), repr(rb.excecao)
    assert rb.excecao.codigo == "passa_do_saldo_do_item"
    assert corrida.b_esperou
    assert [r.quantidade for r in _retiradas()] == [D("4.000")]
