"""E15-01: o registro da execução das tarefas periódicas e o cálculo de "tarefa atrasada"
(acceptance A-1 a A-14)."""

import importlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import transaction

from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

INSTANTE = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
MIN = timedelta(minutes=1)

# nome da tarefa -> (módulo da tarefa, função da tarefa, módulo e nome da função de domínio)
TAREFAS = {
    "processar_envios_pendentes": (
        "apps.notificacoes.tarefas",
        "processar_envios_pendentes",
        "apps.notificacoes.tarefas",
        "processar_envios",
    ),
    "processar_chamadas_ao_provedor": (
        "apps.pagamentos.tarefas",
        "processar_chamadas_ao_provedor",
        "apps.pagamentos.tarefas",
        "processar_chamadas",
    ),
    "encerrar_fechamentos_vencidos": (
        "apps.rodadas.tarefas",
        "encerrar_fechamentos_vencidos_agora",
        "apps.rodadas.tarefas",
        "encerrar_fechamentos_vencidos",
    ),
    "bloquear_tentativas_vencidas": (
        "apps.pedidos.tarefas",
        "bloquear_tentativas_vencidas",
        "apps.pedidos.tarefas",
        "bloquear_tentativas_vencidas_agora",
    ),
    "enviar_pedidos_formais": (
        "apps.pedidos.tarefas",
        "enviar_pedidos_formais",
        "apps.pedidos.envio_do_pedido_formal",
        "processar_pedidos_formais",
    ),
    "registrar_tarifas_pendentes": (
        "apps.financeiro.tarefas",
        "registrar_tarifas_pendentes",
        "apps.financeiro.tarefas",
        "registrar_tarifas_pendentes_agora",
    ),
    "verificar_invariante": (
        "apps.financeiro.tarefas",
        "verificar_invariante",
        "apps.financeiro.tarefas",
        "verificar_invariante_agora",
    ),
    "reconsultar_pagamentos_da_margem": (
        "apps.pedidos.tarefas",
        "reconsultar_pagamentos_da_margem",
        "apps.pedidos.tarefas",
        "reconsultar_pagamentos_da_margem_agora",
    ),
    "autorizar_devolucoes_do_cancelamento": (
        "apps.pedidos.tarefas",
        "autorizar_devolucoes_do_cancelamento",
        "apps.pedidos.cancelamento_da_rodada",
        "autorizar_devolucoes_do_cancelamento_agora",
    ),
    "conciliar_dias_pendentes": (
        "apps.financeiro.tarefas",
        "conciliar_dias_pendentes",
        "apps.financeiro.tarefas",
        "conciliar_dias_pendentes_agora",
    ),
}


@pytest.fixture(autouse=True)
def _relogio(relogio: RelogioControlado) -> None:
    relogio.congelar(INSTANTE)


def _execucao(nome: str) -> Any:
    from apps.operacao.models import ExecucaoDaTarefa

    return ExecucaoDaTarefa.objects.get(nome=nome)


def _monitorar(nome: str, corpo: Any = None) -> None:
    from apps.operacao.execucao import execucao_monitorada

    with execucao_monitorada(nome):
        if corpo is not None:
            corpo()


def _falhar(erro: Exception) -> Any:
    def corpo() -> None:
        raise erro

    return corpo


def test_a_primeira_conclusao_cria_o_registro() -> None:  # A-1
    _monitorar("processar_envios_pendentes")
    registro = _execucao("processar_envios_pendentes")
    assert registro.monitorada_desde == INSTANTE
    assert registro.ultima_conclusao_em == INSTANTE
    assert registro.falhas_seguidas == 0
    assert registro.ultima_falha_em is None
    assert registro.ultimo_erro == ""


def test_a_falha_e_relancada_sem_a_mensagem(relogio: RelogioControlado) -> None:  # A-2
    _monitorar("processar_envios_pendentes")
    relogio.congelar(INSTANTE + MIN)
    with pytest.raises(RuntimeError):
        _monitorar("processar_envios_pendentes", _falhar(RuntimeError("dado sensível")))
    registro = _execucao("processar_envios_pendentes")
    assert registro.ultima_falha_em == INSTANTE + MIN
    assert registro.ultimo_erro == "RuntimeError"
    assert registro.falhas_seguidas == 1
    assert registro.ultima_conclusao_em == INSTANTE


