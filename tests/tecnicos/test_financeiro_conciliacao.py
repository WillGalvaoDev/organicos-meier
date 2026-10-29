"""E09-07: conciliação diária com o provedor (acceptance A-11 a A-18, A-21 e A-23)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction

from apps.financeiro.alertas import abrir_alerta
from apps.financeiro.conciliacao import (
    ConciliacaoDiaria,
    conciliar_dia,
    conciliar_dias_pendentes_agora,
)
from apps.financeiro.liquidez import registrar_saida
from apps.financeiro.livro import EXTERIOR
from apps.financeiro.models import AlertaFinanceiro, MovimentoFinanceiro, TipoDeMovimento
from apps.financeiro.reserva import registrar_aporte
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
from apps.pagamentos.models import ChamadaAoProvedor, PagamentoNoProvedor
from apps.pagamentos.provedor import (
    MovimentoNoProvedor,
    NovaCobranca,
    SaldoNoProvedor,
    TipoDeMovimentoNoProvedor,
    obter_provedor,
)
from apps.simulador_pagamentos.provedor import ProvedorSimulado
from tests.apoio.financeiro import custodia, montar_l, montar_mundo, mover, obrigacao_de
from tests.apoio.pedidos import T0, administrador
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)
DIA = date(2026, 11, 2)  # em Brasília: de 2026-11-02 03:00Z a 2026-11-03 03:00Z
DEPOIS_DO_DIA = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


@dataclass
class Dia:
    a: Any
    b: Any
    sim: Any
    relogio: RelogioControlado
    id_deposito: str
    id_repasse: str


def _alertas(tipo: str) -> list[AlertaFinanceiro]:
    return list(AlertaFinanceiro.objects.filter(tipo=tipo, resolvido_em=None).order_by("pk"))


@pytest.fixture
def dia(relogio: RelogioControlado, simulador_pagamentos: Any) -> Dia:
    """O dia D (2026-11-02) conciliável: o pagamento de XA (às `T0 + 1h`), o depósito e o aporte
    registrado, e um repasse de 50,00 de B (liberado), registrado no simulador e no livro. O
    relógio fica no dia seguinte, depois do fim de D."""
    a, b = montar_l(simulador_pagamentos, relogio)
    relogio.congelar(T0 + 3 * H)
    id_deposito = simulador_pagamentos.depositar(D("1000.00"))
    id_repasse = simulador_pagamentos.registrar_saida(D("50.00"), descricao="repasse")
    with transaction.atomic():
        registrar_aporte(administrador(), D("1000.00"), id_deposito, "Aporte inicial")
    with transaction.atomic():  # uma operação por transação, como em produção
        registrar_saida(
            administrador(),
            tipo="repasse",
            conta=obrigacao_de(b.fornecedor, b.rodada),
            valor=D("50.00"),
            identificacao=id_repasse,
            justificativa="Repasse manual por Pix",
        )
    relogio.congelar(DEPOIS_DO_DIA)
    return Dia(a, b, simulador_pagamentos, relogio, id_deposito, id_repasse)


def test_dia_sem_diferencas_concilia_ok_sem_alertas(dia: Dia) -> None:  # A-11
    conciliacao = conciliar_dia(DIA)
    assert conciliacao.data == DIA
    assert conciliacao.resultado == "ok"
    assert conciliacao.resumo["sem_par"] == 0
    assert D(str(conciliacao.resumo["diferenca"])) == D("0.00")
    assert conciliacao.resumo["movimentos"] == 3  # o pagamento de XA, o depósito e a saída
    assert AlertaFinanceiro.objects.count() == 0


def _pagamento_nunca_sincronizado(dia: Dia) -> str:
    dia.relogio.congelar(T0 + 4 * H)
    nova = NovaCobranca(
        chave_idempotencia="k-sem-sync",
        referencia_externa="ref-desconhecida",
        valor=D("40.00"),
        descricao="Sem sincronizar",
        expira_em=T0 + 24 * H,
    )
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    dia.sim.aprovar(id_externo)
    dia.relogio.congelar(DEPOIS_DO_DIA)
    return id_externo


def test_pagamento_aprovado_e_nunca_sincronizado_alerta_e_agenda_a_consulta(dia: Dia) -> None:
    id_externo = _pagamento_nunca_sincronizado(dia)  # A-12, A-21
    movimentos = MovimentoFinanceiro.objects.count()
    conciliacao = conciliar_dia(DIA)
    assert conciliacao.resultado == "divergente"
    (alerta,) = _alertas("pagamento_sem_conciliacao")
    assert alerta.chave == id_externo
    consulta = ChamadaAoProvedor.objects.get(operacao="consultar_pagamento", alvo=id_externo)
    assert consulta.situacao == "pendente"
    assert MovimentoFinanceiro.objects.count() == movimentos  # a conciliação não lança nada (A-21)
    processar_chamadas()
    assert (
        MovimentoFinanceiro.objects.filter(tipo=TipoDeMovimento.ENTRADA_PARA_DEVOLUCAO).count() == 1
    )
    assert _alertas("pagamento_sem_conciliacao") == []
    assert PagamentoNoProvedor.objects.filter(id_externo=id_externo).exists()


def test_deposito_sem_aporte_e_aporte_sem_deposito(dia: Dia) -> None:  # A-13
    dia.relogio.congelar(T0 + 5 * H)
    id_novo = dia.sim.depositar(D("200.00"))
    with transaction.atomic():
        registrar_aporte(administrador(), D("50.00"), "inexistente", "Aporte sem depósito")
    dia.relogio.congelar(DEPOIS_DO_DIA)
    conciliar_dia(DIA)
    chaves = sorted(a.chave for a in _alertas("divergencia_na_conciliacao"))
    assert chaves == sorted([id_novo, "livro:inexistente"])
    with transaction.atomic():
        registrar_aporte(administrador(), D("200.00"), id_novo, "Aporte do depósito")
    assert [a.chave for a in _alertas("divergencia_na_conciliacao")] == ["livro:inexistente"]


def test_ajuste_do_provedor_e_divergencia_mas_a_diferenca_esta_explicada(dia: Dia) -> None:
    dia.relogio.congelar(T0 + 5 * H)  # A-14
    id_ajuste = dia.sim.ajustar_saldo(D("-0.50"))
    dia.relogio.congelar(DEPOIS_DO_DIA)
    conciliar_dia(DIA)
    (alerta,) = _alertas("divergencia_na_conciliacao")
    assert alerta.chave == id_ajuste
    assert alerta.dados["descricao_no_provedor"] == "ajuste"
    assert not [a for a in AlertaFinanceiro.objects.all() if a.chave.startswith("saldo:")]


def test_lancamento_sem_pagamento_no_provedor_deixa_diferenca_inexplicada(dia: Dia) -> None:
    mundo = montar_mundo()  # A-15 (i)
    dia.relogio.congelar(T0 + 5 * H)
    mover(
        TipoDeMovimento.ENTRADA_DE_PAGAMENTO,
        EXTERIOR,
        custodia(mundo.ra, mundo.ca, mundo.x),
        "10.00",
    )
    dia.relogio.congelar(DEPOIS_DO_DIA)
    conciliar_dia(DIA)
    (alerta,) = _alertas("divergencia_na_conciliacao")
    assert alerta.chave == f"saldo:{DIA.isoformat()}"
    assert D(str(alerta.dados["diferenca"])) == D("-10.00")


def test_conciliacao_posterior_sem_diferenca_resolve_o_alerta_de_saldo(dia: Dia) -> None:
    with transaction.atomic():  # A-15 (ii)
        abrir_alerta(
            "divergencia_na_conciliacao",
            f"saldo:{(DIA - timedelta(days=1)).isoformat()}",
            {"data": (DIA - timedelta(days=1)).isoformat(), "diferenca": "-3.00"},
        )
    conciliar_dia(DIA)
    assert _alertas("divergencia_na_conciliacao") == []


def test_repetir_futuro_e_provedor_fora_do_ar(dia: Dia) -> None:  # A-16
    primeira = conciliar_dia(DIA)
    dia.sim.indisponivel()
    assert conciliar_dia(DIA).pk == primeira.pk  # não consulta o provedor
    dia.relogio.congelar(datetime(2026, 11, 3, 12, 0, tzinfo=UTC))
    with pytest.raises(ValueError):  # noqa: PT011
        conciliar_dia(date(2026, 11, 3))  # hoje, ainda não terminou
    dia.relogio.congelar(datetime(2026, 11, 4, 12, 0, tzinfo=UTC))
    with pytest.raises(ConsultaAoProvedorFalhou):
        conciliar_dia(date(2026, 11, 3))
    assert ConciliacaoDiaria.objects.count() == 1


def _ja_conciliado(data: date) -> None:
    ConciliacaoDiaria.objects.create(
        data=data, executada_em=datetime(2026, 11, 1, tzinfo=UTC), resultado="ok", resumo={}
    )


def test_dias_pendentes_sao_conciliados_em_ordem(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-17
    _ja_conciliado(date(2026, 10, 30))  # D - 3, com D = 02/11
    relogio.congelar(datetime(2026, 11, 3, 4, 0, tzinfo=UTC))  # 01:00 de D + 1 em Brasília
    assert conciliar_dias_pendentes_agora() == 3
    datas = list(ConciliacaoDiaria.objects.order_by("pk").values_list("data", flat=True))
    assert datas == [date(2026, 10, 30), date(2026, 10, 31), date(2026, 11, 1), date(2026, 11, 2)]


def test_o_dia_corrente_nao_e_conciliado(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-18
    _ja_conciliado(date(2026, 11, 1))
    relogio.congelar(datetime(2026, 11, 3, 2, 59, tzinfo=UTC))  # 23:59 de 2026-11-02 em Brasília
    assert conciliar_dias_pendentes_agora() == 0
    assert not ConciliacaoDiaria.objects.filter(data=DIA).exists()


def test_falha_do_provedor_para_a_fila_e_deixa_os_dias_para_a_proxima(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-17
    from apps.pagamentos.provedor import ProvedorIndisponivel

    _ja_conciliado(date(2026, 10, 30))
    relogio.congelar(datetime(2026, 11, 3, 4, 0, tzinfo=UTC))
    original = ProvedorSimulado.listar_movimentos
    chamadas: list[datetime] = []

    def falha_no_segundo_dia(self: ProvedorSimulado, desde: datetime, ate: datetime) -> Any:
        chamadas.append(desde)
        if len(chamadas) == 2:
            raise ProvedorIndisponivel("fora do ar")
        return original(self, desde, ate)

    monkeypatch.setattr(ProvedorSimulado, "listar_movimentos", falha_no_segundo_dia)
    assert conciliar_dias_pendentes_agora() == 1  # D - 2; para em D - 1
    datas = list(ConciliacaoDiaria.objects.order_by("pk").values_list("data", flat=True))
    assert datas == [date(2026, 10, 30), date(2026, 10, 31)]
    monkeypatch.setattr(ProvedorSimulado, "listar_movimentos", original)
    assert conciliar_dias_pendentes_agora() == 2  # D - 1 e D ficaram para a próxima


class _ProvedorComChargeback:
    def __init__(self, referente_a: datetime) -> None:
        self.referente_a = referente_a

    def listar_movimentos(self, desde: datetime, ate: datetime) -> list[MovimentoNoProvedor]:
        return [
            MovimentoNoProvedor(
                id_movimento="mp-77",
                tipo=TipoDeMovimentoNoProvedor.OUTRO,
                descricao_no_provedor="chargeback",
                valor=D("-10.00"),
                id_externo=None,
                ocorrido_em=datetime(2026, 11, 2, 15, 0, tzinfo=UTC),
                liberado_em=datetime(2026, 11, 2, 15, 0, tzinfo=UTC),
            )
        ]

    def consultar_saldo(self) -> SaldoNoProvedor:
        return SaldoNoProvedor(D("-10.00"), D("0.00"), self.referente_a, self.referente_a)


def test_movimento_desconhecido_do_provedor_e_divergencia_com_o_rotulo(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-23
    relogio.congelar(DEPOIS_DO_DIA)
    monkeypatch.setattr(
        "apps.financeiro.conciliacao.obter_provedor", lambda: _ProvedorComChargeback(DEPOIS_DO_DIA)
    )
    conciliar_dia(DIA)
    (alerta,) = _alertas("divergencia_na_conciliacao")
    assert alerta.chave == "mp-77"
    assert alerta.dados["descricao_no_provedor"] == "chargeback"


def test_conciliacao_nao_cria_movimento_no_livro(dia: Dia) -> None:  # A-21
    antes = MovimentoFinanceiro.objects.count()
    conciliar_dia(DIA)
    assert MovimentoFinanceiro.objects.count() == antes


def test_tarifa_do_provedor_sem_despesa_e_divergencia_ate_a_tarefa_registra(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:
    from dataclasses import replace

    from apps.financeiro.entradas import registrar_tarifas_pendentes_agora
    from apps.pagamentos.sincronizacao import sincronizar_pagamento
    from tests.apoio.financeiro import pedido_composto
    from tests.apoio.pedidos import sincronizar, tentativa_criada
    from tests.fabricas import ContaFactory

    simulador_pagamentos.definir_tarifa("pix", percentual=D("1.00"), fixa=D("0.00"))
    relogio.congelar(T0 + H)
    pedido = pedido_composto(ContaFactory.create())
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    simulador_pagamentos.aprovar(id_externo)
    completa = obter_provedor().consultar_pagamento(id_externo)
    with transaction.atomic():
        sincronizar_pagamento(replace(completa, tarifa=None, liberado_em=None), origem="tarefa")
    relogio.congelar(DEPOIS_DO_DIA)
    conciliar_dia(DIA)
    (alerta,) = _alertas("divergencia_na_conciliacao")
    assert alerta.dados["tipo"] == "tarifa"
    assert alerta.dados["id_externo"] == id_externo
    sincronizar(id_externo)
    assert registrar_tarifas_pendentes_agora() == 1
    assert _alertas("divergencia_na_conciliacao") == []


# --- Correções E09-R06 e E09-R07 (A-25 a A-27) -------------------------------------------------


class _Dubles:
    """Um provedor de teste: o saldo e os movimentos que o teste decidir."""

    def __init__(
        self, saldo_: SaldoNoProvedor, movimentos: list[MovimentoNoProvedor] | None = None
    ) -> None:
        self._saldo = saldo_
        self._movimentos = movimentos or []

    def consultar_saldo(self) -> SaldoNoProvedor:
        return self._saldo

    def listar_movimentos(self, desde: datetime, ate: datetime) -> list[MovimentoNoProvedor]:
        return [m for m in self._movimentos if desde <= m.ocorrido_em < ate]


def _usar(monkeypatch: pytest.MonkeyPatch, provedor: _Dubles) -> None:
    monkeypatch.setattr("apps.financeiro.conciliacao.obter_provedor", lambda: provedor)


def _saldo(valor: str, quando: datetime) -> SaldoNoProvedor:
    return SaldoNoProvedor(D(valor), D("0.00"), quando, quando)


def _movimento(
    tipo: TipoDeMovimentoNoProvedor,
    id_movimento: str,
    valor: str,
    quando: datetime,
    id_externo: str | None = None,
) -> MovimentoNoProvedor:
    return MovimentoNoProvedor(id_movimento, tipo, tipo.value, D(valor), id_externo, quando, quando)


def test_identificacao_de_64_caracteres_e_conciliavel(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-25, E09-R06
    from apps.financeiro.conciliacao import limites_do_dia
    from tests.apoio.financeiro import frete_de, montar_mundo, semear

    inicio, fim = limites_do_dia(DIA)
    relogio.congelar(inicio + 12 * H)
    mundo = montar_mundo()
    with transaction.atomic():
        semear(mundo, frete_de(mundo.ra), "10.00")
        registrar_aporte(administrador(), D("100.00"), "a" * 64, "Aporte")
        registrar_saida(
            administrador(),
            tipo="pagamento_do_frete",
            conta=frete_de(mundo.ra),
            valor=D("5.00"),
            identificacao="s" * 64,
            justificativa="Pagamento do frete",
        )
    _usar(monkeypatch, _Dubles(_saldo("0.00", fim + H)))
    relogio.congelar(fim + H)
    conciliacao = conciliar_dia(DIA)
    assert conciliacao.resultado == "divergente"
    alertas = _alertas("divergencia_na_conciliacao")
    assert sorted(a.chave for a in alertas if a.chave.startswith("livro:")) == sorted(
        ["livro:" + "a" * 64, "livro:" + "s" * 64]
    )
    assert {a.dados["identificacao"] for a in alertas if a.chave.startswith("livro:")} == {
        "a" * 64,
        "s" * 64,
    }
    relogio.congelar(fim + 2 * 24 * H)
    _usar(monkeypatch, _Dubles(_saldo("0.00", fim + 2 * 24 * H)))
    assert conciliar_dias_pendentes_agora() >= 1
    assert ConciliacaoDiaria.objects.filter(data=DIA + timedelta(days=1)).exists()


def test_a_diferenca_respeita_o_instante_do_saldo(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-26 (i), E09-R07
    from apps.financeiro.conciliacao import limites_do_dia

    inicio, fim = limites_do_dia(DIA)
    ajuste = _movimento(TipoDeMovimentoNoProvedor.AJUSTE, "ajuste-tarde", "10.00", inicio + 12 * H)
    _usar(monkeypatch, _Dubles(_saldo("0.00", inicio + 10 * H), [ajuste]))
    relogio.congelar(fim + H)
    conciliacao = conciliar_dia(DIA)
    assert D(str(conciliacao.resumo["diferenca"])) == D("0.00")
    assert [a.chave for a in _alertas("divergencia_na_conciliacao")] == ["ajuste-tarde"]


def test_pagamento_lancado_depois_do_instante_do_saldo_nao_cria_diferenca(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-26 (ii), E09-R07
    from apps.financeiro.conciliacao import limites_do_dia
    from tests.apoio.financeiro import pedido_composto
    from tests.apoio.pedidos import sincronizar, tentativa_criada
    from tests.fabricas import ContaFactory

    _, fim = limites_do_dia(DIA)
    relogio.congelar(T0 + H)
    pedido = pedido_composto(ContaFactory.create())
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    relogio.congelar(fim - H)  # 23:00 de D em Brasília
    simulador_pagamentos.aprovar(id_externo)
    relogio.congelar(fim + timedelta(minutes=30))  # a entrada é lançada às 00:30 de D + 1
    sincronizar(id_externo)
    pagamento = _movimento(
        TipoDeMovimentoNoProvedor.PAGAMENTO, "pag-1", "125.00", fim - H, id_externo
    )
    _usar(monkeypatch, _Dubles(_saldo("125.00", fim - timedelta(minutes=30)), [pagamento]))
    relogio.congelar(fim + H)
    conciliacao = conciliar_dia(DIA)
    assert D(str(conciliacao.resumo["diferenca"])) == D("0.00")
    assert not [a for a in AlertaFinanceiro.objects.all() if a.chave.startswith("saldo:")]
    assert _alertas("pagamento_sem_conciliacao") == []


def test_movimento_do_provedor_depois_do_dia_nao_e_par_de_um_aporte_do_dia(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-27, E09-R07
    from apps.financeiro.conciliacao import limites_do_dia
    from tests.apoio.financeiro import montar_mundo

    inicio, fim = limites_do_dia(DIA)
    relogio.congelar(inicio + 12 * H)
    montar_mundo()
    with transaction.atomic():
        registrar_aporte(administrador(), D("100.00"), "futuro", "Aporte")
    deposito = _movimento(TipoDeMovimentoNoProvedor.DEPOSITO, "futuro", "100.00", fim + H)
    _usar(monkeypatch, _Dubles(_saldo("100.00", fim + 2 * H), [deposito]))
    relogio.congelar(fim + 2 * H)
    conciliacao = conciliar_dia(DIA)
    assert conciliacao.resultado == "divergente"
    assert conciliacao.resumo["sem_par"] == 1
    assert [a.chave for a in _alertas("divergencia_na_conciliacao")] == ["livro:futuro"]
    assert D(str(conciliacao.resumo["diferenca"])) == D("0.00")


# --- Correção E09-R07 residual: a tarifa pareada pelo instante do lançamento (A-28 e A-29) ------


def _arranjo_da_tarifa(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> tuple[datetime, str]:
    """Pagamento de 125,00 sincronizado em T (23:00 de D), tarifa fixa de 10,00: a despesa nasce em
    T e o movimento `tarifa:<pk>` em T + 10 s (o relógio avança imediatamente antes do `lancar`
    da tarifa; o monkeypatch não retira validação nem efeito)."""
    from apps.financeiro.conciliacao import limites_do_dia
    from apps.financeiro.livro import lancar as lancar_original
    from apps.financeiro.models import Despesa
    from tests.apoio.financeiro import pedido_composto
    from tests.apoio.pedidos import sincronizar, tentativa_criada
    from tests.fabricas import ContaFactory

    _, fim = limites_do_dia(DIA)
    instante = fim - H
    simulador_pagamentos.definir_tarifa("pix", percentual=D("0.00"), fixa=D("10.00"))
    relogio.congelar(T0 + H)
    pedido = pedido_composto(ContaFactory.create())
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    relogio.congelar(instante)
    simulador_pagamentos.aprovar(id_externo)

    def lancar_com_atraso(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("tipo") == TipoDeMovimento.TARIFA:
            relogio.avancar(timedelta(seconds=10))
        return lancar_original(*args, **kwargs)

    monkeypatch.setattr("apps.financeiro.entradas.lancar", lancar_com_atraso)
    sincronizar(id_externo)
    despesa = Despesa.objects.get(tipo="tarifa")
    assert despesa.criada_em == instante
    tarifa = MovimentoFinanceiro.objects.get(tipo=TipoDeMovimento.TARIFA)
    assert tarifa.momento == instante + timedelta(seconds=10)
    return instante, id_externo


def _conciliar_com_saldo_em(
    monkeypatch: pytest.MonkeyPatch,
    relogio: RelogioControlado,
    instante: datetime,
    id_externo: str,
    referente_a: datetime,
) -> Any:
    from apps.financeiro.conciliacao import limites_do_dia

    _, fim = limites_do_dia(DIA)
    movimentos = [
        _movimento(TipoDeMovimentoNoProvedor.PAGAMENTO, "pag-1", "125.00", instante, id_externo),
        _movimento(TipoDeMovimentoNoProvedor.TARIFA, "tar-1", "-10.00", instante, id_externo),
    ]
    _usar(monkeypatch, _Dubles(_saldo("115.00", referente_a), movimentos))
    relogio.congelar(fim + H)
    return conciliar_dia(DIA)


def _confere_conciliacao_sem_divergencia(conciliacao: Any) -> None:
    assert D(str(conciliacao.resumo["diferenca"])) == D("0.00")
    assert conciliacao.resumo["movimentos"] == 2
    assert conciliacao.resumo["sem_par"] == 0
    assert conciliacao.resultado == "ok"
    assert not [a for a in AlertaFinanceiro.objects.all() if a.chave.startswith("saldo:")]
    assert _alertas("divergencia_na_conciliacao") == []


def test_tarifa_sem_movimento_no_instante_do_saldo_nao_e_par(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-28, E09-R07 residual
    instante, id_externo = _arranjo_da_tarifa(relogio, simulador_pagamentos, monkeypatch)
    conciliacao = _conciliar_com_saldo_em(
        monkeypatch, relogio, instante, id_externo, instante + timedelta(seconds=5)
    )
    _confere_conciliacao_sem_divergencia(conciliacao)


def test_tarifa_com_movimento_antes_do_instante_do_saldo_e_par(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-29, E09-R07 residual (regressão: já passa no código atual)
    instante, id_externo = _arranjo_da_tarifa(relogio, simulador_pagamentos, monkeypatch)
    conciliacao = _conciliar_com_saldo_em(
        monkeypatch, relogio, instante, id_externo, instante + timedelta(seconds=15)
    )
    _confere_conciliacao_sem_divergencia(conciliacao)
