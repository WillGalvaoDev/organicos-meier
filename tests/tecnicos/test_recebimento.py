"""E14-01: o recebimento dos produtos do fornecedor (acceptance A-1 a A-17)."""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction

from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from tests.apoio.entrega import arranjo_af, receber
from tests.apoio.apuracao import H
from tests.apoio.pedido_formal import PRAZO
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, ProdutoFactory

pytestmark = pytest.mark.django_db

D = Decimal
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _recebimentos() -> list[Any]:
    from apps.pedidos.models import RecebimentoDoFornecedor

    return list(RecebimentoDoFornecedor.objects.order_by("pk"))


def _situacao(rodada: Any) -> dict[str, Any]:
    from apps.pedidos.recebimento import situacao_do_recebimento

    return {linha.nome: linha for linha in situacao_do_recebimento(rodada)}


def _auditorias() -> int:
    return EntradaAuditoria.objects.filter(acao="recebimento.registrar").count()


def _recusa(autor: Any, rodada: Any, produto: Any, quantidade: Any, acionamento: Any = None) -> str:
    from apps.pedidos.recebimento import RecebimentoRecusado

    antes = (len(_recebimentos()), _auditorias())
    with pytest.raises(RecebimentoRecusado) as erro:
        receber(autor, rodada, produto, quantidade, acionamento)
    assert (len(_recebimentos()), _auditorias()) == antes
    return str(erro.value.codigo)


def test_o_primeiro_recebimento_grava_e_resume(relogio: RelogioControlado, sim: Any) -> None:  # A-1
    a, _x, _y, _pf = arranjo_af(relogio, sim)
    resultado = receber(a.admin, a.rodada, a.p1, D("7"))
    assert resultado.novo is True
    (registro,) = _recebimentos()
    assert registro.linha.produto_id == a.p1.pk
    assert registro.quantidade == D("7.000")
    assert registro.autor_id == a.admin.pk
    assert registro.registrado_em == PRAZO
    situacao = _situacao(a.rodada)
    assert (situacao["P1"].pedida, situacao["P1"].recebida, situacao["P1"].a_resolver) == (
        D("11"),
        D("7"),
        D("4"),
    )
    assert (situacao["P2"].pedida, situacao["P2"].recebida, situacao["P2"].a_resolver) == (
        D("12"),
        D("0"),
        D("12"),
    )
    assert situacao["P1"].unidade == "unidade"


def test_entregas_parciais_somam(relogio: RelogioControlado, sim: Any) -> None:  # A-2
    from apps.pedidos.recebimento import recebimento_resolvido

    a, _x, _y, _pf = arranjo_af(relogio, sim)
    receber(a.admin, a.rodada, a.p1, D("7"))
    relogio.congelar(T0 + 60 * H)
    receber(a.admin, a.rodada, a.p1, D("4"))
    primeiro, segundo = _recebimentos()
    assert (primeiro.registrado_em, segundo.registrado_em) == (PRAZO, T0 + 60 * H)
    situacao = _situacao(a.rodada)
    assert (situacao["P1"].recebida, situacao["P1"].a_resolver) == (D("11"), D("0"))
    assert recebimento_resolvido(a.rodada) is False


def test_tudo_recebido_resolve(relogio: RelogioControlado, sim: Any) -> None:  # A-3
    from apps.pedidos.recebimento import recebimento_resolvido

    a, _x, _y, _pf = arranjo_af(relogio, sim)
    receber(a.admin, a.rodada, a.p1, D("11"))
    receber(a.admin, a.rodada, a.p2, D("12"))
    assert recebimento_resolvido(a.rodada) is True


def test_passar_do_pedido_formal_e_recusado(relogio: RelogioControlado, sim: Any) -> None:  # A-4
    from apps.pedidos.recebimento import RecebimentoRecusado

    a, _x, _y, _pf = arranjo_af(relogio, sim)
    receber(a.admin, a.rodada, a.p1, D("7"))
    with pytest.raises(RecebimentoRecusado) as erro:
        receber(a.admin, a.rodada, a.p1, D("5"))
    assert erro.value.codigo == "passa_do_pedido_formal"
    assert str(erro.value).endswith("(4 unidade).")
    assert len(_recebimentos()) == 1


@pytest.mark.parametrize(
    "quantidade", [D("0"), D("-1"), D("1.5"), D("NaN"), D("1.0001"), 1.0], ids=str
)
def test_quantidade_invalida(relogio: RelogioControlado, sim: Any, quantidade: Any) -> None:  # A-5
    a, _x, _y, _pf = arranjo_af(relogio, sim)
    assert _recusa(a.admin, a.rodada, a.p1, quantidade) == "quantidade_invalida"


