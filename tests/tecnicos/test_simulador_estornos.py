"""E10-03: estorno, consulta de estornos e contestação no provedor e no simulador (A-1 a A-20)."""

# A spec fixa `ValueError` sem mensagem nos controles; o tipo é o contrato.
# ruff: noqa: PT011

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier
from typing import Any

import pytest

from apps.pagamentos.provedor import (
    EstornoConsultado,
    MovimentoNoProvedor,
    NovaCobranca,
    NovoEstorno,
    PagamentoNaoEncontrado,
    ProvedorIndisponivel,
    RecusaDoProvedor,
    SaldoInsuficienteParaEstorno,
    SituacaoDoEstorno,
    SituacaoNoProvedor,
    TipoDeMovimentoNoProvedor,
    obter_provedor,
)
from apps.simulador_pagamentos.models import AvisoSimulado, EstornoSimulado, MovimentoSimulado
from tests.apoio.concorrencia import executar_em_paralelo
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
T = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)
DIA = timedelta(days=1)


def _desde_sempre() -> tuple[datetime, datetime]:
    return T - 400 * DIA, T + 400 * DIA


def _movimentos(tipo: TipoDeMovimentoNoProvedor | None = None) -> list[MovimentoNoProvedor]:
    movimentos = obter_provedor().listar_movimentos(*_desde_sempre())
    return [m for m in movimentos if tipo is None or m.tipo == tipo]


def _cobranca(sim: Any, *, aporte: bool = True) -> str:
    """P1: 125,00 pelo Pix, aprovado em T, tarifa de 1,25 e liberação imediata, mais um aporte."""
    sim.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    sim.definir_liberacao("pix", horas=0)
    criada = obter_provedor().criar_cobranca(
        NovaCobranca("c1", "ref-1", D("125.00"), "Pedido", T + DIA)
    )
    id_externo = criada.pagamento.id_externo
    sim.aprovar(id_externo)
    if aporte:
        sim.depositar(D("1000.00"))
    return id_externo


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    relogio.congelar(T)
    return simulador_pagamentos


@pytest.fixture
def p1(sim: Any) -> str:
    return _cobranca(sim)


def estornar(id_externo: str, valor: str, chave: str) -> EstornoConsultado:
    return obter_provedor().estornar(NovoEstorno(id_externo, D(valor), chave))


def _saldo_liberado() -> Decimal:
    return obter_provedor().consultar_saldo().liberado


def _sem_efeito(antes: int | None = None) -> None:
    assert EstornoSimulado.objects.count() == (antes or 0)
    assert not _movimentos(TipoDeMovimentoNoProvedor.DEVOLUCAO)


def test_estorno_total_conclui_e_debita_so_o_valor(p1: str) -> None:  # A-1
    saldo_antes = _saldo_liberado()
    estorno = estornar(p1, "125.00", "k1")
    assert estorno.situacao == SituacaoDoEstorno.CONCLUIDO
    assert estorno.id_estorno.startswith("sim-est-")
    assert (estorno.id_externo, estorno.valor, estorno.codigo) == (p1, D("125.00"), None)
    assert (estorno.criado_em, estorno.concluido_em) == (T, T)
    (movimento,) = _movimentos(TipoDeMovimentoNoProvedor.DEVOLUCAO)
    assert movimento.valor == D("-125.00")
    assert movimento.id_externo == p1
    assert movimento.id_estorno == estorno.id_estorno
    assert movimento.descricao_no_provedor == "refund"
    assert _saldo_liberado() == saldo_antes - D("125.00")
    (tarifa,) = _movimentos(TipoDeMovimentoNoProvedor.TARIFA)
    assert tarifa.valor == D("-1.25")


def test_dois_estornos_parciais_e_a_consulta_em_ordem(p1: str) -> None:  # A-2
    primeiro = estornar(p1, "25.00", "k1")
    segundo = estornar(p1, "100.00", "k2")
    assert len(_movimentos(TipoDeMovimentoNoProvedor.DEVOLUCAO)) == 2
    consultados = obter_provedor().consultar_estornos(p1)
    assert [e.id_estorno for e in consultados] == [primeiro.id_estorno, segundo.id_estorno]
    assert all(e.situacao == SituacaoDoEstorno.CONCLUIDO for e in consultados)


