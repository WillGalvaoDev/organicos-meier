"""E14-02: as ocorrências de entrega com reembolso pontual (acceptance A-1 a A-24)."""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction

from apps.financeiro.livro import conta, saldo
from apps.financeiro.models import (
    Destinacao,
    ItemReembolsado,
    ObrigacaoComComprador,
    ParcelaDeDevolucao,
    Reembolso,
)
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from tests.apoio.devolucoes import M as ARRANJO_M
from tests.apoio.devolucoes import itens_do_pedido
from tests.apoio.entrega import (
    NOVO,
    arranjo_ae,
    arranjo_unico,
    item_de,
    ocorrer,
    receber,
)
from tests.apoio.pedido_formal import PRAZO
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _ocorrencias() -> list[Any]:
    from apps.pedidos.models import OcorrenciaDeEntrega

    return list(OcorrenciaDeEntrega.objects.order_by("pk"))


def _foto_dos_registros() -> Any:
    return (
        len(_ocorrencias()),
        Reembolso.objects.count(),
        ObrigacaoComComprador.objects.count(),
        EntradaAuditoria.objects.filter(acao="ocorrencia.registrar").count(),
    )


def _recusa(autor: Any, item: Any, quantidade: Any, tipo: Any, acionamento: Any = NOVO) -> str:
    from apps.pedidos.ocorrencias import OcorrenciaRecusada

    antes = _foto_dos_registros()
    with pytest.raises(OcorrenciaRecusada) as erro:
        ocorrer(autor, item, quantidade, tipo, acionamento)
    assert _foto_dos_registros() == antes
    return str(erro.value.codigo)


def _componentes(resultado: Any) -> tuple[Decimal, Decimal, Decimal]:
    reembolso = resultado.reembolso.reembolso
    return reembolso.produtos, reembolso.servico, reembolso.frete


def _obrigacao_do_fornecedor(a: Any) -> Any:
    return conta(Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=a.fornecedor.pk, rodada=a.rodada.pk)


def _liberada(rodada: Any) -> None:
    from apps.rodadas.models import Rodada

    Rodada.objects.filter(pk=rodada.pk).update(etapa="disponivel_para_retirada")


# --- AE-48 e AE-18 ---------------------------------------------------------------------------


