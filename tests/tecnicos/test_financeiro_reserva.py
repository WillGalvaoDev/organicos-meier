"""E09-05: reserva, aportes e designações (acceptance A-1 a A-11 e A-15)."""

from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction

from apps.financeiro.alertas import abrir_alerta
from apps.financeiro.livro import MovimentoInvalido, saldo
from apps.financeiro.models import (
    AlertaFinanceiro,
    ContaFinanceira,
    DesignacaoDaReserva,
    DesignacaoDesfeita,
    MovimentoFinanceiro,
    TipoDeMovimento,
)
from apps.financeiro.reserva import (
    AporteRepetido,
    CoberturaExcedente,
    DesignacaoEncerrada,
    InvarianteViolado,
    ReservaInsuficiente,
    SituacaoDaReserva,
    avaliar_reserva,
    desfazer_designacao,
    designar_reserva,
    itens_sem_cobertura,
    obrigacoes_sem_cobertura,
    registrar_aporte,
    situacao_da_reserva,
    utilizar_reserva,
)
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.financeiro import (
    Mundo,
    despesa_de_tarifa,
    despesas,
    montar_mundo,
    obrigacao_de_teste,
    reserva,
    semear,
)
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
T = TipoDeMovimento


@pytest.fixture
def m() -> Mundo:
    return montar_mundo()


def _estado() -> tuple[int, int, int, list[tuple[int, Decimal]]]:
    return (
        MovimentoFinanceiro.objects.count(),
        DesignacaoDaReserva.objects.count(),
        DesignacaoDesfeita.objects.count(),
        [(c.pk, saldo(c)) for c in ContaFinanceira.objects.order_by("pk") if saldo(c) != 0],
    )


def _aportar(m: Mundo, valor: str, identificacao: str = "sim-mov-1") -> None:
    registrar_aporte(m.admin, D(valor), identificacao, "Aporte de teste")


def test_o_aporte_entra_so_na_reserva(m: Mundo) -> None:  # A-1, cenário 29, A1
    movimento = registrar_aporte(m.admin, D("1000.00"), "sim-mov-1", "Aporte inicial")
    assert movimento.tipo == T.APORTE
    assert (movimento.autor_tipo, movimento.autor_id) == ("usuario", str(m.admin.pk))
    assert movimento.chave == "aporte:sim-mov-1"
    assert movimento.justificativa == "Aporte inicial"
    assert saldo(reserva()) == D("1000.00")
    assert situacao_da_reserva() == SituacaoDaReserva(D("1000.00"), D("0.00"), D("1000.00"))
    outras = ContaFinanceira.objects.exclude(destinacao="reserva")
    assert [c for c in outras if saldo(c) != 0] == []
    assert EntradaAuditoria.objects.filter(acao="financeiro.movimento").count() == 1


def test_aporte_repetido_ou_invalido_e_recusado(m: Mundo) -> None:  # A-2
    _aportar(m, "1000.00")
    antes = _estado()
    with pytest.raises(AporteRepetido):
        _aportar(m, "1000.00")
    for valor in (D("0"), D("-1.00"), D("1.001"), 1.0):
        with pytest.raises(MovimentoInvalido) as erro:
            registrar_aporte(m.admin, valor, "sim-mov-9", "Aporte")  # type: ignore[arg-type]
        assert erro.value.codigo == "valor"
    for identificacao in ("", "x" * 65):
        with pytest.raises(MovimentoInvalido) as erro:
            registrar_aporte(m.admin, D("1.00"), identificacao, "Aporte")
        assert erro.value.codigo == "identificacao"
    with pytest.raises(MovimentoInvalido) as erro:
        registrar_aporte(m.admin, D("1.00"), "sim-mov-9", "  ")
    assert erro.value.codigo == "justificativa"
    assert _estado() == antes


def test_designar_separa_o_dinheiro_sem_mover_nada(m: Mundo) -> None:  # A-3, P-3
    _aportar(m, "1000.00")
    obrigacao = obrigacao_de_teste("50.00")
    movimentos = MovimentoFinanceiro.objects.count()
    designacao = designar_reserva(m.admin, obrigacao, D("50.00"), "devolução depois do repasse")
    assert (designacao.valor, designacao.justificativa) == (
        D("50.00"),
        "devolução depois do repasse",
    )
    assert situacao_da_reserva() == SituacaoDaReserva(D("1000.00"), D("50.00"), D("950.00"))
    assert MovimentoFinanceiro.objects.count() == movimentos
    assert [i for i in itens_sem_cobertura() if i.tipo == "obrigacao"] == []
    assert EntradaAuditoria.objects.filter(acao="financeiro.designacao").count() == 1


