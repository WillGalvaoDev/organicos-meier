"""E14-04: a liberação da retirada e o encerramento da rodada (acceptance A-1 a A-22)."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied

from apps.financeiro.models import MovimentoFinanceiro, ObrigacaoComComprador
from apps.interesses.models import ParcelaDeInteresse
from apps.notificacoes.models import Envio, Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.apuracao import H
from tests.apoio.entrega import (
    ENDERECO,
    ae_recebido,
    arranjo_ae,
    item_de,
    liberar,
    ocorrer,
    receber,
    registrar_endereco,
)
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, ParcelaFactory

pytestmark = pytest.mark.django_db

D = Decimal
L = T0 + 72 * H
PRAZO_FINAL = L + timedelta(days=7)
EVENTO = "retirada_liberada"
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _liberacoes() -> list[Any]:
    from apps.pedidos.models import LiberacaoDaRetirada

    return list(LiberacaoDaRetirada.objects.order_by("pk"))


def _avisos() -> list[Notificacao]:
    return list(Notificacao.objects.filter(evento=EVENTO).order_by("pk"))


def _recusa(a: Any, codigo: str, autor: Any = None) -> str:
    from apps.pedidos.liberacao_da_retirada import LiberacaoRecusada, liberar_retirada

    antes = (len(_liberacoes()), len(_avisos()), EntradaAuditoria.objects.count())
    with pytest.raises(LiberacaoRecusada) as erro:
        liberar_retirada(autor or a.admin, a.rodada)
    assert erro.value.codigo == codigo
    assert (len(_liberacoes()), len(_avisos()), EntradaAuditoria.objects.count()) == antes
    return str(erro.value)


def _etapa(a: Any) -> str:
    from apps.rodadas.models import Rodada

    return str(Rodada.objects.get(pk=a.rodada.pk).etapa)


def test_a_liberacao_encerra_a_rodada(relogio: RelogioControlado, sim: Any) -> None:  # A-1
    a, _x, _y, pf = ae_recebido(relogio, sim)
    liberacao = liberar(relogio, a)
    assert _etapa(a) == "disponivel_para_retirada"
    (gravada,) = _liberacoes()
    assert gravada.pk == liberacao.pk
    assert (gravada.liberada_em, gravada.prazo_final) == (L, PRAZO_FINAL)
    assert gravada.endereco.texto == ENDERECO
    assert (gravada.autor_id, gravada.rodada_id, gravada.pedido_formal_id) == (
        a.admin.pk,
        a.rodada.pk,
        pf.pk,
    )
    assert gravada.ciclo_id == a.ciclo.pk


def test_o_aviso_da_liberacao(relogio: RelogioControlado, sim: Any) -> None:  # A-2
    a, x, y, _pf = ae_recebido(relogio, sim)
    liberacao = liberar(relogio, a)
    avisos = _avisos()
    assert {n.conta_id for n in avisos} == {a.a.pk, a.b.pk}
    for pedido, comprador in ((x, a.a), (y, a.b)):
        (aviso,) = [n for n in avisos if n.conta_id == comprador.pk]
        assert aviso.titulo == "Retirada liberada: F"
        assert f"seu pedido {pedido.pk}" in aviso.corpo
        assert ENDERECO in aviso.corpo
        assert "Retire até 12/11/2026 às 10:00 (horário de Brasília)" in aviso.corpo
        assert "Restrições de dia ou horário são publicadas nos comunicados." in aviso.corpo
        assert aviso.link == f"/pedidos/{pedido.pk}/"
        assert aviso.chave == f"retirada_liberada:{liberacao.pk}:{comprador.pk}"
        assert Envio.objects.filter(notificacao=aviso).exists()


def test_as_parcelas_em_pedido_deixam_de_reservar(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-3
    from apps.interesses.consultas import total_reservado

    a, _x, _y, _pf = ae_recebido(relogio, sim)
    c = ContaFactory.create(nome="Comprador C")
    pendente = ParcelaFactory.create(
        comprador=c,
        produto=a.p1,
        situacao="pendente",
        quantidade_original=D("3"),
        quantidade_reservada=D("0"),
        quantidade_pendente=D("3"),
    )
    assert (total_reservado(a.p1), total_reservado(a.p2)) == (D("11"), D("12"))
    antes = {p.pk: p.sequencia for p in ParcelaDeInteresse.objects.all()}
    em_pedido = [p.pk for p in ParcelaDeInteresse.objects.filter(situacao="em_pedido")]
    assert len(em_pedido) == 5
    pendente_antes = ParcelaDeInteresse.objects.filter(pk=pendente.pk).values().get()
    liberar(relogio, a)
    for pk in em_pedido:
        parcela = ParcelaDeInteresse.objects.get(pk=pk)
        assert (parcela.situacao, parcela.quantidade_reservada) == ("removida", D("0"))
    assert (total_reservado(a.p1), total_reservado(a.p2)) == (D("0"), D("0"))
    assert {p.pk: p.sequencia for p in ParcelaDeInteresse.objects.all()} == antes
    assert ParcelaDeInteresse.objects.filter(pk=pendente.pk).values().get() == pendente_antes


def test_cenario_22_a_nova_rodada_nao_herda_a_reserva(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    from apps.interesses.servicos import definir_interesse
    from apps.rodadas.estoque import incluir_produto_na_rodada
    from apps.rodadas.servicos import abrir_rodada

    a, _x, _y, _pf = ae_recebido(relogio, sim)
    liberar(relogio, a)
    nova = abrir_rodada(a.admin, a.fornecedor)
    assert nova.etapa == "interesse"
    incluir_produto_na_rodada(a.admin, nova, a.p1, "11")
    c = ContaFactory.create(nome="Comprador C")
    resumo = definir_interesse(c, a.p1, "11")
    assert resumo.reservado == D("11")


def test_recebimento_pendente_recusa_a_liberacao(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    a, _x, _y, _pf = arranjo_ae(relogio, sim)
    registrar_endereco(a.admin)
    receber(a.admin, a.rodada, a.p1, D("9"))
    receber(a.admin, a.rodada, a.p2, D("12"))
    relogio.congelar(L)
    mensagem = _recusa(a, "recebimento_pendente")
    assert mensagem == "Ainda falta resolver: P1 (2 unidade)."
    assert _etapa(a) == "aguardando_fornecedor"


def test_a_ocorrencia_faltante_completa_o_recebimento(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    registrar_endereco(a.admin)
    receber(a.admin, a.rodada, a.p1, D("9"))
    receber(a.admin, a.rodada, a.p2, D("12"))
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    liberar(relogio, a)
    assert {n.conta_id for n in _avisos()} == {a.a.pk, a.b.pk}


def test_produto_todo_nao_entregue(relogio: RelogioControlado, sim: Any) -> None:  # A-7
    a, x, y, _pf = arranjo_ae(relogio, sim)
    registrar_endereco(a.admin)
    receber(a.admin, a.rodada, a.p1, D("11"))
    ocorrer(a.admin, item_de(x, a.p2), D("4"), "nao_entregue")
    ocorrer(a.admin, item_de(y, a.p2), D("8"), "nao_entregue")
    liberar(relogio, a)
    assert {n.conta_id for n in _avisos()} == {a.a.pk, a.b.pk}


def test_so_quem_tem_o_que_retirar_e_avisado(relogio: RelogioControlado, sim: Any) -> None:  # A-8
    a, _x, y, _pf = arranjo_ae(relogio, sim)
    registrar_endereco(a.admin)
    receber(a.admin, a.rodada, a.p1, D("11"))
    receber(a.admin, a.rodada, a.p2, D("4"))
    ocorrer(a.admin, item_de(y, a.p1), D("5"), "incorreto")
    ocorrer(a.admin, item_de(y, a.p2), D("8"), "nao_entregue")
    liberar(relogio, a)
    assert [n.conta_id for n in _avisos()] == [a.a.pk]


@pytest.mark.parametrize(("situacao", "avisado"), [("suspensa", True), ("removida", False)])
def test_suspenso_recebe_e_removido_nao(
    relogio: RelogioControlado, sim: Any, situacao: str, avisado: bool
) -> None:  # A-9
    from apps.contas.models import Conta

    a, _x, _y, _pf = ae_recebido(relogio, sim)
    Conta.objects.filter(pk=a.b.pk).update(situacao=situacao)
    liberar(relogio, a)
    assert (a.b.pk in {n.conta_id for n in _avisos()}) is avisado
    assert a.a.pk in {n.conta_id for n in _avisos()}


def test_sem_endereco_nao_libera(relogio: RelogioControlado, sim: Any) -> None:  # A-10
    a, _x, _y, _pf = ae_recebido(relogio, sim, endereco=False)
    relogio.congelar(L)
    assert _recusa(a, "sem_endereco") == "Registre o endereço de retirada antes de liberar."


def test_liberar_de_novo_e_recusado(relogio: RelogioControlado, sim: Any) -> None:  # A-11
    a, _x, _y, _pf = ae_recebido(relogio, sim)
    liberar(relogio, a)
    avisos = len(_avisos())
    assert _recusa(a, "ja_liberada") == "A retirada desta rodada já foi liberada."
    assert (len(_liberacoes()), len(_avisos())) == (1, avisos)


@pytest.mark.parametrize("etapa", ["interesse", "pagamento", "cancelada"])
def test_fora_de_aguardando_fornecedor(
    relogio: RelogioControlado, sim: Any, etapa: str
) -> None:  # A-12
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
    from apps.rodadas.models import Rodada

    a, _x, _y, _pf = ae_recebido(relogio, sim)
    if etapa == "cancelada":
        cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    else:
        Rodada.objects.filter(pk=a.rodada.pk).update(etapa=etapa)
    relogio.congelar(L)
    assert _recusa(a, "etapa") == "A retirada só é liberada quando a rodada aguarda o fornecedor."


def test_so_o_administrador_libera(relogio: RelogioControlado, sim: Any) -> None:  # A-13
    from apps.pedidos.liberacao_da_retirada import liberar_retirada

    a, _x, _y, _pf = ae_recebido(relogio, sim)
    conta_f = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    for autor in (a.a, conta_f, None):
        with pytest.raises(PermissionDenied):
            liberar_retirada(autor, a.rodada)
    assert not _liberacoes()
    assert _etapa(a) == "aguardando_fornecedor"


@pytest.mark.parametrize("com_reembolso", [True, False])
def test_a_rodada_liberada_nao_e_cancelada(
    relogio: RelogioControlado, sim: Any, com_reembolso: bool
) -> None:  # A-14
    from apps.pedidos.cancelamento_da_rodada import CancelamentoRecusado, cancelar_rodada
    from apps.pedidos.models import CancelamentoDaRodada

    a, _x, _y, _pf = ae_recebido(relogio, sim)
    liberar(relogio, a)
    avisos = Notificacao.objects.count()
    obrigacoes = ObrigacaoComComprador.objects.count()
    with pytest.raises(CancelamentoRecusado) as erro:
        cancelar_rodada(a.admin, a.rodada, com_reembolso=com_reembolso)
    assert erro.value.codigo == "rodada_encerrada"
    assert not CancelamentoDaRodada.objects.exists()
    assert (Notificacao.objects.count(), ObrigacaoComComprador.objects.count()) == (
        avisos,
        obrigacoes,
    )
    assert _etapa(a) == "disponivel_para_retirada"


def test_a_liberacao_nao_e_ato_financeiro(relogio: RelogioControlado, sim: Any) -> None:  # A-15
    from apps.pagamentos.models import PagamentoNoProvedor
    from apps.pedidos.models import (
        EnvioDoPedidoFormal,
        ItemDoPedido,
        Pedido,
        PedidoFormal,
        SituacaoDoPedido,
    )

    a, _x, _y, _pf = ae_recebido(relogio, sim)

    def foto() -> Any:
        return (
            list(Pedido.objects.values()),
            list(ItemDoPedido.objects.values()),
            list(SituacaoDoPedido.objects.values()),
            list(PagamentoNoProvedor.objects.values()),
            list(MovimentoFinanceiro.objects.values()),
            list(PedidoFormal.objects.values()),
            list(EnvioDoPedidoFormal.objects.values()),
        )

    antes = foto()
    liberar(relogio, a)
    assert foto() == antes


def test_a_previsao_deixa_de_ser_ajustavel(relogio: RelogioControlado, sim: Any) -> None:  # A-16
    from apps.pedidos.previsao_de_entrega import PrevisaoRecusada, ajustar_previsao_de_entrega

    a, _x, _y, _pf = ae_recebido(relogio, sim)
    liberar(relogio, a)
    with pytest.raises(PrevisaoRecusada) as erro:
        ajustar_previsao_de_entrega(a.admin, a.rodada, date(2026, 12, 1))
    assert erro.value.codigo == "fora_de_aguardando_fornecedor"


def test_o_repasse_continua_permitido(relogio: RelogioControlado, sim: Any) -> None:  # A-17
    from apps.pedidos.repasse import registrar_repasse

    a, _x, _y, _pf = ae_recebido(relogio, sim, liberacao_horas=0)
    liberar(relogio, a)
    movimento = registrar_repasse(
        a.admin, a.rodada, valor=D("10.00"), identificacao="pix-001", justificativa="Repasse"
    )
    assert movimento.pk is not None


def test_a_auditoria_da_liberacao(relogio: RelogioControlado, sim: Any) -> None:  # A-18
    a, _x, _y, _pf = ae_recebido(relogio, sim)
    liberacao = liberar(relogio, a)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.liberar_retirada")
    assert auditoria.autor_id == str(a.admin.pk)
    dados = auditoria.alteracoes
    assert dados["rodada"] == a.rodada.pk
    assert dados["liberada_em"] == L.isoformat().replace("+00:00", "Z")
    assert dados["prazo_final"] == PRAZO_FINAL.isoformat().replace("+00:00", "Z")
    assert dados["endereco"] == ENDERECO
    assert dados["liberacao"] == liberacao.pk
    assert len(dados["parcelas"]) == 5
    for parcela in dados["parcelas"]:
        assert parcela["situacao_anterior"] == "em_pedido"
        assert parcela["situacao_nova"] == "removida"
        assert D(parcela["reservada_anterior"]) > 0


def test_o_endereco_de_duas_linhas_no_aviso(relogio: RelogioControlado, sim: Any) -> None:  # A-19
    a, _x, _y, _pf = ae_recebido(relogio, sim, endereco=False)
    registrar_endereco(a.admin, "Rua A, 1\nFundos")
    liberar(relogio, a)
    assert all("Rua A, 1, Fundos" in n.corpo for n in _avisos())


# --- concorrência (A-20 a A-22) --------------------------------------------------------------


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_duas_liberacoes_em_paralelo(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-20
    from apps.pedidos import liberacao_da_retirada as modulo
    from apps.pedidos.liberacao_da_retirada import LiberacaoRecusada, liberar_retirada
    from tests.apoio.corrida import Corrida

    a, _x, _y, _pf = ae_recebido(relogio, simulador_pagamentos)
    relogio.congelar(L)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "registrar_auditoria")
    ra, rb = corrida.rodar(
        lambda: liberar_retirada(a.admin, a.rodada),
        lambda: liberar_retirada(a.admin, a.rodada),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert isinstance(rb.excecao, LiberacaoRecusada), repr(rb.excecao)
    assert rb.excecao.codigo == "ja_liberada"
    assert corrida.b_esperou
    assert (len(_liberacoes()), len(_avisos())) == (1, 2)


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_liberacao_e_cancelamento_em_paralelo(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-21
    from apps.pedidos import liberacao_da_retirada as modulo
    from apps.pedidos.cancelamento_da_rodada import CancelamentoRecusado, cancelar_rodada
    from apps.pedidos.liberacao_da_retirada import liberar_retirada
    from tests.apoio.corrida import Corrida

    a, _x, _y, _pf = ae_recebido(relogio, simulador_pagamentos)
    relogio.congelar(L)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "registrar_auditoria")
    ra, rb = corrida.rodar(
        lambda: liberar_retirada(a.admin, a.rodada),
        lambda: cancelar_rodada(a.admin, a.rodada, com_reembolso=False),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert isinstance(rb.excecao, CancelamentoRecusado), repr(rb.excecao)
    assert rb.excecao.codigo == "rodada_encerrada"
    assert corrida.b_esperou
    assert _etapa(a) == "disponivel_para_retirada"


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_liberacao_espera_a_ocorrencia_que_completa_o_recebimento(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-22
    from apps.pedidos import ocorrencias as ocorrencias_modulo
    from apps.pedidos.liberacao_da_retirada import liberar_retirada
    from tests.apoio.corrida import Corrida

    a, x, _y, _pf = arranjo_ae(relogio, simulador_pagamentos)
    registrar_endereco(a.admin)
    receber(a.admin, a.rodada, a.p1, D("9"))
    receber(a.admin, a.rodada, a.p2, D("12"))
    item = item_de(x, a.p1)
    relogio.congelar(L)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, ocorrencias_modulo, "registrar_auditoria")
    ra, rb = corrida.rodar(
        lambda: ocorrer(a.admin, item, D("2"), "faltante"),
        lambda: liberar_retirada(a.admin, a.rodada),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert rb.excecao is None, repr(rb.excecao)
    assert corrida.b_esperou
    assert _etapa(a) == "disponivel_para_retirada"