def test_mesma_chave_devolve_o_mesmo_estorno(p1: str) -> None:  # A-3
    primeiro = estornar(p1, "25.00", "k1")
    segundo = estornar(p1, "25.00", "k1")
    assert segundo.id_estorno == primeiro.id_estorno
    assert EstornoSimulado.objects.count() == 1
    assert len(_movimentos(TipoDeMovimentoNoProvedor.DEVOLUCAO)) == 1


def test_chave_reutilizada_com_outro_valor_e_recusada(p1: str) -> None:  # A-4
    estornar(p1, "25.00", "k1")
    with pytest.raises(RecusaDoProvedor) as erro:
        estornar(p1, "30.00", "k1")
    assert erro.value.codigo == "chave_em_uso"
    assert EstornoSimulado.objects.count() == 1
    assert len(_movimentos(TipoDeMovimentoNoProvedor.DEVOLUCAO)) == 1


def test_falha_depois_de_executar_deixa_o_estorno_gravado(p1: str, sim: Any) -> None:  # A-5
    sim.falhar_proximas(1, operacao="estornar", depois_de_executar=True)
    with pytest.raises(ProvedorIndisponivel):
        estornar(p1, "25.00", "k1")
    assert EstornoSimulado.objects.count() == 1
    repetido = estornar(p1, "25.00", "k1")
    assert repetido.id_estorno == EstornoSimulado.objects.get().id_estorno
    assert len(_movimentos(TipoDeMovimentoNoProvedor.DEVOLUCAO)) == 1


def test_provedor_indisponivel_nada_grava(p1: str, sim: Any) -> None:  # A-6
    sim.indisponivel()
    with pytest.raises(ProvedorIndisponivel):
        estornar(p1, "25.00", "k1")
    with pytest.raises(ProvedorIndisponivel):
        obter_provedor().consultar_estornos(p1)
    sim.normalizar()
    _sem_efeito()


def test_saldo_insuficiente_nao_e_recusa_definitiva(sim: Any) -> None:  # A-7
    p1 = _cobranca(sim, aporte=False)
    assert _saldo_liberado() == D("123.75")
    with pytest.raises(SaldoInsuficienteParaEstorno):
        estornar(p1, "125.00", "k1")
    _sem_efeito()
    sim.depositar(D("50.00"))
    assert estornar(p1, "125.00", "k1").situacao == SituacaoDoEstorno.CONCLUIDO


def test_prazo_de_180_dias(p1: str, relogio: RelogioControlado) -> None:  # A-8
    relogio.congelar(T + 181 * DIA)
    with pytest.raises(RecusaDoProvedor) as erro:
        estornar(p1, "10.00", "k1")
    assert erro.value.codigo == "prazo_vencido"
    relogio.congelar(T + 180 * DIA)
    assert estornar(p1, "10.00", "k2").situacao == SituacaoDoEstorno.CONCLUIDO


def test_recusa_programada(p1: str, sim: Any) -> None:  # A-9
    sim.recusar_estornos(p1, "meio_nao_permite_estorno")
    with pytest.raises(RecusaDoProvedor) as erro:
        estornar(p1, "25.00", "k1")
    assert erro.value.codigo == "meio_nao_permite_estorno"
    _sem_efeito()


def test_provedor_sem_estorno_parcial(p1: str, sim: Any) -> None:  # A-10
    sim.sem_estorno_parcial(p1)
    with pytest.raises(RecusaDoProvedor) as erro:
        estornar(p1, "25.00", "k1")
    assert erro.value.codigo == "parcial_nao_suportado"
    assert estornar(p1, "125.00", "k2").situacao == SituacaoDoEstorno.CONCLUIDO


def test_estorno_nao_passa_do_restante(p1: str) -> None:  # A-11
    estornar(p1, "100.00", "k1")
    with pytest.raises(RecusaDoProvedor) as erro:
        estornar(p1, "30.00", "k2")
    assert erro.value.codigo == "valor_acima_do_disponivel"