def test_uso_acima_do_livre_e_recusado_inteiro(m: Mundo) -> None:  # A-4, T-10
    semear(m, reserva(), "30.00")
    obrigacao = obrigacao_de_teste("50.00")
    tarifa = despesa_de_tarifa("40.00")
    antes = _estado()
    with pytest.raises(ReservaInsuficiente):
        designar_reserva(m.admin, obrigacao, D("50.00"), "devolução")
    with pytest.raises(ReservaInsuficiente):
        utilizar_reserva(m.admin, tarifa, D("40.00"), "tarifa")
    assert _estado() == antes
    assert [(i.tipo, i.valor) for i in itens_sem_cobertura()] == [
        ("obrigacao", D("50.00")),
        ("despesa", D("40.00")),
    ]


def test_obrigacoes_sem_cobertura_acima_do_livre_abrem_o_alerta(m: Mundo) -> None:  # A-5
    semear(m, reserva(), "30.00")
    obrigacao_de_teste("50.00")
    despesa_de_tarifa("2.00")
    assert obrigacoes_sem_cobertura() == D("52.00")
    avaliar_reserva()
    (alerta,) = AlertaFinanceiro.objects.filter(tipo="reserva_insuficiente", resolvido_em=None)
    assert alerta.chave == "geral"
    assert (D(alerta.dados["sem_cobertura"]), D(alerta.dados["livre"])) == (D("52.00"), D("30.00"))


def test_aporte_resolve_o_alerta_e_a_reserva_cobre_designacao_e_tarifa(m: Mundo) -> None:  # A-6
    semear(m, reserva(), "30.00")
    obrigacao = obrigacao_de_teste("50.00")
    tarifa = despesa_de_tarifa("2.00")
    avaliar_reserva()
    registrar_aporte(m.admin, D("40.00"), "sim-mov-2", "Novo aporte")
    assert situacao_da_reserva().livre == D("70.00")
    assert (
        AlertaFinanceiro.objects.filter(tipo="reserva_insuficiente", resolvido_em=None).count() == 0
    )
    designar_reserva(m.admin, obrigacao, D("50.00"), "devolução")
    movimento = utilizar_reserva(m.admin, tarifa, D("2.00"), "tarifa de outubro")
    assert movimento.tipo == T.COBERTURA_DE_DESPESA
    (transferencia,) = movimento.transferencias.all()
    assert (transferencia.de.destinacao, transferencia.para.destinacao) == (
        "reserva",
        "despesas_a_cobrir",
    )
    assert situacao_da_reserva() == SituacaoDaReserva(D("68.00"), D("50.00"), D("18.00"))
    assert saldo(despesas()) == D("2.00")
    assert itens_sem_cobertura() == []


def test_designar_alem_do_que_falta_a_obrigacao_e_recusado(m: Mundo) -> None:  # A-7
    _aportar(m, "1000.00")
    obrigacao = obrigacao_de_teste("50.00")
    designar_reserva(m.admin, obrigacao, D("50.00"), "devolução")
    antes = _estado()
    with pytest.raises(CoberturaExcedente):
        designar_reserva(m.admin, obrigacao, D("0.01"), "a mais")
    assert _estado() == antes


def test_desfazer_a_designacao_devolve_o_comprometido(m: Mundo) -> None:  # A-8
    _aportar(m, "1000.00")
    obrigacao = obrigacao_de_teste("50.00")
    designacao = designar_reserva(m.admin, obrigacao, D("50.00"), "devolução")
    desfazer_designacao(m.admin, designacao, "outra fonte")
    assert situacao_da_reserva().comprometido == D("0.00")
    assert [(i.tipo, i.valor) for i in itens_sem_cobertura()] == [("obrigacao", D("50.00"))]
    (desfeita,) = DesignacaoDesfeita.objects.all()
    assert (desfeita.designacao_id, desfeita.justificativa) == (designacao.pk, "outra fonte")
    assert EntradaAuditoria.objects.filter(acao="financeiro.designacao_desfeita").count() == 1
    antes = _estado()
    with pytest.raises(DesignacaoEncerrada):
        desfazer_designacao(m.admin, designacao, "de novo")
    assert _estado() == antes


