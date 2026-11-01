"""E12-02: cancelamento da rodada com pedidos (acceptance A-1 a A-16)."""

from decimal import Decimal
from typing import Any

import pytest

from apps.financeiro.models import ContaFinanceira, MovimentoFinanceiro, ObrigacaoComComprador
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor
from apps.pagamentos.provedor import NovaCobranca, obter_provedor
from apps.pedidos.models import (
    ApuracaoFinal,
    ItemDoPedido,
    ParcelaNoPedido,
    Pedido,
    SituacaoDoPedido,
    TentativaDePagamento,
)
from apps.rodadas.models import Rodada
from tests.apoio.apuracao import H, arranjo_ap, cobranca, pagar
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _cancelar(a: Any, **kwargs: Any) -> Any:
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    kwargs.setdefault("com_reembolso", False)
    return cancelar_rodada(a.admin, a.rodada, **kwargs)


def _situacao(pedido: Pedido) -> SituacaoDoPedido:
    return SituacaoDoPedido.objects.get(pedido=pedido)


def _composicao() -> tuple[Any, ...]:
    return (
        list(Pedido.objects.order_by("pk").values()),
        list(ItemDoPedido.objects.order_by("pk").values()),
        list(ParcelaNoPedido.objects.order_by("pk").values()),
    )


def _livro() -> tuple[Any, ...]:
    from apps.financeiro.livro import saldo

    return (
        MovimentoFinanceiro.objects.count(),
        {c.pk: saldo(c) for c in ContaFinanceira.objects.all()},
        list(ObrigacaoComComprador.objects.order_by("pk").values()),
    )


def _situacao_no_provedor(id_externo: str) -> str:
    return str(obter_provedor().consultar_pagamento(id_externo).situacao)


def test_cancela_o_nao_pago_e_preserva_o_pago(relogio: RelogioControlado, sim: Any) -> None:
    # A-1
    from apps.interesses.consultas import total_reservado
    from apps.interesses.models import ParcelaDeInteresse

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    _cancelar(a)
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "cancelada"
    assert _situacao(x).situacao == "pago"
    cancelado = _situacao(y)
    assert (cancelado.situacao, cancelado.motivo_do_cancelamento, cancelado.cancelado_em) == (
        "cancelado",
        "cancelamento_da_rodada",
        T0 + 2 * H,
    )
    assert {p.situacao for p in ParcelaDeInteresse.objects.filter(comprador__in=[a.a, a.b])} == {
        "removida"
    }
    assert total_reservado(a.p1) == D("0")
    assert total_reservado(a.p2) == D("0")


def test_a_composicao_dos_pedidos_nao_muda(relogio: RelogioControlado, sim: Any) -> None:
    # A-2
    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    antes = _composicao()
    _cancelar(a)
    assert _composicao() == antes


def test_parcela_com_pendente_continua_na_fila(relogio: RelogioControlado, sim: Any) -> None:
    # A-3
    from apps.interesses.models import ParcelaDeInteresse

    a, x, _y = arranjo_ap(relogio, pendente_a_p1=2)
    pagar(relogio, sim, x)
    (parcela,) = ParcelaDeInteresse.objects.filter(comprador=a.a, produto=a.p1)
    sequencia = parcela.sequencia
    _cancelar(a)
    parcela.refresh_from_db()
    assert (
        parcela.situacao,
        parcela.quantidade_pendente,
        parcela.quantidade_reservada,
        parcela.sequencia,
    ) == ("pendente", D("2"), D("0"), sequencia)


