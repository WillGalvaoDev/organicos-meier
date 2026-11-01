"""E11-01: início da apuração final (acceptance A-1 a A-21)."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.financeiro.devolucoes import autorizar_devolucao
from apps.financeiro.models import AlertaFinanceiro, ObrigacaoComComprador
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
from apps.pagamentos.models import ChamadaAoProvedor
from apps.pagamentos.provedor import obter_provedor
from apps.pedidos.models import (
    DestinoDoPagamento,
    ItemDoPedido,
    ParcelaNoPedido,
    Pedido,
    SituacaoDoPedido,
    TentativaDePagamento,
)
from tests.apoio.apuracao import H, arranjo_ap, cobranca, pagar
from tests.apoio.pedidos import T0, cancelar_direto
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
MS = timedelta(milliseconds=1)
PRAZO = T0 + 48 * H
ALERTA = "aprovado_no_prazo_depois_da_apuracao"


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


@pytest.fixture
def consultas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """As referências consultadas pela apuração, sem mudar o que a consulta faz."""
    from apps.pagamentos import consulta
    from apps.pedidos import apuracao

    registradas: list[str] = []
    original = consulta.consultar_antes_de_decidir

    def espiar(referencia: str) -> Any:
        registradas.append(referencia)
        return original(referencia)

    monkeypatch.setattr(apuracao, "consultar_antes_de_decidir", espiar)
    return registradas


def _receber_o_aviso(sim: Any, **entrega: Any) -> None:
    """O aviso é entregue e a tarefa consulta e sincroniza o pagamento."""
    sim.entregar_avisos(**entrega)
    processar_chamadas()


def _iniciar(a: Any) -> Any:
    from apps.pedidos.apuracao import iniciar_apuracao

    return iniciar_apuracao(a.admin, a.rodada)


def _foto() -> tuple[Any, ...]:
    from apps.pedidos.models import ApuracaoFinal

    return (
        ApuracaoFinal.objects.count(),
        list(
            SituacaoDoPedido.objects.order_by("pedido_id").values_list(
                "pedido_id", "situacao", "motivo_do_cancelamento", "cancelado_em"
            )
        ),
        ChamadaAoProvedor.objects.count(),
        EntradaAuditoria.objects.count(),
    )


def _situacao(pedido: Pedido) -> SituacaoDoPedido:
    return SituacaoDoPedido.objects.get(pedido=pedido)


def _alertas() -> list[AlertaFinanceiro]:
    return list(AlertaFinanceiro.objects.filter(tipo=ALERTA, resolvido_em=None))


def _composicao() -> tuple[Any, ...]:
    return (
        list(Pedido.objects.order_by("pk").values()),
        list(ItemDoPedido.objects.order_by("pk").values()),
        list(ParcelaNoPedido.objects.order_by("pk").values()),
    )


def _destinos(pedido: Pedido) -> list[tuple[str, str]]:
    return list(
        DestinoDoPagamento.objects.filter(pedido=pedido)
        .order_by("pk")
        .values_list("destino", "motivo")
    )


def test_antes_de_48_horas_e_recusada_sem_consulta_nem_escrita(
    relogio: RelogioControlado, sim: Any, consultas: list[str]
) -> None:  # A-1
    from apps.pedidos.apuracao import ApuracaoRecusada

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    pagar(relogio, sim, y)
    relogio.congelar(PRAZO - MS)
    antes = _foto()
    with pytest.raises(ApuracaoRecusada) as recusa:
        _iniciar(a)
    assert recusa.value.codigo == "antes_do_prazo"
    assert "04/11/2026" in str(recusa.value)
    assert "10:00" in str(recusa.value)
    assert "horário de Brasília" in str(recusa.value)
    assert consultas == []
    assert _foto() == antes


def test_em_48_horas_exatas_a_apuracao_e_aceita(relogio: RelogioControlado, sim: Any) -> None:
    # A-2
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    pagar(relogio, sim, y)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert apuracao.iniciada_em == PRAZO
    assert (apuracao.pedidos_pagos, apuracao.pedidos_nao_pagos) == (2, 0)
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "pagamento"


def test_so_o_administrador_apura(relogio: RelogioControlado) -> None:  # A-3
    from apps.pedidos.apuracao import iniciar_apuracao

    a, _, _ = arranjo_ap(relogio)
    relogio.congelar(PRAZO)
    antes = _foto()
    for autor in (a.a, ContaFactory.create(fornecedor=True), None):
        with pytest.raises(PermissionDenied):
            iniciar_apuracao(autor, a.rodada)
    assert _foto() == antes


def test_rodada_fora_de_pagamento_e_recusada(relogio: RelogioControlado) -> None:  # A-4
    from apps.pedidos.apuracao import ApuracaoRecusada, iniciar_apuracao

    a, _, _ = arranjo_ap(relogio)
    relogio.congelar(PRAZO)
    for etapa in ("fechamento_encerrado", "interesse"):
        a.rodada.etapa = etapa
        a.rodada.save(update_fields=["etapa"])
        antes = _foto()
        with pytest.raises(ApuracaoRecusada) as recusa:
            iniciar_apuracao(a.admin, a.rodada)
        assert recusa.value.codigo == "fora_de_pagamento"
        assert "etapa de pagamento" in str(recusa.value)
        assert _foto() == antes


def test_cancela_o_nao_pago_por_inadimplencia_e_audita(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert _situacao(x).situacao == "pago"
    cancelado = _situacao(y)
    assert (cancelado.situacao, cancelado.motivo_do_cancelamento) == ("cancelado", "inadimplencia")
    assert cancelado.cancelado_em == PRAZO
    assert (apuracao.pedidos_pagos, apuracao.pedidos_nao_pagos) == (1, 1)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.apuracao_final")
    assert auditoria.autor_id == str(a.admin.pk)
    dados = auditoria.alteracoes
    assert dados["rodada"] == a.rodada.pk
    assert dados["ciclo"] == a.ciclo.pk
    assert dados["pagos"] == [x.pk]
    assert dados["nao_pagos"] == [[y.pk, "aguardando_pagamento"]]
    assert dados["cancelados_agora"] == [y.pk]


def test_a_apuracao_nao_altera_a_composicao_do_pedido(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    antes = _composicao()
    _iniciar(a)
    assert _composicao() == antes


def test_cancelado_por_suspensao_continua_e_conta_como_nao_pago(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    cancelar_direto(y, "suspensao", T0 + 10 * H)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    cancelado = _situacao(y)
    assert (cancelado.situacao, cancelado.motivo_do_cancelamento) == ("cancelado", "suspensao")
    assert cancelado.cancelado_em == T0 + 10 * H
    assert (apuracao.pedidos_pagos, apuracao.pedidos_nao_pagos) == (1, 1)


def _y_com_cobranca_pendente(
    relogio: RelogioControlado, sim: Any
) -> tuple[Any, Pedido, Pedido, str, TentativaDePagamento]:
    """O arranjo do A-8: X pago e Y com uma tentativa `criada` (cobrança pendente no simulador)."""
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    return a, x, y, id_y, TentativaDePagamento.objects.get(pedido=y)


def _situacao_no_provedor(id_externo: str) -> str:
    return str(obter_provedor().consultar_pagamento(id_externo).situacao)


def test_cancela_no_provedor_antes_de_apurar(
    relogio: RelogioControlado, sim: Any, caplog: pytest.LogCaptureFixture
) -> None:  # A-8 (R03)
    from apps.pagamentos.models import PagamentoNoProvedor

    a, _x, y, id_y, tentativa = _y_com_cobranca_pendente(relogio, sim)
    relogio.congelar(PRAZO)
    caplog.set_level("INFO", logger="apps.simulador_pagamentos")
    _iniciar(a)
    assert _situacao_no_provedor(id_y) == "cancelado"
    assert PagamentoNoProvedor.objects.get(id_externo=id_y).situacao == "cancelado"
    chamada = ChamadaAoProvedor.objects.get(
        operacao="cancelar_cobranca", alvo=f"t{tentativa.pk}:apuracao"
    )
    assert chamada.situacao == "concluida"
    operacoes = [
        r.getMessage() for r in caplog.records if "Simulador de pagamentos" in r.getMessage()
    ]
    primeira_consulta = next(i for i, m in enumerate(operacoes) if "buscar_por_referencia" in m)
    cancelamento = next(i for i, m in enumerate(operacoes) if "cancelar_cobranca" in m)
    assert primeira_consulta < cancelamento
    cancelado = _situacao(y)
    assert (cancelado.situacao, cancelado.motivo_do_cancelamento) == ("cancelado", "inadimplencia")


def test_falha_do_cancelamento_bloqueia_a_apuracao(relogio: RelogioControlado, sim: Any) -> None:
    # A-22
    a, _x, y, id_y, tentativa = _y_com_cobranca_pendente(relogio, sim)
    relogio.congelar(PRAZO)
    antes = _foto()
    parcelas = _parcelas_do_fornecedor()
    sim.falhar_proximas(1, operacao="cancelar_cobranca")
    with pytest.raises(ConsultaAoProvedorFalhou) as erro:
        _iniciar(a)
    assert id_y in str(erro.value)
    assert _foto()[0] == 0
    assert _situacao(y).situacao == "aguardando_pagamento"
    assert _parcelas_do_fornecedor() == parcelas
    chamada = ChamadaAoProvedor.objects.get(
        operacao="cancelar_cobranca", alvo=f"t{tentativa.pk}:apuracao"
    )
    assert (chamada.situacao, bool(chamada.ultimo_erro)) == ("pendente", True)
    assert antes[0] == 0


def _parcelas_do_fornecedor() -> list[Any]:
    from apps.interesses.models import ParcelaDeInteresse

    return list(
        ParcelaDeInteresse.objects.order_by("pk").values_list(
            "pk", "situacao", "quantidade_reservada", "quantidade_pendente"
        )
    )


def test_pagamento_aprovado_na_resposta_do_cancelamento_quita_o_pedido(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-23
    a, _x, y, id_y, _ = _y_com_cobranca_pendente(relogio, sim)
    sim.aprovar_no_cancelamento(id_y, em=T0 + 47 * H)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert _situacao(y).situacao == "pago"
    assert (apuracao.pedidos_pagos, apuracao.pedidos_nao_pagos) == (2, 0)
    assert _destinos(y) == [("quita", "")]
    assert ObrigacaoComComprador.objects.filter(pedido=y).count() == 0


def test_cobranca_orfa_da_referencia_tambem_e_cancelada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-24
    from apps.pagamentos.provedor import NovaCobranca, obter_provedor

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(T0 + H)
    orfa = obter_provedor().criar_cobranca(
        NovaCobranca("orfa-y", y.referencia_externa, y.total, "Pedido", T0 + 25 * H)
    )
    id_orfa = orfa.pagamento.id_externo
    relogio.congelar(PRAZO)
    _iniciar(a)
    chamada = ChamadaAoProvedor.objects.get(
        operacao="cancelar_cobranca", alvo=f"{id_orfa}:apuracao"
    )
    assert chamada.situacao == "concluida"
    assert _situacao_no_provedor(id_orfa) == "cancelado"
    assert _situacao(y).situacao == "cancelado"


def _cancelamento_recusado(monkeypatch: pytest.MonkeyPatch, *, cancela_antes: bool) -> None:
    """Dublê do cancelamento recusado (`estado_invalido`); com `cancela_antes`, o provedor já o
    tinha cancelado."""
    from apps.pagamentos.provedor import RecusaDoProvedor
    from apps.simulador_pagamentos.provedor import ProvedorSimulado

    original = ProvedorSimulado.cancelar_cobranca

    def recusar(self: Any, id_externo: str) -> Any:
        if cancela_antes:
            original(self, id_externo)
        raise RecusaDoProvedor("estado_invalido")

    monkeypatch.setattr(ProvedorSimulado, "cancelar_cobranca", recusar)


def test_cancelamento_recusado_com_a_cobranca_ja_cancelada_segue(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-25
    a, _x, y, id_y, tentativa = _y_com_cobranca_pendente(relogio, sim)
    relogio.congelar(PRAZO)
    _cancelamento_recusado(monkeypatch, cancela_antes=True)
    _iniciar(a)
    chamada = ChamadaAoProvedor.objects.get(
        operacao="cancelar_cobranca", alvo=f"t{tentativa.pk}:apuracao"
    )
    assert chamada.situacao == "falhou"
    assert _situacao(y).motivo_do_cancelamento == "inadimplencia"
    assert _situacao_no_provedor(id_y) == "cancelado"


def test_cancelamento_recusado_com_a_cobranca_ainda_pendente_bloqueia(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-26
    a, _x, y, _id_y, _ = _y_com_cobranca_pendente(relogio, sim)
    relogio.congelar(PRAZO)
    _cancelamento_recusado(monkeypatch, cancela_antes=False)
    with pytest.raises(ConsultaAoProvedorFalhou):
        _iniciar(a)
    assert _foto()[0] == 0
    assert _situacao(y).situacao == "aguardando_pagamento"


def test_cobranca_que_reaparece_pendente_antes_da_decisao_recusa(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-27
    from apps.pagamentos.models import PagamentoNoProvedor
    from apps.pedidos import apuracao
    from apps.pedidos.apuracao import ApuracaoRecusada

    a, _x, y, id_y, _ = _y_com_cobranca_pendente(relogio, sim)
    relogio.congelar(PRAZO)
    original = apuracao._cancelar_no_provedor

    def cancelar_e_reabrir(*args: Any, **kwargs: Any) -> Any:
        resultado = original(*args, **kwargs)
        PagamentoNoProvedor.objects.filter(id_externo=id_y).update(situacao="pendente")
        return resultado

    monkeypatch.setattr(apuracao, "_cancelar_no_provedor", cancelar_e_reabrir)
    antes = _foto()
    with pytest.raises(ApuracaoRecusada) as recusa:
        _iniciar(a)
    assert recusa.value.codigo == "cobranca_aberta"
    assert str(recusa.value) == "Há cobrança ainda aberta no provedor; tente de novo."
    assert _foto() == antes
    assert _situacao(y).situacao == "aguardando_pagamento"


def test_chamada_do_bloqueio_pendente_nao_impede_a_da_apuracao(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-28
    from apps.pedidos.tarefas import bloquear_tentativas_vencidas_agora

    a, _x, _y, id_y, tentativa = _y_com_cobranca_pendente(relogio, sim)
    relogio.congelar(T0 + 25 * H)
    sim.falhar_proximas(1, operacao="cancelar_cobranca")
    bloquear_tentativas_vencidas_agora()
    processar_chamadas()
    do_bloqueio = ChamadaAoProvedor.objects.get(
        operacao="cancelar_cobranca", alvo=f"t{tentativa.pk}:prazo"
    )
    assert (do_bloqueio.situacao, bool(do_bloqueio.ultimo_erro)) == ("pendente", True)
    relogio.congelar(PRAZO)
    _iniciar(a)
    da_apuracao = ChamadaAoProvedor.objects.get(
        operacao="cancelar_cobranca", alvo=f"t{tentativa.pk}:apuracao"
    )
    assert da_apuracao.situacao == "concluida"
    do_bloqueio.refresh_from_db()
    assert do_bloqueio.situacao == "pendente"
    assert _situacao_no_provedor(id_y) == "cancelado"
    relogio.congelar(PRAZO + 2 * H)
    processar_chamadas()  # o segundo cancelamento encontra a cobrança já cancelada
    assert _situacao_no_provedor(id_y) == "cancelado"


def test_auditoria_lista_as_cobrancas_canceladas_no_provedor(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-29
    a, _x, _y, id_y, _ = _y_com_cobranca_pendente(relogio, sim)
    relogio.congelar(PRAZO)
    _iniciar(a)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.apuracao_final")
    assert auditoria.alteracoes["cobrancas_canceladas"] == [
        {"id_externo": id_y, "situacao": "cancelado"}
    ]


def test_reconsulta_registra_o_pagamento_aprovado_depois_de_48_horas(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    pagar(relogio, sim, y, quando=PRAZO + MS, entregar=False)
    relogio.congelar(T0 + 49 * H)
    _iniciar(a)
    assert _destinos(y) == [("devolucao", "aprovado_apos_a_margem")]
    obrigacao = ObrigacaoComComprador.objects.get(pedido=y)
    assert obrigacao.integral == y.total
    cancelado = _situacao(y)
    assert (cancelado.situacao, cancelado.motivo_do_cancelamento) == ("cancelado", "inadimplencia")


def test_reconsulta_quita_o_aprovado_em_48_horas_exatas(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-10
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    pagar(relogio, sim, y, quando=PRAZO, entregar=False)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert _situacao(y).situacao == "pago"
    assert (apuracao.pedidos_pagos, apuracao.pedidos_nao_pagos) == (2, 0)


def test_provedor_indisponivel_bloqueia_a_apuracao(relogio: RelogioControlado, sim: Any) -> None:
    # A-11
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    sim.falhar_proximas(1, operacao="buscar_por_referencia")
    with pytest.raises(ConsultaAoProvedorFalhou):
        _iniciar(a)
    assert _foto()[0] == 0
    assert _situacao(y).situacao == "aguardando_pagamento"
    assert ChamadaAoProvedor.objects.filter(operacao="cancelar_cobranca").count() == 0


@pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])
def test_dentro_de_transacao_de_quem_chama_e_recusada(
    relogio: RelogioControlado, simulador_pagamentos: Any, consultas: list[str]
) -> None:  # A-12
    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    relogio.congelar(PRAZO)
    antes = _foto()
    with pytest.raises(RuntimeError, match="durable"):
        with transaction.atomic():
            _iniciar(a)
    assert consultas == []
    assert _foto() == antes


def test_apurar_de_novo_e_recusado(relogio: RelogioControlado, sim: Any) -> None:  # A-13
    from apps.pedidos.apuracao import ApuracaoRecusada

    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    _iniciar(a)
    antes = _foto()
    with pytest.raises(ApuracaoRecusada) as recusa:
        _iniciar(a)
    assert recusa.value.codigo == "ja_apurada"
    assert str(recusa.value) == "A apuração deste ciclo já foi feita."
    assert _foto() == antes


# --- pagamento informado depois da apuração (A-17 a A-21) ----------------------------------------


def _apurada_com_cobranca_de_y(
    relogio: RelogioControlado, sim: Any, aprovada_em: Any
) -> tuple[Any, Pedido, Pedido, str]:
    """AP-viável; X pago; a cobrança de Y criada em `T0 + 1h` e aprovada no simulador em
    `aprovada_em` (sem aviso); a apuração feita em `T0 + 48h`."""
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    relogio.congelar(PRAZO)
    _iniciar(a)
    sim.aprovar(id_y, em=aprovada_em)
    return a, x, y, id_y


def test_pagamento_no_prazo_informado_depois_da_apuracao_vira_devolucao_e_alerta(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-17
    a, _x, y, _ = _apurada_com_cobranca_de_y(relogio, sim, PRAZO - timedelta(minutes=1))
    antes = _composicao()
    relogio.congelar(T0 + 50 * H)
    _receber_o_aviso(sim)
    cancelado = _situacao(y)
    assert (cancelado.situacao, cancelado.motivo_do_cancelamento) == ("cancelado", "inadimplencia")
    assert cancelado.quitado_em is None
    assert _destinos(y) == [("devolucao", "pedido_cancelado")]
    obrigacao = ObrigacaoComComprador.objects.get(pedido=y)
    assert obrigacao.integral == y.total
    (alerta,) = _alertas()
    assert alerta.gravidade == "critico"
    assert alerta.dados["pedido"] == y.pk
    assert alerta.dados["comprador"] == a.b.pk
    assert Decimal(str(alerta.dados["valor"])) == y.total
    assert "aprovado_em" in alerta.dados
    assert _composicao() == antes


def test_aviso_repetido_nao_repete_destino_obrigacao_nem_alerta(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-18
    _a, _x, y, _ = _apurada_com_cobranca_de_y(relogio, sim, PRAZO - timedelta(minutes=1))
    relogio.congelar(T0 + 50 * H)
    _receber_o_aviso(sim, vezes=3)
    assert len(_destinos(y)) == 1
    assert ObrigacaoComComprador.objects.filter(pedido=y).count() == 1
    assert len(_alertas()) == 1


def test_aprovado_depois_da_margem_nao_abre_o_alerta_do_prazo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-19
    _a, _x, y, _ = _apurada_com_cobranca_de_y(relogio, sim, T0 + 49 * H)
    relogio.congelar(T0 + 50 * H)
    _receber_o_aviso(sim)
    assert _destinos(y) == [("devolucao", "aprovado_apos_a_margem")]
    assert _alertas() == []


def test_cancelamento_por_suspensao_antes_da_apuracao_nao_quita_depois_dela(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-20
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    cancelar_direto(y, "suspensao", T0 + 30 * H)
    relogio.congelar(PRAZO)
    _iniciar(a)
    sim.aprovar(id_y, em=T0 + 29 * H)
    relogio.congelar(T0 + 50 * H)
    _receber_o_aviso(sim)
    cancelado = _situacao(y)
    assert (cancelado.situacao, cancelado.motivo_do_cancelamento) == ("cancelado", "suspensao")
    assert _destinos(y) == [("devolucao", "pedido_cancelado")]
    assert len(_alertas()) == 1


def test_devolucao_concluida_resolve_o_alerta(relogio: RelogioControlado, sim: Any) -> None:
    # A-21
    a, _x, y, _ = _apurada_com_cobranca_de_y(relogio, sim, PRAZO - timedelta(minutes=1))
    relogio.congelar(T0 + 50 * H)
    _receber_o_aviso(sim)
    assert len(_alertas()) == 1
    obrigacao = ObrigacaoComComprador.objects.get(pedido=y)
    autorizar_devolucao(obrigacao, autor=a.admin)
    processar_chamadas()
    assert _alertas() == []
    resolvido = AlertaFinanceiro.objects.get(tipo=ALERTA)
    assert resolvido.motivo_da_resolucao == "devolução concluída"


# --- concorrência (A-14 a A-16) -------------------------------------------------------------------

COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_duas_apuracoes_em_paralelo_gravam_uma(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-14
    from apps.pedidos import apuracao
    from apps.pedidos.apuracao import ApuracaoRecusada
    from apps.pedidos.models import ApuracaoFinal
    from tests.apoio.corrida import Corrida

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    relogio.congelar(PRAZO)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, apuracao, "_gravar_a_apuracao")
    ra, rb = corrida.rodar(
        lambda: apuracao.iniciar_apuracao(a.admin, a.rodada),
        lambda: apuracao.iniciar_apuracao(a.admin, a.rodada),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert isinstance(rb.excecao, ApuracaoRecusada), rb.excecao
    assert rb.excecao.codigo == "ja_apurada"
    assert ApuracaoFinal.objects.count() == 1
    assert _situacao(y).situacao == "cancelado"
    assert EntradaAuditoria.objects.filter(acao="rodada.apuracao_final").count() == 1


def _reconsulta_de_y_pendente(monkeypatch: pytest.MonkeyPatch, y: Pedido) -> None:
    """Dublê da consulta só na reconsulta da apuração: a de Y não vê a aprovação."""
    from apps.pagamentos import consulta
    from apps.pedidos import apuracao

    original = consulta.consultar_antes_de_decidir

    def reconsultar(referencia: str) -> Any:
        if referencia == y.referencia_externa:
            return []
        return original(referencia)

    monkeypatch.setattr(apuracao, "consultar_antes_de_decidir", reconsultar)


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_aviso_antes_da_apuracao_quita_y(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-15 (i)
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    pagar(relogio, simulador_pagamentos, y, quando=T0 + 47 * H)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert _situacao(y).situacao == "pago"
    assert apuracao.pedidos_pagos == 2
    assert _destinos(y) == [("quita", "")]


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_apuracao_espera_o_aviso_que_trava_a_situacao_de_y(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-15 (ii)
    from apps.pedidos import apuracao, quitacao
    from apps.pedidos.models import ApuracaoFinal
    from tests.apoio.corrida import Corrida

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    pagar(relogio, simulador_pagamentos, y, quando=T0 + 47 * H, entregar=False)
    relogio.congelar(PRAZO)
    _reconsulta_de_y_pendente(monkeypatch, y)
    corrida = Corrida()
    corrida.antes_de(monkeypatch, quitacao, "_motivo_da_devolucao")
    ra, rb = corrida.rodar(
        lambda: _receber_o_aviso(simulador_pagamentos),
        lambda: apuracao.iniciar_apuracao(a.admin, a.rodada),
        b_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    assert _situacao(y).situacao == "pago"
    assert ApuracaoFinal.objects.get().pedidos_pagos == 2
    assert _destinos(y) == [("quita", "")]


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_aviso_espera_a_apuracao_que_ja_cancelou_y(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-16
    from apps.pedidos import apuracao
    from tests.apoio.corrida import Corrida

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    pagar(relogio, simulador_pagamentos, y, quando=T0 + 47 * H, entregar=False)
    relogio.congelar(PRAZO)
    _reconsulta_de_y_pendente(monkeypatch, y)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, apuracao, "_cancelar_os_nao_pagos")
    ra, rb = corrida.rodar(
        lambda: apuracao.iniciar_apuracao(a.admin, a.rodada),
        lambda: _receber_o_aviso(simulador_pagamentos),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    cancelado = _situacao(y)
    assert (cancelado.situacao, cancelado.motivo_do_cancelamento) == ("cancelado", "inadimplencia")
    assert _destinos(y) == [("devolucao", "pedido_cancelado")]
    assert ObrigacaoComComprador.objects.get(pedido=y).integral == D("106.15")
    assert len(_alertas()) == 1