def test_estorno_em_processamento_conclui_depois(
    p1: str, sim: Any, relogio: RelogioControlado
) -> None:  # A-12
    sim.estornos_em_processamento(p1)
    estorno = estornar(p1, "25.00", "k1")
    assert estorno.situacao == SituacaoDoEstorno.EM_PROCESSAMENTO
    assert estorno.concluido_em is None
    assert not _movimentos(TipoDeMovimentoNoProvedor.DEVOLUCAO)
    (visto,) = obter_provedor().consultar_estornos(p1)
    assert visto.situacao == SituacaoDoEstorno.EM_PROCESSAMENTO
    relogio.congelar(T + timedelta(hours=2))
    sim.concluir_estorno(estorno.id_estorno)
    (concluido,) = obter_provedor().consultar_estornos(p1)
    assert concluido.situacao == SituacaoDoEstorno.CONCLUIDO
    assert concluido.concluido_em == T + timedelta(hours=2)
    (movimento,) = _movimentos(TipoDeMovimentoNoProvedor.DEVOLUCAO)
    assert movimento.ocorrido_em == T + timedelta(hours=2)
    assert movimento.id_estorno == estorno.id_estorno


def test_estorno_recusado_depois_libera_o_restante(p1: str, sim: Any) -> None:  # A-13
    sim.estornos_em_processamento(p1)
    estorno = estornar(p1, "25.00", "k1")
    sim.recusar_estorno(estorno.id_estorno, "estado_invalido")
    (visto,) = obter_provedor().consultar_estornos(p1)
    assert (visto.situacao, visto.codigo) == (SituacaoDoEstorno.RECUSADO, "estado_invalido")
    assert not _movimentos(TipoDeMovimentoNoProvedor.DEVOLUCAO)
    # o recusado não conta: o restante volta a ser os 125,00 inteiros (o controle ainda vale)
    assert estornar(p1, "125.00", "k2").situacao == SituacaoDoEstorno.EM_PROCESSAMENTO


def test_recusa_que_o_provedor_conclui_depois_fica_invisivel(p1: str, sim: Any) -> None:  # A-14
    sim.recusar_mas_processar(p1, "meio_nao_permite_estorno")
    with pytest.raises(RecusaDoProvedor) as erro:
        estornar(p1, "25.00", "k1")
    assert erro.value.codigo == "meio_nao_permite_estorno"
    assert obter_provedor().consultar_estornos(p1) == []
    invisivel = EstornoSimulado.objects.get()
    assert invisivel.situacao == "em_processamento"
    sim.concluir_estorno(invisivel.id_estorno)
    (visto,) = obter_provedor().consultar_estornos(p1)
    assert visto.situacao == SituacaoDoEstorno.CONCLUIDO
    assert len(_movimentos(TipoDeMovimentoNoProvedor.DEVOLUCAO)) == 1


def test_o_invisivel_conta_no_restante(p1: str, sim: Any) -> None:  # A-14 (restante)
    sim.recusar_mas_processar(p1, "meio_nao_permite_estorno")
    with pytest.raises(RecusaDoProvedor):
        estornar(p1, "100.00", "k1")
    with pytest.raises(RecusaDoProvedor) as erro:
        estornar(p1, "30.00", "k2")
    assert erro.value.codigo == "valor_acima_do_disponivel"


def test_pagamento_pendente_ou_inexistente(sim: Any) -> None:  # A-15
    pendente = obter_provedor().criar_cobranca(
        NovaCobranca("c2", "ref-2", D("10.00"), "Pedido", T + DIA)
    )
    with pytest.raises(RecusaDoProvedor) as erro:
        estornar(pendente.pagamento.id_externo, "5.00", "k1")
    assert erro.value.codigo == "estado_invalido"
    obter_provedor().cancelar_cobranca(pendente.pagamento.id_externo)
    with pytest.raises(RecusaDoProvedor) as erro:
        estornar(pendente.pagamento.id_externo, "5.00", "k2")
    assert erro.value.codigo == "estado_invalido"
    with pytest.raises(PagamentoNaoEncontrado):
        estornar("sim-999999", "5.00", "k3")
    with pytest.raises(PagamentoNaoEncontrado):
        obter_provedor().consultar_estornos("sim-999999")