def test_a_cobranca_pendente_de_uma_tentativa_e_cancelada_depois_do_commit(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    from apps.pagamentos.models import PagamentoNoProvedor

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    tentativa = TentativaDePagamento.objects.get(pedido=y)
    _cancelar(a)
    chamada = ChamadaAoProvedor.objects.get(
        operacao="cancelar_cobranca", alvo=f"t{tentativa.pk}:cancelamento_da_rodada"
    )
    assert chamada.situacao == "pendente"
    assert _situacao_no_provedor(id_y) == "pendente"
    processar_chamadas()
    assert _situacao_no_provedor(id_y) == "cancelado"
    assert PagamentoNoProvedor.objects.get(id_externo=id_y).situacao == "cancelado"


def _cobranca_orfa(relogio: RelogioControlado, y: Pedido) -> str:
    from apps.pagamentos.consulta import consultar_antes_de_decidir

    relogio.congelar(T0 + H)
    orfa = obter_provedor().criar_cobranca(
        NovaCobranca("orfa-y", y.referencia_externa, y.total, "Pedido", T0 + 25 * H)
    )
    consultar_antes_de_decidir(y.referencia_externa)  # registra a cobrança, sem tentativa
    return orfa.pagamento.id_externo


def test_a_cobranca_orfa_da_referencia_tambem_e_cancelada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_orfa = _cobranca_orfa(relogio, y)
    relogio.congelar(T0 + 2 * H)
    _cancelar(a)
    chamada = ChamadaAoProvedor.objects.get(
        operacao="cancelar_cobranca", alvo=f"{id_orfa}:cancelamento_da_rodada"
    )
    assert chamada.situacao == "pendente"
    processar_chamadas()
    assert _situacao_no_provedor(id_orfa) == "cancelado"


def test_a_tentativa_solicitada_nao_recebe_cancelamento_e_a_criacao_e_recusada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    from apps.pedidos.pagamento import pedir_pagamento

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(T0 + 2 * H)
    tentativa = pedir_pagamento(a.b, y)
    assert tentativa.situacao == "solicitada"
    _cancelar(a)
    assert not ChamadaAoProvedor.objects.filter(
        operacao="cancelar_cobranca", alvo__endswith=":cancelamento_da_rodada"
    ).exists()
    processar_chamadas()
    tentativa.refresh_from_db()
    assert tentativa.situacao == "nao_criada"
    chamada = ChamadaAoProvedor.objects.get(operacao="criar_cobranca")
    assert "pedido_cancelado" in (chamada.ultimo_erro or "")
    assert tuple(obter_provedor().buscar_por_referencia(y.referencia_externa)) == ()


def test_pedir_pagamento_depois_do_cancelamento_e_recusado(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    from apps.pedidos.pagamento import PagamentoRecusado, pedir_pagamento

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    _cancelar(a)
    tentativas = TentativaDePagamento.objects.count()
    chamadas = ChamadaAoProvedor.objects.count()
    for comprador, pedido in ((a.b, y), (a.a, x)):
        with pytest.raises(PagamentoRecusado) as recusa:
            pedir_pagamento(comprador, pedido)
        assert recusa.value.codigo == "rodada_cancelada"
        assert str(recusa.value) == (
            "A rodada foi cancelada pelo administrador; não há pagamento a fazer."
        )
    assert TentativaDePagamento.objects.count() == tentativas
    assert ChamadaAoProvedor.objects.count() == chamadas


def test_a_apuracao_recusa_a_rodada_cancelada(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-8
    from apps.pedidos import apuracao
    from apps.pedidos.apuracao import ApuracaoRecusada, iniciar_apuracao

    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    _cancelar(a)
    consultadas: list[str] = []
    monkeypatch.setattr(
        apuracao, "consultar_antes_de_decidir", lambda referencia: consultadas.append(referencia)
    )
    relogio.congelar(PRAZO)
    with pytest.raises(ApuracaoRecusada) as recusa:
        iniciar_apuracao(a.admin, a.rodada)
    assert recusa.value.codigo == "fora_de_pagamento"
    assert consultadas == []
    assert ApuracaoFinal.objects.count() == 0


def test_a_aprovacao_recusa_a_rodada_cancelada(relogio: RelogioControlado, sim: Any) -> None:
    # A-9
    from apps.financeiro.models import ApuracaoNoLivro
    from apps.pedidos.apuracao import ApuracaoRecusada, aprovar_resultado, iniciar_apuracao
    from apps.pedidos.models import AprovacaoDoResultado

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    pagar(relogio, sim, y)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    _cancelar(a)
    with pytest.raises(ApuracaoRecusada) as recusa:
        aprovar_resultado(a.admin, a.rodada)
    assert recusa.value.codigo == "fora_de_pagamento"
    assert ApuracaoNoLivro.objects.count() == 0
    assert AprovacaoDoResultado.objects.count() == 0


def test_as_tarefas_da_linha_do_tempo_ignoram_a_rodada_cancelada(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-10
    from apps.pedidos import tarefas
    from apps.pedidos.tarefas import (
        bloquear_tentativas_vencidas_agora,
        reconsultar_pagamentos_da_margem_agora,
    )

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    cobranca(relogio, y)
    _cancelar(a)
    processar_chamadas()
    consultadas: list[str] = []
    monkeypatch.setattr(
        tarefas, "consultar_antes_de_decidir", lambda referencia: consultadas.append(referencia)
    )
    chamadas = ChamadaAoProvedor.objects.count()
    relogio.congelar(T0 + 25 * H)
    bloquear_tentativas_vencidas_agora()
    reconsultar_pagamentos_da_margem_agora()
    assert ChamadaAoProvedor.objects.count() == chamadas
    assert not ChamadaAoProvedor.objects.filter(alvo__endswith=":prazo").exists()
    assert consultadas == []


def test_pagamento_em_duplicidade_continua_como_estava(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-11 (regressão)
    from apps.pedidos.models import DestinoDoPagamento

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    pagar(relogio, sim, y)
    relogio.congelar(T0 + H)
    dup = obter_provedor().criar_cobranca(
        NovaCobranca("dup-y", y.referencia_externa, y.total, "Pedido", T0 + 25 * H)
    )
    relogio.congelar(T0 + 3 * H)
    sim.aprovar(dup.pagamento.id_externo, em=T0 + 3 * H)
    sim.entregar_avisos()
    processar_chamadas()
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=dup.pagamento.id_externo)
    assert (destino.destino, destino.motivo) == ("devolucao", "duplicidade")
    antes = _livro()
    obrigacoes = ObrigacaoComComprador.objects.count()
    _cancelar(a, com_reembolso=False)
    assert ObrigacaoComComprador.objects.count() == obrigacoes
    assert _livro() == antes


def test_rodada_aprovada_cancelada_sem_reembolso_nao_mexe_no_livro(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    from apps.financeiro.models import ApuracaoNoLivro
    from apps.pedidos.apuracao import aprovar_resultado, iniciar_apuracao

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    pagar(relogio, sim, y)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    aprovar_resultado(a.admin, a.rodada)
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "aguardando_fornecedor"
    antes = _livro()
    apuracoes = list(ApuracaoNoLivro.objects.order_by("pk").values())
    _cancelar(a, com_reembolso=False)
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "cancelada"
    assert _livro() == antes
    assert list(ApuracaoNoLivro.objects.order_by("pk").values()) == apuracoes


def test_pedido_cancelado_por_inadimplencia_mantem_o_motivo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-13
    from apps.pedidos.apuracao import iniciar_apuracao

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    antes = _situacao(y)
    assert antes.motivo_do_cancelamento == "inadimplencia"
    _cancelar(a)
    depois = _situacao(y)
    assert (depois.situacao, depois.motivo_do_cancelamento, depois.cancelado_em) == (
        "cancelado",
        "inadimplencia",
        antes.cancelado_em,
    )


def test_a_auditoria_lista_pedidos_pagos_e_cobrancas(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-14
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    tentativa = TentativaDePagamento.objects.get(pedido=y)
    _cancelar(a)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.cancelar")
    dados = auditoria.alteracoes
    assert dados["pedidos_cancelados"] == [
        {"pedido": y.pk, "situacao_anterior": "aguardando_pagamento"}
    ]
    assert dados["pedidos_pagos"] == [x.pk]
    assert dados["cobrancas"] == [
        {"alvo": f"t{tentativa.pk}:cancelamento_da_rodada", "id_externo": id_y}
    ]


# --- concorrência (A-15 e A-16) -------------------------------------------------------------------


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_cancelamento_espera_o_pedido_de_pagamento_que_ja_travou(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-15 (i)
    from apps.pedidos import pagamento
    from tests.apoio.corrida import Corrida

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    relogio.congelar(T0 + 2 * H)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, pagamento, "tentativa_aberta")
    ra, rb = corrida.rodar(
        lambda: pagamento.pedir_pagamento(a.b, y),
        lambda: _cancelar(a),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    assert _situacao(y).situacao == "cancelado"
    processar_chamadas()
    assert tuple(obter_provedor().buscar_por_referencia(y.referencia_externa)) == ()


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_pedido_de_pagamento_espera_o_cancelamento_que_ja_travou(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-15 (ii)
    from apps.pedidos import cancelamento_da_rodada as modulo
    from apps.pedidos import pagamento
    from tests.apoio.corrida import Corrida

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    relogio.congelar(T0 + 2 * H)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "_gravar_o_cancelamento")
    ra, rb = corrida.rodar(
        lambda: _cancelar(a),
        lambda: pagamento.pedir_pagamento(a.b, y),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert isinstance(rb.excecao, pagamento.PagamentoRecusado), rb.excecao
    assert rb.excecao.codigo == "rodada_cancelada"
    assert corrida.b_esperou
    assert tuple(obter_provedor().buscar_por_referencia(y.referencia_externa)) == ()


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_cancelamento_espera_a_apuracao_que_ja_travou(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-16 (i)
    from apps.pedidos import apuracao
    from tests.apoio.corrida import Corrida

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    relogio.congelar(PRAZO)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, apuracao, "_gravar_a_apuracao")
    ra, rb = corrida.rodar(
        lambda: apuracao.iniciar_apuracao(a.admin, a.rodada),
        lambda: _cancelar(a),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    cancelado = _situacao(y)
    assert (cancelado.situacao, cancelado.motivo_do_cancelamento) == ("cancelado", "inadimplencia")
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "cancelada"


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_apuracao_espera_o_cancelamento_que_ja_travou(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-16 (ii)
    from apps.pedidos import apuracao
    from apps.pedidos import cancelamento_da_rodada as modulo
    from tests.apoio.corrida import Corrida

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    relogio.congelar(PRAZO)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "_gravar_o_cancelamento")
    ra, rb = corrida.rodar(
        lambda: _cancelar(a),
        lambda: apuracao.iniciar_apuracao(a.admin, a.rodada),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert isinstance(rb.excecao, apuracao.ApuracaoRecusada), rb.excecao
    assert rb.excecao.codigo == "fora_de_pagamento"
    assert corrida.b_esperou
    cancelado = _situacao(y)
    assert (cancelado.situacao, cancelado.motivo_do_cancelamento) == (
        "cancelado",
        "cancelamento_da_rodada",
    )