def test_a_conclusao_zera_as_falhas(relogio: RelogioControlado) -> None:  # A-3
    _monitorar("processar_envios_pendentes")
    for minutos in (1, 2):
        relogio.congelar(INSTANTE + minutos * MIN)
        with pytest.raises(RuntimeError):
            _monitorar("processar_envios_pendentes", _falhar(RuntimeError("x")))
    assert _execucao("processar_envios_pendentes").falhas_seguidas == 2
    relogio.congelar(INSTANTE + 3 * MIN)
    _monitorar("processar_envios_pendentes")
    registro = _execucao("processar_envios_pendentes")
    assert registro.falhas_seguidas == 0
    assert registro.ultima_conclusao_em == INSTANTE + 3 * MIN
    assert registro.ultima_falha_em == INSTANTE + 2 * MIN
    assert registro.ultimo_erro == "RuntimeError"


def test_nome_fora_do_catalogo() -> None:  # A-4
    from apps.operacao.execucao import execucao_monitorada
    from apps.operacao.models import ExecucaoDaTarefa

    executou: list[int] = []
    with pytest.raises(ValueError):  # noqa: PT012
        with execucao_monitorada("tarefa_inexistente"):
            executou.append(1)
    assert not executou
    assert not ExecucaoDaTarefa.objects.exists()


def _dubla(monkeypatch: pytest.MonkeyPatch, nome: str, erro: Exception | None = None) -> list[int]:
    _modulo_da_tarefa, _funcao, modulo_de_dominio, funcao_de_dominio = TAREFAS[nome]
    chamadas: list[int] = []

    def falso(*args: Any, **kwargs: Any) -> None:
        chamadas.append(1)
        if erro is not None:
            raise erro

    monkeypatch.setattr(importlib.import_module(modulo_de_dominio), funcao_de_dominio, falso)
    return chamadas


def _chamar(nome: str) -> None:
    modulo, funcao, _m, _f = TAREFAS[nome]
    getattr(importlib.import_module(modulo), funcao)(timestamp=0)


def test_cada_tarefa_do_catalogo_e_registrada(monkeypatch: pytest.MonkeyPatch) -> None:  # A-5
    from apps.operacao.catalogo import TAREFAS_MONITORADAS
    from apps.operacao.models import ExecucaoDaTarefa

    assert [t.nome for t in TAREFAS_MONITORADAS][:10] == list(TAREFAS)
    chamadas = {nome: _dubla(monkeypatch, nome) for nome in TAREFAS}
    for nome in TAREFAS:
        _chamar(nome)
    assert all(c == [1] for c in chamadas.values())
    registros = {r.nome: r for r in ExecucaoDaTarefa.objects.all()}
    assert set(TAREFAS) <= set(registros)
    assert all(registros[nome].ultima_conclusao_em == INSTANTE for nome in TAREFAS)


def test_a_excecao_da_tarefa_sai_e_fica_registrada(monkeypatch: pytest.MonkeyPatch) -> None:  # A-6
    _dubla(monkeypatch, "verificar_invariante", ValueError("x"))
    with pytest.raises(ValueError):
        _chamar("verificar_invariante")
    registro = _execucao("verificar_invariante")
    assert registro.falhas_seguidas == 1
    assert registro.ultimo_erro == "ValueError"


def test_o_registro_sobrevive_ao_desfazer_do_corpo() -> None:  # A-7
    from apps.operacao.models import ExecucaoDaTarefa

    def corpo() -> None:
        with transaction.atomic():
            ExecucaoDaTarefa.objects.create(nome="objeto-do-corpo", monitorada_desde=INSTANTE)
            raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        _monitorar("processar_envios_pendentes", corpo)
    assert not ExecucaoDaTarefa.objects.filter(nome="objeto-do-corpo").exists()
    assert _execucao("processar_envios_pendentes").falhas_seguidas == 1


def test_falha_ao_gravar_vai_para_o_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:  # A-8
    from apps.operacao import execucao

    class Quebrado:
        def __getattr__(self, nome: str) -> Any:
            raise RuntimeError("banco indisponível")

    monkeypatch.setattr(execucao.ExecucaoDaTarefa, "objects", Quebrado())
    corpo_rodou: list[int] = []
    with caplog.at_level(logging.ERROR):
        _monitorar("processar_envios_pendentes", lambda: corpo_rodou.append(1))
    assert corpo_rodou == [1]
    texto = " ".join(r.getMessage() for r in caplog.records)
    assert "processar_envios_pendentes" in texto
    assert "RuntimeError" in texto


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True)
def test_duas_primeiras_execucoes_simultaneas(monkeypatch: pytest.MonkeyPatch) -> None:  # A-9
    from apps.operacao import execucao
    from apps.operacao.models import ExecucaoDaTarefa
    from tests.apoio.corrida import Corrida

    corrida = Corrida()
    corrida.depois_de(monkeypatch, execucao, "_criar")
    ra, rb = corrida.rodar(
        lambda: _monitorar("processar_envios_pendentes"),
        lambda: _monitorar("processar_envios_pendentes"),
        a_atomica=False,
        b_atomica=False,
    )
    assert ra.excecao is None, repr(ra.excecao)
    assert rb.excecao is None, repr(rb.excecao)
    assert corrida.b_esperou
    assert ExecucaoDaTarefa.objects.count() == 1
    assert _execucao("processar_envios_pendentes").ultima_conclusao_em is not None


