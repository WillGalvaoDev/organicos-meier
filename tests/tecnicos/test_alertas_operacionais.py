"""E15-02: os alertas operacionais e a verificação periódica (acceptance A-1 a A-15)."""

import logging
from datetime import timedelta
from typing import Any

import pytest
from django.db import transaction

from tests.apoio.operacao import (
    INSTANTE,
    MIN,
    Ao,
    alertas,
    arranjo_ao,
    concluir,
    concluir_todas,
    notificacoes,
    verificar,
)
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

ENVIOS = "processar_envios_pendentes"
CORPO_DO_ATRASO = (
    "A tarefa Envio de notificações não conclui desde 20/11/2026 09:00. "
    "Ela deveria rodar a cada 1 minuto(s)."
)


@pytest.fixture
def ao(relogio: RelogioControlado) -> Ao:
    return arranjo_ao(relogio)


def _atrasar_envios(relogio: RelogioControlado, instante: Any) -> tuple[int, int]:
    """Todas as tarefas em dia no instante, menos a de envios, que parou em `INSTANTE`."""
    concluir_todas(instante, exceto=(ENVIOS,))
    return verificar(relogio, instante)


def test_a_tarefa_atrasada_abre_o_alerta_e_avisa(relogio: RelogioControlado, ao: Ao) -> None:  # A-1
    from apps.notificacoes.models import Envio

    retorno = _atrasar_envios(relogio, INSTANTE + 6 * MIN)
    assert retorno == (1, 0)
    (alerta,) = alertas("tarefa_atrasada")
    assert alerta.chave == ENVIOS
    assert alerta.gravidade == "aviso"
    assert alerta.dados == {
        "tarefa": ENVIOS,
        "descricao": "Envio de notificações",
        "referencia": INSTANTE.isoformat(),
        "atrasada_desde": (INSTANTE + 5 * MIN).isoformat(),
        "intervalo_minutos": 1,
    }
    (notificacao,) = notificacoes(ao.adm1)
    assert notificacao.titulo == "Tarefa atrasada"
    assert notificacao.corpo == CORPO_DO_ATRASO
    assert notificacao.link == "/administracao/"
    (envio,) = Envio.objects.filter(notificacao=notificacao)
    assert envio.canal == "email"
    for outro in (ao.c, ao.f):
        assert notificacoes(outro) == []
        assert Envio.objects.filter(conta=outro).count() == 0


def test_verificar_de_novo_nao_repete(relogio: RelogioControlado, ao: Ao) -> None:  # A-2
    _atrasar_envios(relogio, INSTANTE + 6 * MIN)
    assert _atrasar_envios(relogio, INSTANTE + 7 * MIN) == (0, 0)
    assert len(alertas("tarefa_atrasada")) == 1
    assert len(notificacoes(ao.adm1)) == 1


def test_o_alerta_e_resolvido_quando_a_tarefa_volta(
    relogio: RelogioControlado, ao: Ao
) -> None:  # A-3
    _atrasar_envios(relogio, INSTANTE + 6 * MIN)
    concluir(ENVIOS, INSTANTE + 8 * MIN)
    concluir_todas(INSTANTE + 9 * MIN)
    assert verificar(relogio, INSTANTE + 9 * MIN) == (0, 1)
    (alerta,) = alertas("tarefa_atrasada")
    assert alerta.resolvido_em == INSTANTE + 9 * MIN
    assert alerta.motivo_da_resolucao == "condição encerrada"


def test_a_tarefa_que_para_de_novo_abre_outro_alerta(
    relogio: RelogioControlado, ao: Ao
) -> None:  # A-4
    _atrasar_envios(relogio, INSTANTE + 6 * MIN)
    concluir_todas(INSTANTE + 9 * MIN)
    verificar(relogio, INSTANTE + 9 * MIN)
    primeiro = alertas("tarefa_atrasada")[0]
    concluir_todas(INSTANTE + 15 * MIN, exceto=(ENVIOS,))
    assert verificar(relogio, INSTANTE + 15 * MIN) == (1, 0)
    todos = alertas("tarefa_atrasada")
    assert len(todos) == 2
    assert todos[1].pk != primeiro.pk
    assert todos[0].resolvido_em == INSTANTE + 9 * MIN
    assert len(notificacoes(ao.adm1)) == 2