def test_cenario_48_faltante_gera_reembolso_pontual(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    a, pedido, _pf = arranjo_unico(relogio, sim)
    item = item_de(pedido, a.p1)
    resultado = ocorrer(a.admin, item, D("2"), "faltante")
    assert resultado.nova is True
    (ocorrencia,) = _ocorrencias()
    assert (ocorrencia.tipo, ocorrencia.quantidade, ocorrencia.etapa) == (
        "faltante",
        D("2.000"),
        "aguardando_fornecedor",
    )
    assert (ocorrencia.autor_id, ocorrencia.registrada_em) == (a.admin.pk, PRAZO)
    reembolso = resultado.reembolso.reembolso
    assert reembolso.motivo == "ocorrencia_de_entrega"
    assert _componentes(resultado) == (D("20.00"), D("1.00"), D("4.00"))
    assert reembolso.total == D("25.00")
    obrigacao = resultado.reembolso.obrigacao
    assert (obrigacao.devido, obrigacao.comprador_id) == (D("25.00"), a.c.pk)
    assert ocorrencia.reembolso_id == reembolso.pk


def test_a_ocorrencia_nao_muda_o_pedido_nem_a_rodada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    from apps.pedidos.models import (
        ItemDoPedido,
        ParcelaNoPedido,
        Pedido,
        PedidoFormal,
    )
    from apps.rodadas.models import Rodada

    a, pedido, _pf = arranjo_unico(relogio, sim)

    def foto() -> Any:
        return (
            list(Pedido.objects.values()),
            list(ItemDoPedido.objects.values()),
            list(ParcelaNoPedido.objects.values()),
            list(Rodada.objects.values()),
            list(PedidoFormal.objects.values()),
        )

    antes = foto()
    ocorrer(a.admin, item_de(pedido, a.p1), D("2"), "faltante")
    assert foto() == antes
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "aguardando_fornecedor"


def test_cenario_18_servico_e_frete_proporcionais(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-3
    a, pedido, _pf = arranjo_unico(relogio, sim, preco="12.50", quantidade=8)
    resultado = ocorrer(a.admin, item_de(pedido, a.p1), D("2"), "faltante")
    assert _componentes(resultado) == (D("25.00"), D("1.25"), D("5.00"))
    assert resultado.reembolso.obrigacao.devido == D("31.25")


def test_faltante_no_ae_antes_do_repasse(relogio: RelogioControlado, sim: Any) -> None:  # A-4
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    antes = saldo(_obrigacao_do_fornecedor(a))
    assert antes == D("170.00")
    resultado = ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    assert _componentes(resultado) == (D("20.00"), D("1.00"), D("2.59"))
    assert resultado.reembolso.obrigacao.devido == D("23.59")
    assert resultado.reembolso.obrigacao.comprador_id == a.a.pk
    assert resultado.reembolso.sem_cobertura == D("0.00")
    assert saldo(_obrigacao_do_fornecedor(a)) == D("150.00")


def test_cenario_49_a_soma_nao_passa_da_quantidade_paga(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    from apps.pedidos.ocorrencias import OcorrenciaRecusada

    a, x, _y, _pf = arranjo_ae(relogio, sim)
    item = item_de(x, a.p1)
    ocorrer(a.admin, item, D("4"), "faltante")
    antes = _foto_dos_registros()
    with pytest.raises(OcorrenciaRecusada) as erro:
        ocorrer(a.admin, item, D("3"), "nao_entregue")
    assert erro.value.codigo == "passa_do_saldo_do_item"
    assert str(erro.value).endswith("(2 unidade).")
    assert _foto_dos_registros() == antes


def test_o_que_ja_foi_reembolsado_na_apuracao_conta_no_saldo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    a, x, _y, _pf = arranjo_ae(relogio, sim, pagar_y=False)
    assert _recusa(a.admin, item_de(x, a.p2), D("1"), "faltante") == "passa_do_saldo_do_item"


def test_faltante_passa_do_que_falta_receber(relogio: RelogioControlado, sim: Any) -> None:  # A-7
    from apps.pedidos.ocorrencias import OcorrenciaRecusada

    a, _x, y, _pf = arranjo_ae(relogio, sim)
    receber(a.admin, a.rodada, a.p1, D("9"))
    item = item_de(y, a.p1)
    with pytest.raises(OcorrenciaRecusada) as erro:
        ocorrer(a.admin, item, D("3"), "faltante")
    assert erro.value.codigo == "passa_do_pedido_formal"
    assert str(erro.value).endswith("(2 unidade).")
    ocorrer(a.admin, item, D("2"), "faltante")
    assert len(_ocorrencias()) == 1


def test_incorreto_so_do_que_foi_recebido(relogio: RelogioControlado, sim: Any) -> None:  # A-8
    from apps.pedidos.ocorrencias import OcorrenciaRecusada

    a, x, y, _pf = arranjo_ae(relogio, sim)
    receber(a.admin, a.rodada, a.p2, D("4"))
    primeira = ocorrer(a.admin, item_de(y, a.p2), D("2"), "incorreto")
    assert _componentes(primeira) == (D("10.00"), D("0.50"), D("1.29"))
    with pytest.raises(OcorrenciaRecusada) as erro:
        ocorrer(a.admin, item_de(x, a.p2), D("3"), "incorreto")
    assert erro.value.codigo == "passa_do_recebido"
    assert str(erro.value).endswith("(4 unidade).")


def test_depois_da_liberacao_so_valem_etapa_item_tipo_quantidade_e_saldo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    _liberada(a.rodada)
    item = item_de(x, a.p1)
    resultado = ocorrer(a.admin, item, D("6"), "incorreto")
    assert resultado.ocorrencia.etapa == "disponivel_para_retirada"
    assert _recusa(a.admin, item, D("1"), "faltante") == "passa_do_saldo_do_item"


@pytest.mark.parametrize("situacao", ["cancelada", "pagamento"])
def test_fora_das_etapas_da_entrega(
    relogio: RelogioControlado, sim: Any, situacao: str
) -> None:  # A-10
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
    from apps.rodadas.models import Rodada

    a, x, _y, _pf = arranjo_ae(relogio, sim)
    if situacao == "cancelada":
        cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    else:
        Rodada.objects.filter(pk=a.rodada.pk).update(etapa="pagamento")
    assert _recusa(a.admin, item_de(x, a.p1), D("1"), "faltante") == "etapa"


def test_item_de_pedido_nao_valido(relogio: RelogioControlado, sim: Any) -> None:  # A-11
    a, _x, y, _pf = arranjo_ae(relogio, sim, pagar_y=False)
    assert _recusa(a.admin, item_de(y, a.p1), D("1"), "faltante") == "item_fora_do_pedido_formal"


@pytest.mark.parametrize("tipo", ["troca", "", None])
def test_tipo_invalido(relogio: RelogioControlado, sim: Any, tipo: Any) -> None:  # A-12
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    assert _recusa(a.admin, item_de(x, a.p1), D("1"), tipo) == "tipo_invalido"


@pytest.mark.parametrize(
    "quantidade", [D("0"), D("-1"), D("0.5"), D("1.0001"), D("NaN"), 1.0], ids=str
)
def test_quantidade_invalida(relogio: RelogioControlado, sim: Any, quantidade: Any) -> None:  # A-12
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    assert _recusa(a.admin, item_de(x, a.p1), quantidade, "faltante") == "quantidade_invalida"


def test_so_o_administrador_registra(relogio: RelogioControlado, sim: Any) -> None:  # A-13
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    conta_f = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    antes = _foto_dos_registros()
    for autor in (a.a, conta_f, None):
        with pytest.raises(PermissionDenied):
            ocorrer(autor, item_de(x, a.p1), D("2"), "faltante")
    assert _foto_dos_registros() == antes


def test_o_mesmo_acionamento_repete_sem_escrever(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-14
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    a1 = uuid.uuid4()
    item = item_de(x, a.p1)
    primeira = ocorrer(a.admin, item, D("2"), "faltante", a1)
    segunda = ocorrer(a.admin, item, D("2"), "faltante", a1)
    assert (primeira.nova, segunda.nova) == (True, False)
    assert primeira.ocorrencia.pk == segunda.ocorrencia.pk
    assert segunda.reembolso.reembolso.pk == primeira.reembolso.reembolso.pk
    assert segunda.reembolso.obrigacao.pk == primeira.reembolso.obrigacao.pk
    assert _foto_dos_registros() == (1, 1, 1, 1)


def test_acionamento_com_outro_conteudo(relogio: RelogioControlado, sim: Any) -> None:  # A-15
    a, x, y, _pf = arranjo_ae(relogio, sim)
    a1 = uuid.uuid4()
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante", a1)
    assert _recusa(a.admin, item_de(x, a.p1), D("1"), "faltante", a1) == "acionamento_invalido"
    assert _recusa(a.admin, item_de(y, a.p1), D("2"), "faltante", a1) == "acionamento_invalido"
    assert _recusa(a.admin, item_de(x, a.p1), D("1"), "faltante", "abc") == "acionamento_invalido"


def test_cenario_115_centavos_nao_passam_do_pago(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-16
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    (item_m,) = itens_do_pedido(x, ARRANJO_M[3])
    _liberada(a.rodada)  # o item M não tem linha no pedido formal: só valem item, saldo etc.
    produtos = []
    resultados = []
    for _ in range(6):
        resultado = ocorrer(a.admin, item_m, D("0.1"), "faltante")
        resultados.append(resultado)
        produtos.append(_componentes(resultado)[0])
    assert produtos == [D("0.02"), D("0.02"), D("0.02"), D("0.02"), D("0.01"), D("0.00")]
    assert resultados[5].reembolso.obrigacao is None
    assert resultados[5].reembolso.reembolso.pk is not None
    assert _recusa(a.admin, item_m, D("0.1"), "faltante") == "passa_do_saldo_do_item"


def test_a_auditoria_da_ocorrencia(relogio: RelogioControlado, sim: Any) -> None:  # A-17
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    a1 = uuid.uuid4()
    item = item_de(x, a.p1)
    resultado = ocorrer(a.admin, item, D("2"), "faltante", a1)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="ocorrencia.registrar")
    assert auditoria.autor_id == str(a.admin.pk)
    dados = dict(auditoria.alteracoes)
    reembolso = {chave: D(valor) for chave, valor in dados.pop("reembolso").items()}
    assert reembolso == {"produtos": D("20.00"), "servico": D("1.00"), "frete": D("2.59")}
    assert D(dados.pop("quantidade")) == D("2")
    assert dados == {
        "pedido": x.pk,
        "item": item.pk,
        "tipo": "faltante",
        "etapa": "aguardando_fornecedor",
        "obrigacao": resultado.reembolso.obrigacao.pk,
        "acionamento": str(a1),
    }
    texto = str(auditoria.alteracoes)
    assert a.a.email not in texto
    assert a.a.nome not in texto


def test_a_ocorrencia_so_aceita_insercao(relogio: RelogioControlado, sim: Any) -> None:  # A-18
    from apps.pedidos.models import OcorrenciaDeEntrega

    a, x, _y, _pf = arranjo_ae(relogio, sim)
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    registro = OcorrenciaDeEntrega.objects.get()
    with pytest.raises(RegistroImutavel):
        registro.save()
    with pytest.raises(RegistroImutavel):
        registro.delete()
    with pytest.raises(RegistroImutavel):
        OcorrenciaDeEntrega.objects.all().update(quantidade=1)
    with pytest.raises(RegistroImutavel):
        OcorrenciaDeEntrega.objects.all().delete()
    for comando in (
        "UPDATE pedidos_ocorrenciadeentrega SET quantidade = 1",
        "DELETE FROM pedidos_ocorrenciadeentrega",
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(comando)


def test_a_devolucao_nao_e_automatica(relogio: RelogioControlado, sim: Any) -> None:  # A-19
    from apps.financeiro.devolucoes import autorizar_devolucao

    a, x, _y, _pf = arranjo_ae(relogio, sim)
    resultado = ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    obrigacao = resultado.reembolso.obrigacao
    assert not ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).exists()
    assert not Notificacao.objects.filter(evento="estorno").exists()
    parcela = autorizar_devolucao(obrigacao, autor=a.admin)
    assert parcela.obrigacao_id == obrigacao.pk


def test_ocorrencia_depois_do_repasse_fica_sem_cobertura_de_produtos(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-20
    from apps.pedidos.repasse import registrar_repasse

    a, x, _y, _pf = arranjo_ae(relogio, sim, liberacao_horas=0)
    registrar_repasse(
        a.admin, a.rodada, valor=D("170.00"), identificacao="pix-001", justificativa="Repasse"
    )
    fornecedor = _obrigacao_do_fornecedor(a)
    assert saldo(fornecedor) == D("0.00")
    resultado = ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    assert resultado.reembolso.obrigacao.devido == D("23.59")
    assert resultado.reembolso.sem_cobertura == D("20.00")
    assert saldo(fornecedor) == D("0.00")


# --- cancelamento (A-24) ---------------------------------------------------------------------


def test_o_cancelamento_devolve_so_o_saldo_restante(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-24
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
    from apps.pedidos.models import OcorrenciaDeEntrega

    a, x, _y, _pf = arranjo_ae(relogio, sim)
    item = item_de(x, a.p1)
    ocorrer(a.admin, item, D("2"), "faltante")
    cancelar_rodada(a.admin, a.rodada, com_reembolso=True)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo="cancelamento_da_rodada")
    assert obrigacao.devido == D("70.76")
    total = sum(
        (i.valor for i in ItemReembolsado.objects.filter(item=item)),
        D("0.00"),
    )
    assert total == D("60.00")
    assert OcorrenciaDeEntrega.objects.count() == 1


# --- concorrência (A-21 a A-23) --------------------------------------------------------------


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_duas_ocorrencias_no_mesmo_item_t18(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-21
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
    assert rb.excecao.codigo == "passa_do_saldo_do_item"
    assert corrida.b_esperou
    assert _componentes(ra.valor) == (D("40.00"), D("2.00"), D("5.18"))
    assert _foto_dos_registros() == (1, 1, 1, 1)


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_o_mesmo_acionamento_em_paralelo(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-22
    from apps.pedidos import ocorrencias as modulo
    from tests.apoio.corrida import Corrida

    a, x, _y, _pf = arranjo_ae(relogio, simulador_pagamentos)
    item = item_de(x, a.p1)
    a1 = uuid.uuid4()
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "registrar_auditoria")
    ra, rb = corrida.rodar(
        lambda: ocorrer(a.admin, item, D("2"), "faltante", a1),
        lambda: ocorrer(a.admin, item, D("2"), "faltante", a1),
        a_atomica=False,
        b_atomica=False,
    )
    assert [ra.excecao, rb.excecao] == [None, None]
    assert ra.valor.ocorrencia.pk == rb.valor.ocorrencia.pk
    assert (ra.valor.nova, rb.valor.nova) == (True, False)
    assert _foto_dos_registros() == (1, 1, 1, 1)


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_ocorrencia_e_cancelamento_com_reembolso_em_paralelo(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-23
    from apps.pedidos import cancelamento_da_rodada as cancelamento
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
    from apps.pedidos.ocorrencias import OcorrenciaRecusada
    from tests.apoio.corrida import Corrida

    a, x, y, _pf = arranjo_ae(relogio, simulador_pagamentos)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, cancelamento, "_gravar_o_cancelamento")
    ra, rb = corrida.rodar(
        lambda: cancelar_rodada(a.admin, a.rodada, com_reembolso=True),
        lambda: ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante"),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert isinstance(rb.excecao, OcorrenciaRecusada), repr(rb.excecao)
    assert rb.excecao.codigo == "etapa"
    assert corrida.b_esperou
    devido = {
        o.pedido_id: o.devido
        for o in ObrigacaoComComprador.objects.filter(motivo="cancelamento_da_rodada")
    }
    assert devido == {x.pk: D("94.35"), y.pk: D("106.15")}
    assert not _ocorrencias()