def test_o_instante_nao_volta_no_tempo(relogio: RelogioControlado) -> None:  # A-10
    _monitorar("processar_envios_pendentes")
    relogio.congelar(INSTANTE - MIN)
    _monitorar("processar_envios_pendentes")
    assert _execucao("processar_envios_pendentes").ultima_conclusao_em == INSTANTE
    relogio.congelar(INSTANTE + MIN)
    with pytest.raises(RuntimeError):
        _monitorar("processar_envios_pendentes", _falhar(RuntimeError("x")))
    relogio.congelar(INSTANTE)
    with pytest.raises(RuntimeError):
        _monitorar("processar_envios_pendentes", _falhar(RuntimeError("x")))
    assert _execucao("processar_envios_pendentes").ultima_falha_em == INSTANTE + MIN


def _situacao(nome: str, instante: datetime) -> Any:
    from apps.operacao.execucao import situacao_das_tarefas

    return next(s for s in situacao_das_tarefas(instante) if s.nome == nome)


def test_estado_atrasada_e_o_limite() -> None:  # A-11
    for nome in ("processar_envios_pendentes", "verificar_invariante", "conciliar_dias_pendentes"):
        _monitorar(nome)
    envios = "processar_envios_pendentes"
    assert _situacao(envios, INSTANTE + 5 * MIN).estado == "em_dia"
    assert _situacao(envios, INSTANTE + 5 * MIN).atrasada_desde is None
    atrasada = _situacao(envios, INSTANTE + 5 * MIN + timedelta(seconds=1))
    assert atrasada.estado == "atrasada"
    assert atrasada.atrasada_desde == INSTANTE + 5 * MIN
    invariante = "verificar_invariante"
    assert _situacao(invariante, INSTANTE + 30 * MIN).estado == "em_dia"
    assert _situacao(invariante, INSTANTE + 30 * MIN + timedelta(seconds=1)).estado == "atrasada"
    conciliacao = "conciliar_dias_pendentes"
    assert _situacao(conciliacao, INSTANTE + 30 * MIN + timedelta(seconds=1)).estado == "em_dia"
    assert _situacao(conciliacao, INSTANTE + timedelta(hours=3, seconds=1)).estado == "atrasada"


def test_so_falhas_conta_a_partir_do_inicio_do_monitoramento() -> None:  # A-12
    with pytest.raises(RuntimeError):
        _monitorar("enviar_pedidos_formais", _falhar(RuntimeError("x")))
    situacao = _situacao("enviar_pedidos_formais", INSTANTE + 6 * MIN)
    assert situacao.estado == "atrasada"
    assert situacao.atrasada_desde == INSTANTE + 5 * MIN
    assert situacao.ultima_conclusao_em is None
    assert situacao.monitorada_desde == INSTANTE


def test_sem_registro_lista_as_dez_na_ordem_do_catalogo() -> None:  # A-13
    from apps.operacao.catalogo import TAREFAS_MONITORADAS
    from apps.operacao.execucao import situacao_das_tarefas

    itens = situacao_das_tarefas(INSTANTE)
    assert [s.nome for s in itens][:10] == list(TAREFAS)
    assert all(s.estado == "sem_registro" for s in itens)
    por_nome = {t.nome: t for t in TAREFAS_MONITORADAS}
    assert por_nome["processar_envios_pendentes"].descricao == "Envio de notificações"
    assert por_nome["conciliar_dias_pendentes"].descricao == "Conciliação diária"
    assert itens[0].intervalo == MIN
    assert itens[0].tolerancia == 5 * MIN
    assert itens[9].tolerancia == timedelta(hours=3)


def test_nada_sensivel_no_registro_nem_no_log(caplog: pytest.LogCaptureFixture) -> None:  # A-14
    with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError):
        _monitorar("processar_envios_pendentes", _falhar(RuntimeError("dado sensível")))
    registro = _execucao("processar_envios_pendentes")
    assert "dado sensível" not in repr(registro.__dict__)
    assert "dado sensível" not in " ".join(r.getMessage() for r in caplog.records)