def test_tarefa_sem_registro_ganha_o_registro_e_depois_o_alerta(
    relogio: RelogioControlado, ao: Ao
) -> None:  # A-5
    from apps.operacao.models import ExecucaoDaTarefa

    ExecucaoDaTarefa.objects.filter(nome="enviar_pedidos_formais").delete()
    assert verificar(relogio, INSTANTE) == (0, 0)
    registro = ExecucaoDaTarefa.objects.get(nome="enviar_pedidos_formais")
    assert registro.monitorada_desde == INSTANTE
    assert alertas("tarefa_atrasada") == []
    instante = INSTANTE + 5 * MIN + timedelta(seconds=1)
    concluir_todas(instante, exceto=("enviar_pedidos_formais",))
    verificar(relogio, instante)
    (alerta,) = alertas("tarefa_atrasada")
    assert alerta.chave == "enviar_pedidos_formais"
    (notificacao,) = notificacoes(ao.adm1)
    assert "não tem execução concluída desde 20/11/2026 09:00" in notificacao.corpo


def test_uma_verificacao_que_falha_nao_derruba_as_outras(
    relogio: RelogioControlado,
    ao: Ao,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-6
    from apps.operacao import verificacao

    _atrasar_envios(relogio, INSTANTE + 6 * MIN)

    def quebra(instante: Any) -> dict[str, dict[str, Any]]:
        raise RuntimeError("falha de teste")

    monkeypatch.setattr(
        verificacao,
        "VERIFICACOES",
        {"verificacao_de_teste": quebra, **verificacao.VERIFICACOES},
    )
    concluir_todas(INSTANTE + 9 * MIN)
    with caplog.at_level(logging.ERROR):
        assert verificar(relogio, INSTANTE + 9 * MIN) == (0, 1)
    texto = " ".join(r.getMessage() for r in caplog.records)
    assert "verificacao_de_teste" in texto
    assert "RuntimeError" in texto
    assert "falha de teste" not in texto
    assert alertas("tarefa_atrasada")[0].resolvido_em == INSTANTE + 9 * MIN


def test_verificacao_que_falha_nao_resolve_nada(
    relogio: RelogioControlado, ao: Ao, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-7
    from apps.operacao import verificacao

    _atrasar_envios(relogio, INSTANTE + 6 * MIN)

    def quebra(instante: Any) -> dict[str, dict[str, Any]]:
        raise RuntimeError("x")

    monkeypatch.setattr(verificacao, "VERIFICACOES", {**verificacao.VERIFICACOES})
    verificacao.VERIFICACOES["tarefa_atrasada"] = quebra
    concluir_todas(INSTANTE + 9 * MIN)
    assert verificar(relogio, INSTANTE + 9 * MIN) == (0, 0)
    assert len(alertas("tarefa_atrasada", abertos=True)) == 1


def test_o_alerta_financeiro_segue_como_antes(ao: Ao) -> None:  # A-8
    from apps.financeiro.alertas import abrir_alerta

    with transaction.atomic():
        abrir_alerta("invariante_violado", "geral", {"diferenca": "10.00"})
    (notificacao,) = notificacoes(ao.adm1, "alerta_financeiro")
    assert notificacao.link == "/administracao/financeiro/"
    assert notificacoes(ao.adm1) == []


def test_sem_administrador_ativo_o_alerta_abre_sem_aviso(
    relogio: RelogioControlado, ao: Ao, caplog: pytest.LogCaptureFixture
) -> None:  # A-9
    from apps.contas.models import Conta, Papel

    Conta.objects.filter(papel=Papel.ADMINISTRADOR).update(papel=Papel.COMPRADOR)
    with caplog.at_level(logging.WARNING):
        assert _atrasar_envios(relogio, INSTANTE + 6 * MIN) == (1, 0)
    assert len(alertas("tarefa_atrasada")) == 1
    assert notificacoes(ao.adm1) == []
    assert any("nenhum administrador ativo" in r.getMessage() for r in caplog.records)


def test_a_abertura_vai_para_o_log_sem_os_dados(
    relogio: RelogioControlado, ao: Ao, caplog: pytest.LogCaptureFixture
) -> None:  # A-10
    with caplog.at_level(logging.INFO):
        _atrasar_envios(relogio, INSTANTE + 6 * MIN)
    avisos = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "tarefa_atrasada" in r.getMessage()
    ]
    assert len(avisos) == 1
    assert ENVIOS in avisos[0].getMessage()
    assert "Envio de notificações" not in avisos[0].getMessage()


def test_a_tarefa_periodica_da_verificacao() -> None:  # A-11
    from procrastinate.contrib.django import app

    from apps.operacao import tarefas
    from apps.operacao.catalogo import TAREFAS_MONITORADAS
    from apps.operacao.models import ExecucaoDaTarefa

    candidatas = [
        p
        for p in app.periodic_registry.periodic_tasks.values()
        if p.task.name == "verificar_operacao"
    ]
    assert len(candidatas) == 1
    assert candidatas[0].cron == "*/5 * * * *"
    assert candidatas[0].task.queueing_lock == "verificar_operacao"
    entrada = next(t for t in TAREFAS_MONITORADAS if t.nome == "verificar_operacao")
    assert entrada.descricao == "Verificação operacional"
    assert (entrada.intervalo, entrada.tolerancia) == (5 * MIN, 15 * MIN)
    tarefas.verificar_operacao(timestamp=0)
    assert ExecucaoDaTarefa.objects.get(nome="verificar_operacao").ultima_conclusao_em is not None


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True)
def test_duas_verificacoes_ao_mesmo_tempo(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-12
    from apps.operacao import verificacao
    from tests.apoio.corrida import Corrida

    ao = arranjo_ao(relogio)
    concluir_todas(INSTANTE + 6 * MIN, exceto=(ENVIOS,))
    relogio.congelar(INSTANTE + 6 * MIN)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, verificacao, "abrir_alerta")
    ra, rb = corrida.rodar(
        verificacao.verificar_operacao_agora,
        verificacao.verificar_operacao_agora,
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert rb.excecao is None, repr(rb.excecao)
    assert corrida.b_esperou
    assert len(alertas("tarefa_atrasada", abertos=True)) == 1
    assert len(notificacoes(ao.adm1)) == 1


def test_o_critico_vem_primeiro(relogio: RelogioControlado, ao: Ao) -> None:  # A-13
    from apps.financeiro.alertas import abrir_alerta, alertas_abertos

    _atrasar_envios(relogio, INSTANTE + 6 * MIN)
    with transaction.atomic():
        abrir_alerta("invariante_violado", "geral", {"diferenca": "10.00"})
    assert [a.tipo for a in alertas_abertos()] == ["invariante_violado", "tarefa_atrasada"]


def test_link_e_natureza_do_alerta(relogio: RelogioControlado, ao: Ao) -> None:  # A-14
    from apps.operacao.verificacao import link_do_alerta, natureza_do_alerta

    from apps.financeiro.alertas import abrir_alerta

    _atrasar_envios(relogio, INSTANTE + 6 * MIN)
    with transaction.atomic():
        financeiro = abrir_alerta("invariante_violado", "geral", {"diferenca": "10.00"})
    (operacional,) = alertas("tarefa_atrasada")
    assert link_do_alerta(operacional) == "/administracao/"
    assert natureza_do_alerta(operacional) == "condicao"
    assert link_do_alerta(financeiro) == "/administracao/financeiro/"
    assert natureza_do_alerta(financeiro) is None


def test_comprador_e_fornecedor_nao_recebem(relogio: RelogioControlado, ao: Ao) -> None:  # A-15
    _atrasar_envios(relogio, INSTANTE + 6 * MIN)
    assert notificacoes(ao.c) == []
    assert notificacoes(ao.f) == []