@pytest.mark.django_db(transaction=True)
def test_nenhuma_tarefa_periodica_faz_aporte(m: Mundo) -> None:  # A-9, P-4
    from procrastinate.contrib.django import app

    with transaction.atomic():
        semear(m, reserva(), "10.00")
        obrigacao_de_teste("500.00")
    aportes = MovimentoFinanceiro.objects.filter(tipo=T.APORTE).count()
    tarefas = list(app.periodic_registry.periodic_tasks.values())
    assert len(tarefas) >= 5
    for periodica in tarefas:
        periodica.task.func(timestamp=0)
    assert MovimentoFinanceiro.objects.filter(tipo=T.APORTE).count() == aportes == 1
    assert saldo(reserva()) == D("10.00")


def test_invariante_violado_bloqueia_designar_e_utilizar_mas_nao_o_aporte(m: Mundo) -> None:
    _aportar(m, "1000.00")  # A-10
    obrigacao = obrigacao_de_teste("50.00")
    tarifa = despesa_de_tarifa("2.00")
    with transaction.atomic():
        abrir_alerta("invariante_violado", "geral", {"diferenca": "-5.00"})
    antes = _estado()
    with pytest.raises(InvarianteViolado):
        designar_reserva(m.admin, obrigacao, D("10.00"), "devolução")
    with pytest.raises(InvarianteViolado):
        utilizar_reserva(m.admin, tarifa, D("2.00"), "tarifa")
    assert _estado() == antes
    registrar_aporte(m.admin, D("5.00"), "sim-mov-3", "Aporte durante o bloqueio")
    assert saldo(reserva()) == D("1005.00")


def test_so_o_administrador_chama_os_servicos(m: Mundo) -> None:  # A-11
    _aportar(m, "1000.00")
    obrigacao = obrigacao_de_teste("50.00")
    designacao = designar_reserva(m.admin, obrigacao, D("10.00"), "devolução")
    tarifa = despesa_de_tarifa("2.00")
    antes = _estado()
    intrusos: list[Any] = [m.x, ContaFactory.create(fornecedor=True), AnonymousUser(), None]
    for autor in intrusos:
        with pytest.raises(PermissionDenied):
            registrar_aporte(autor, D("1.00"), "sim-mov-7", "x")
        with pytest.raises(PermissionDenied):
            designar_reserva(autor, obrigacao, D("1.00"), "x")
        with pytest.raises(PermissionDenied):
            desfazer_designacao(autor, designacao, "x")
        with pytest.raises(PermissionDenied):
            utilizar_reserva(autor, tarifa, D("1.00"), "x")
    assert _estado() == antes


def test_totalmente_designada_a_obrigacao_sai_da_lista(m: Mundo) -> None:  # A-15
    _aportar(m, "100.00")
    obrigacao = obrigacao_de_teste("50.00")
    designar_reserva(m.admin, obrigacao, D("50.00"), "devolução")
    despesa_de_tarifa("2.00")
    assert [(i.tipo, i.valor) for i in itens_sem_cobertura()] == [("despesa", D("2.00"))]


def test_o_banco_recusa_designacao_incoerente(m: Mundo) -> None:
    obrigacao = obrigacao_de_teste("50.00")
    autor = str(m.admin.pk)
    recusadas: list[dict[str, Any]] = [
        {"valor": D("0.00"), "justificativa": "devolução"},
        {"valor": D("-1.00"), "justificativa": "devolução"},
        {"valor": D("1.00"), "justificativa": "  "},
    ]
    for campos in recusadas:
        with pytest.raises(IntegrityError), transaction.atomic():
            DesignacaoDaReserva.objects.create(obrigacao=obrigacao, autor_id=autor, **campos)
    designacao = DesignacaoDaReserva.objects.create(
        obrigacao=obrigacao, autor_id=autor, valor=D("1.00"), justificativa="devolução"
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        DesignacaoDesfeita.objects.create(designacao=designacao, autor_id=autor, justificativa="")
    DesignacaoDesfeita.objects.create(designacao=designacao, autor_id=autor, justificativa="ok")
    with pytest.raises(IntegrityError), transaction.atomic():
        DesignacaoDesfeita.objects.create(designacao=designacao, autor_id=autor, justificativa="2")