def test_contestacao_e_so_um_debito_na_conta(p1: str, sim: Any) -> None:  # A-16
    avisos_antes = AvisoSimulado.objects.count()
    sim.contestar(p1)
    sim.contestar(p1, D("10.00"), descricao="med")
    outros = _movimentos(TipoDeMovimentoNoProvedor.OUTRO)
    assert [(m.valor, m.descricao_no_provedor, m.id_externo) for m in outros] == [
        (D("-125.00"), "chargeback", p1),
        (D("-10.00"), "med", p1),
    ]
    assert obter_provedor().consultar_pagamento(p1).situacao == SituacaoNoProvedor.APROVADO
    assert AvisoSimulado.objects.count() == avisos_antes


def test_contestar_exige_pagamento_aprovado_e_valor_valido(p1: str, sim: Any) -> None:  # A-16
    pendente = obter_provedor().criar_cobranca(
        NovaCobranca("c2", "ref-2", D("10.00"), "Pedido", T + DIA)
    )
    with pytest.raises(ValueError):
        sim.contestar(pendente.pagamento.id_externo)
    for valor in (D("0.00"), D("125.01")):
        with pytest.raises(ValueError):
            sim.contestar(p1, valor)


@pytest.mark.parametrize(
    ("valor", "chave"),
    [
        (D("0.00"), "k"),
        (D("-1.00"), "k"),
        (D("1.001"), "k"),
        (D("1.00"), ""),
        (D("1.00"), "x" * 65),
    ],
)
def test_novo_estorno_invalido(valor: Decimal, chave: str) -> None:  # A-17
    with pytest.raises(ValueError):
        NovoEstorno("sim-1", valor, chave)


def test_listar_movimentos_leva_o_id_do_estorno(p1: str) -> None:  # A-19
    estorno = estornar(p1, "25.00", "k1")
    por_tipo = {m.tipo: m for m in _movimentos()}
    assert por_tipo[TipoDeMovimentoNoProvedor.DEVOLUCAO].id_estorno == estorno.id_estorno
    for tipo in (
        TipoDeMovimentoNoProvedor.PAGAMENTO,
        TipoDeMovimentoNoProvedor.TARIFA,
        TipoDeMovimentoNoProvedor.DEPOSITO,
    ):
        assert por_tipo[tipo].id_estorno is None


def test_reiniciar_apaga_os_controles_novos(p1: str, sim: Any) -> None:  # A-20
    sim.estornos_em_processamento(p1)
    sim.recusar_estornos(p1, "prazo_vencido")
    sim.recusar_mas_processar(p1, "prazo_vencido")
    sim.sem_estorno_parcial(p1)
    sim.reiniciar()
    sim.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    sim.definir_liberacao("pix", horas=0)
    sim.depositar(D("1000.00"))
    assert estornar(p1, "25.00", "k1").situacao == SituacaoDoEstorno.CONCLUIDO


def test_concluir_e_recusar_so_aceitam_estorno_em_processamento(p1: str, sim: Any) -> None:
    estorno = estornar(p1, "25.00", "k1")
    with pytest.raises(ValueError):
        sim.concluir_estorno(estorno.id_estorno)
    with pytest.raises(ValueError):
        sim.recusar_estorno(estorno.id_estorno, "estado_invalido")


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True)
def test_dois_estornos_concorrentes_com_a_mesma_chave(sim: Any) -> None:  # A-18
    p1 = _cobranca(sim)

    def pedir(barreira: Barrier) -> EstornoConsultado:
        barreira.wait(timeout=10)
        return estornar(p1, "25.00", "k1")

    resultados = executar_em_paralelo(pedir, pedir)
    assert [r.excecao for r in resultados] == [None, None]
    ids = {r.valor.id_estorno for r in resultados}
    assert len(ids) == 1
    assert EstornoSimulado.objects.count() == 1
    assert MovimentoSimulado.objects.filter(tipo="devolucao").count() == 1