def test_produto_fora_do_pedido_formal(relogio: RelogioControlado, sim: Any) -> None:  # A-6
    a, _x, _y, _pf = arranjo_af(relogio, sim)
    p3 = ProdutoFactory.create(fornecedor=a.fornecedor, nome="P3")
    de_outro = ProdutoFactory.create(nome="Outro")
    assert _recusa(a.admin, a.rodada, p3, D("1")) == "produto_fora_do_pedido_formal"
    assert _recusa(a.admin, a.rodada, de_outro, D("1")) == "produto_fora_do_pedido_formal"


@pytest.mark.parametrize("etapa", ["interesse", "pagamento", "cancelada", "liberada"])
def test_fora_de_aguardando_fornecedor(
    relogio: RelogioControlado, sim: Any, etapa: str
) -> None:  # A-7
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
    from apps.rodadas.models import Rodada

    a, _x, _y, _pf = arranjo_af(relogio, sim)
    if etapa == "cancelada":
        cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    else:
        nova = "disponivel_para_retirada" if etapa == "liberada" else etapa
        Rodada.objects.filter(pk=a.rodada.pk).update(etapa=nova)
    assert _recusa(a.admin, a.rodada, a.p1, D("1")) == "etapa"


def test_so_o_administrador_registra(relogio: RelogioControlado, sim: Any) -> None:  # A-8
    a, _x, _y, _pf = arranjo_af(relogio, sim)
    conta_f = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    for autor in (a.a, conta_f, None):
        with pytest.raises(PermissionDenied):
            receber(autor, a.rodada, a.p1, D("1"))
    assert not _recebimentos()


def test_o_mesmo_acionamento_devolve_o_mesmo_registro(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    a, _x, _y, _pf = arranjo_af(relogio, sim)
    a1 = uuid.uuid4()
    primeiro = receber(a.admin, a.rodada, a.p1, D("7"), a1)
    segundo = receber(a.admin, a.rodada, a.p1, D("7"), a1)
    assert (primeiro.novo, segundo.novo) == (True, False)
    assert primeiro.recebimento.pk == segundo.recebimento.pk
    assert len(_recebimentos()) == 1
    assert _auditorias() == 1


def test_acionamento_invalido(relogio: RelogioControlado, sim: Any) -> None:  # A-10
    a, _x, _y, _pf = arranjo_af(relogio, sim)
    a1 = uuid.uuid4()
    receber(a.admin, a.rodada, a.p1, D("7"), a1)
    outra, _x2, _y2, _pf2 = arranjo_af(relogio, sim)
    assert _recusa(a.admin, a.rodada, a.p1, D("3"), a1) == "acionamento_invalido"
    assert _recusa(outra.admin, outra.rodada, outra.p1, D("7"), a1) == "acionamento_invalido"
    assert _recusa(a.admin, a.rodada, a.p1, D("1"), "abc") == "acionamento_invalido"
    assert _recusa(a.admin, a.rodada, a.p1, D("1"), None) == "acionamento_invalido"


def test_a_auditoria_do_recebimento(relogio: RelogioControlado, sim: Any) -> None:  # A-11
    a, _x, _y, _pf = arranjo_af(relogio, sim)
    a1 = uuid.uuid4()
    receber(a.admin, a.rodada, a.p1, D("7"), a1)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="recebimento.registrar")
    assert auditoria.autor_id == str(a.admin.pk)
    assert auditoria.alteracoes == {
        "rodada": a.rodada.pk,
        "produto": a.p1.pk,
        "quantidade": "7.000",
        "recebido": "7.000",
        "acionamento": str(a1),
    }


def test_o_recebimento_nao_muda_mais_nada(relogio: RelogioControlado, sim: Any) -> None:  # A-12
    from apps.financeiro.models import MovimentoFinanceiro
    from apps.pedidos.models import (
        EnvioDoPedidoFormal,
        LinhaDoPedidoFormal,
        Pedido,
        PedidoFormal,
        PrevisaoDeEntrega,
        SituacaoDoPedido,
    )

    a, _x, _y, _pf = arranjo_af(relogio, sim)

    def foto() -> Any:
        return (
            list(PedidoFormal.objects.values()),
            list(LinhaDoPedidoFormal.objects.values()),
            list(EnvioDoPedidoFormal.objects.values()),
            list(PrevisaoDeEntrega.objects.values()),
            list(Pedido.objects.values()),
            list(SituacaoDoPedido.objects.values()),
            list(MovimentoFinanceiro.objects.values()),
            Notificacao.objects.count(),
        )

    antes = foto()
    receber(a.admin, a.rodada, a.p1, D("7"))
    relogio.congelar(T0 + 60 * H)
    receber(a.admin, a.rodada, a.p1, D("4"))
    assert foto() == antes


def test_o_recebimento_so_aceita_insercao(relogio: RelogioControlado, sim: Any) -> None:  # A-13
    from apps.pedidos.models import RecebimentoDoFornecedor

    a, _x, _y, _pf = arranjo_af(relogio, sim)
    receber(a.admin, a.rodada, a.p1, D("7"))
    registro = RecebimentoDoFornecedor.objects.get()
    with pytest.raises(RegistroImutavel):
        registro.save()
    with pytest.raises(RegistroImutavel):
        registro.delete()
    with pytest.raises(RegistroImutavel):
        RecebimentoDoFornecedor.objects.all().update(quantidade=1)
    with pytest.raises(RegistroImutavel):
        RecebimentoDoFornecedor.objects.all().delete()
    for comando in (
        "UPDATE pedidos_recebimentodofornecedor SET quantidade = 1",
        "DELETE FROM pedidos_recebimentodofornecedor",
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(comando)


def test_produto_por_peso(relogio: RelogioControlado, sim: Any) -> None:  # A-14
    a, _x, _y, _pf = arranjo_af(
        relogio,
        sim,
        unidade_de_p1="kg",
        incremento_de_p1="0.500",
        parcelas_de_p1=(("a", 2), ("b", 1)),
    )
    receber(a.admin, a.rodada, a.p1, D("2.5"))
    assert _recusa(a.admin, a.rodada, a.p1, D("0.3")) == "quantidade_invalida"
    assert _situacao(a.rodada)["P1"].recebida == D("2.5")


# --- concorrência (A-15 a A-17) -------------------------------------------------------------------


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_dois_recebimentos_que_passam_da_linha(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-15
    from apps.pedidos import recebimento as modulo
    from apps.pedidos.recebimento import RecebimentoRecusado
    from tests.apoio.corrida import Corrida

    a, _x, _y, _pf = arranjo_af(relogio, simulador_pagamentos)
    receber(a.admin, a.rodada, a.p1, D("7"))
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "registrar_auditoria")
    ra, rb = corrida.rodar(
        lambda: receber(a.admin, a.rodada, a.p1, D("4")),
        lambda: receber(a.admin, a.rodada, a.p1, D("4")),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert isinstance(rb.excecao, RecebimentoRecusado), repr(rb.excecao)
    assert rb.excecao.codigo == "passa_do_pedido_formal"
    assert corrida.b_esperou
    assert _situacao(a.rodada)["P1"].recebida == D("11")


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_o_mesmo_acionamento_em_paralelo(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-16
    from apps.pedidos import recebimento as modulo
    from tests.apoio.corrida import Corrida

    a, _x, _y, _pf = arranjo_af(relogio, simulador_pagamentos)
    a1 = uuid.uuid4()
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "registrar_auditoria")
    ra, rb = corrida.rodar(
        lambda: receber(a.admin, a.rodada, a.p1, D("7"), a1),
        lambda: receber(a.admin, a.rodada, a.p1, D("7"), a1),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None and rb.excecao is None, (ra.excecao, rb.excecao)
    assert ra.valor.recebimento.pk == rb.valor.recebimento.pk
    assert (ra.valor.novo, rb.valor.novo) == (True, False)
    assert len(_recebimentos()) == 1


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_recebimento_e_cancelamento_em_paralelo(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-17
    from apps.pedidos import cancelamento_da_rodada as cancelamento
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
    from apps.pedidos.recebimento import RecebimentoRecusado
    from tests.apoio.corrida import Corrida

    a, _x, _y, _pf = arranjo_af(relogio, simulador_pagamentos)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, cancelamento, "_gravar_o_cancelamento")
    ra, rb = corrida.rodar(
        lambda: cancelar_rodada(a.admin, a.rodada, com_reembolso=False),
        lambda: receber(a.admin, a.rodada, a.p1, D("1")),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert isinstance(rb.excecao, RecebimentoRecusado), repr(rb.excecao)
    assert rb.excecao.codigo == "etapa"
    assert corrida.b_esperou
    assert not _recebimentos()
