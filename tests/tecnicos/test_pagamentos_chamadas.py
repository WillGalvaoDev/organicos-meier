"""E07-04: chamadas pendentes ao provedor (acceptance A-1 a A-13 e A-16)."""

import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.db.transaction import TransactionManagementError

from apps.pagamentos import chamadas
from apps.pagamentos.chamadas import OPERACOES, Operacao, agendar_chamada, processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor, ConsultaDoPagamento, PagamentoNoProvedor
from apps.pagamentos.provedor import NovaCobranca, SituacaoNoProvedor, obter_provedor
from apps.simulador_pagamentos.models import CobrancaSimulada
from apps.simulador_pagamentos.provedor import ProvedorSimulado
from tests.apoio.chamadas import NOME as CRIAR
from tests.apoio.chamadas import operacao_de_teste
from tests.apoio.models import CobrancaDeTeste, FalhaDeTeste
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
CONSULTAR = "consultar_pagamento"
T = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)
AMANHA = datetime(2026, 11, 3, 13, 0, tzinfo=UTC)
MIN = timedelta(minutes=1)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    relogio.congelar(T)
    return simulador_pagamentos


def cobranca(chave: str = "k1", referencia: str = "ref-1") -> str:
    nova = NovaCobranca(chave, referencia, D("45.90"), "Pedido de teste", AMANHA)
    return obter_provedor().criar_cobranca(nova).pagamento.id_externo


@pytest.fixture
def p(sim: Any) -> str:
    return cobranca()


@pytest.fixture
def chamadas_ao_simulador(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Registra cada `consultar_pagamento` que chega ao simulador."""
    registradas: list[str] = []
    original = ProvedorSimulado.consultar_pagamento

    def contar(self: ProvedorSimulado, id_externo: str) -> Any:
        registradas.append(id_externo)
        return original(self, id_externo)

    monkeypatch.setattr(ProvedorSimulado, "consultar_pagamento", contar)
    return registradas


def unica() -> ChamadaAoProvedor:
    todas = list(ChamadaAoProvedor.objects.all())
    assert len(todas) == 1, f"esperava 1 chamada, há {len(todas)}"
    return todas[0]


def recarregar(chamada: ChamadaAoProvedor) -> ChamadaAoProvedor:
    return ChamadaAoProvedor.objects.get(pk=chamada.pk)


def test_agendar_cria_a_chamada_pendente(p: str, chamadas_ao_simulador: list[str]) -> None:  # A-1
    chamada = agendar_chamada(CONSULTAR, p)
    gravada = unica()
    assert gravada.pk == chamada.pk
    assert gravada.operacao == CONSULTAR
    assert gravada.alvo == p
    assert gravada.situacao == "pendente"
    assert gravada.tentativas == 0
    assert gravada.proxima_em == T
    assert gravada.provedor == "simulador"
    assert gravada.ambiente == "testes"
    assert re.fullmatch("[0-9a-f]{32}", gravada.chave_idempotencia)
    assert chamadas_ao_simulador == []


def test_agendar_de_novo_devolve_a_pendente(p: str, relogio: RelogioControlado) -> None:  # A-2
    primeira = agendar_chamada(CONSULTAR, p)
    relogio.congelar(T + 5 * MIN)
    repetidas = [agendar_chamada(CONSULTAR, p) for _ in range(3)]
    assert {r.pk for r in repetidas} == {primeira.pk}
    gravada = unica()
    assert gravada.chave_idempotencia == primeira.chave_idempotencia
    assert gravada.proxima_em == T


@pytest.mark.django_db(transaction=True)
def test_agendar_exige_transacao_e_operacao_registrada(p: str) -> None:  # A-3
    with pytest.raises(TransactionManagementError):
        agendar_chamada(CONSULTAR, p)
    with pytest.raises(ValueError, match="nao_existe"), transaction.atomic():
        agendar_chamada("nao_existe", p)
    assert ChamadaAoProvedor.objects.count() == 0


def test_a_chamada_aprovada_e_sincronizada(p: str, sim: Any) -> None:  # A-4
    sim.aprovar(p)
    agendar_chamada(CONSULTAR, p)
    assert processar_chamadas() == 1
    chamada = unica()
    assert chamada.situacao == "concluida"
    assert chamada.tentativas == 1
    assert chamada.concluida_em == T
    pagamento = PagamentoNoProvedor.objects.get()
    assert pagamento.id_externo == p
    assert pagamento.situacao == SituacaoNoProvedor.APROVADO
    assert ConsultaDoPagamento.objects.get().origem == "tarefa"


def agora_em(relogio: RelogioControlado, instante: datetime) -> int:
    relogio.congelar(instante)
    return processar_chamadas()


def test_novas_tentativas_com_intervalos_crescentes(
    p: str, sim: Any, relogio: RelogioControlado
) -> None:  # A-5, A-6
    sim.indisponivel()
    agendar_chamada(CONSULTAR, p)
    instantes = [T, T + 1 * MIN, T + 6 * MIN, T + 21 * MIN, T + 81 * MIN, T + 141 * MIN]
    proximas = [T + 1 * MIN, T + 6 * MIN, T + 21 * MIN, T + 81 * MIN, T + 141 * MIN, T + 201 * MIN]
    for instante, proxima in zip(instantes, proximas, strict=True):
        assert agora_em(relogio, instante) == 1, instante
        chamada = unica()
        assert chamada.proxima_em == proxima
        assert chamada.ultimo_erro == "indisponivel"
        assert chamada.situacao == "pendente"
        if instante == T + 1 * MIN:
            assert agora_em(relogio, T + 3 * MIN) == 0
            assert unica().tentativas == 2
    assert unica().tentativas == 6
    sim.normalizar()
    assert agora_em(relogio, T + 201 * MIN) == 1
    concluida = unica()
    assert concluida.situacao == "concluida"
    assert concluida.tentativas == 7


def criar_de_teste(chave: str = "k-teste", **parametros: str) -> ChamadaAoProvedor:
    padrao = {"valor": "10.00", "expira_em": AMANHA.isoformat()}
    return agendar_chamada(
        CRIAR, "ref-teste", parametros={**padrao, **parametros}, chave_idempotencia=chave
    )


def test_repeticao_depois_de_o_provedor_aceitar_usa_a_mesma_chave(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-7
    with operacao_de_teste():
        criar_de_teste()
        sim.falhar_proximas(1, operacao="criar_cobranca", depois_de_executar=True)
        assert agora_em(relogio, T) == 1
        assert unica().situacao == "pendente"
        assert CobrancaSimulada.objects.filter(chave_idempotencia="k-teste").count() == 1
        assert agora_em(relogio, T + 1 * MIN) == 1
    assert unica().situacao == "concluida"
    assert CobrancaSimulada.objects.filter(chave_idempotencia="k-teste").count() == 1
    assert CobrancaDeTeste.objects.get().id_externo == CobrancaSimulada.objects.get().id_externo


def test_recusa_definitiva_encerra_a_chamada(sim: Any, relogio: RelogioControlado) -> None:  # A-8
    with operacao_de_teste():
        criar_de_teste(expira_em=(T - timedelta(hours=1)).isoformat())
        assert agora_em(relogio, T) == 1
        chamada = unica()
        assert chamada.situacao == "falhou"
        assert chamada.ultimo_erro == "expiracao_invalida"
        assert chamada.concluida_em == T
        assert FalhaDeTeste.objects.get().codigo == "expiracao_invalida"
        assert agora_em(relogio, T + timedelta(hours=1)) == 0
    assert FalhaDeTeste.objects.count() == 1
    assert unica().tentativas == chamada.tentativas


def test_pagamento_nao_encontrado_ate_24_horas(sim: Any, relogio: RelogioControlado) -> None:  # A-9
    agendar_chamada(CONSULTAR, "sim-999")
    limite = T + timedelta(hours=24)
    instante = T
    for _ in range(60):
        assert agora_em(relogio, instante) == 1
        chamada = unica()
        assert chamada.ultimo_erro == "nao_encontrado"
        if instante >= limite:
            assert chamada.situacao == "falhou"
            assert instante < limite + timedelta(hours=1, minutes=1)
            return
        assert chamada.situacao == "pendente"
        instante = chamada.proxima_em
    pytest.fail("a chamada não chegou ao limite de 24 horas")


def test_uma_chamada_com_falha_nao_impede_as_outras(
    sim: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:  # A-10
    ids = [cobranca(f"k{i}", f"ref-{i}") for i in (1, 2, 3)]
    agendadas = [agendar_chamada(CONSULTAR, id_externo) for id_externo in ids]
    original = OPERACOES[CONSULTAR]

    def concluir(chamada: ChamadaAoProvedor, resultado: Any) -> None:
        if chamada.alvo == ids[1]:
            raise RuntimeError("defeito no concluir")
        original.concluir(chamada, resultado)

    monkeypatch.setitem(OPERACOES, CONSULTAR, Operacao(original.executar, concluir))
    caplog.set_level(logging.INFO)
    assert processar_chamadas() == 3
    primeira, segunda, terceira = (recarregar(c) for c in agendadas)
    assert (primeira.situacao, terceira.situacao) == ("concluida", "concluida")
    assert segunda.situacao == "pendente"
    assert segunda.tentativas == 0
    assert segunda.proxima_em == T
    assert not PagamentoNoProvedor.objects.filter(id_externo=ids[1]).exists()
    assert not ConsultaDoPagamento.objects.filter(pagamento__id_externo=ids[1]).exists()
    mensagens = [r.getMessage() for r in caplog.records if r.name.startswith("apps.pagamentos")]
    falha = [m for m in mensagens if "RuntimeError" in m]
    assert len(falha) == 1
    assert str(segunda.pk) in falha[0]
    assert CONSULTAR in falha[0]
    assert ids[1] not in falha[0]
    monkeypatch.setitem(OPERACOES, CONSULTAR, original)
    assert processar_chamadas() == 1
    assert recarregar(agendadas[1]).situacao == "concluida"


def test_o_limite_do_lote_respeita_a_ordem(sim: Any) -> None:  # A-11
    ids = [cobranca(f"k{i}", f"ref-{i}") for i in range(5)]
    agendadas = [agendar_chamada(CONSULTAR, id_externo) for id_externo in ids]
    # a ordem do lote é (proxima_em, id): a quarta e a quinta chamadas são as mais antigas
    ChamadaAoProvedor.objects.filter(pk=agendadas[3].pk).update(proxima_em=T - 10 * MIN)
    ChamadaAoProvedor.objects.filter(pk=agendadas[4].pk).update(proxima_em=T - 10 * MIN)
    assert processar_chamadas(limite=2) == 2
    situacoes = [recarregar(c).situacao for c in agendadas]
    assert situacoes == ["pendente", "pendente", "pendente", "concluida", "concluida"]


def test_restricoes_da_tabela(p: str) -> None:  # A-12
    existente = agendar_chamada(CONSULTAR, p)
    base: dict[str, Any] = {
        "operacao": CONSULTAR,
        "provedor": "simulador",
        "ambiente": "testes",
    }
    casos = [
        {**base, "alvo": "outro", "chave_idempotencia": existente.chave_idempotencia},
        {**base, "alvo": p, "chave_idempotencia": "chave-diferente"},
        {**base, "alvo": "outro", "chave_idempotencia": "chave-3", "situacao": "perdida"},
    ]
    for caso in casos:
        with pytest.raises(IntegrityError), transaction.atomic():
            ChamadaAoProvedor.objects.create(**caso)
    assert ChamadaAoProvedor.objects.count() == 1


def test_a_tarefa_esta_registrada_como_periodica() -> None:  # A-13
    from procrastinate.contrib.django import app

    nome = "processar_chamadas_ao_provedor"
    candidatas = [
        pt for pt in app.periodic_registry.periodic_tasks.values() if pt.task.name == nome
    ]
    assert len(candidatas) == 1
    assert candidatas[0].cron == "* * * * *"
    assert candidatas[0].task.queueing_lock == nome


def test_o_log_nao_leva_parametros_chave_nem_dados_da_cobranca(
    p: str, sim: Any, relogio: RelogioControlado, caplog: pytest.LogCaptureFixture
) -> None:  # A-16
    caplog.set_level(logging.DEBUG)
    sim.aprovar(p)
    consultada = agendar_chamada(CONSULTAR, p, parametros={"origem": "tarefa"})
    sim.indisponivel()
    processar_chamadas()
    sim.normalizar()
    agora_em(relogio, T + 1 * MIN)
    with operacao_de_teste():
        criada = criar_de_teste(expira_em=(T - timedelta(hours=1)).isoformat())
        agora_em(relogio, T + 2 * MIN)
    mensagens = [r.getMessage() for r in caplog.records if r.name.startswith("apps.pagamentos")]
    assert mensagens
    proibidos = [
        consultada.chave_idempotencia,
        "k-teste",
        "origem",
        "45.90",
        "ref-1",
        "ref-teste",
        "SIMULADO-",
        "valor",
    ]
    for mensagem in mensagens:
        for proibido in proibidos:
            assert proibido not in mensagem, mensagem
    chamada_id = str(consultada.pk)
    assert any(chamada_id in m and CONSULTAR in m for m in mensagens)
    assert any(str(criada.pk) in m and CRIAR in m for m in mensagens)


def test_o_registro_de_operacoes_comeca_com_a_consulta() -> None:
    assert CONSULTAR in chamadas.OPERACOES
    assert CRIAR not in chamadas.OPERACOES


@pytest.fixture(autouse=True)
def _operacao_de_teste_fora_do_registro() -> Iterator[None]:
    yield
    OPERACOES.pop(CRIAR, None)


def test_agendar_de_novo_combina_o_horario_do_aviso(p: str) -> None:  # A-20, E07-R02
    primeira = agendar_chamada(CONSULTAR, p)
    das_13 = {"origem": "aviso", "aviso_recebido_em": "2026-11-02T13:00:00+00:00"}
    fixos = ("chave_idempotencia", "proxima_em", "tentativas", "criada_em")
    antes = {campo: getattr(primeira, campo) for campo in fixos}

    def agendar(parametros: dict[str, Any]) -> ChamadaAoProvedor:
        chamada = agendar_chamada(CONSULTAR, p, parametros=parametros)
        assert chamada.pk == primeira.pk
        gravada = unica()
        assert {campo: getattr(gravada, campo) for campo in fixos} == antes
        return gravada

    assert agendar(das_13).parametros == das_13
    assert (
        agendar({**das_13, "aviso_recebido_em": "2026-11-02T13:05:00+00:00"}).parametros == das_13
    )
    mais_antigo = agendar({**das_13, "aviso_recebido_em": "2026-11-02T09:55:00-03:00"})
    assert mais_antigo.parametros == {**das_13, "aviso_recebido_em": "2026-11-02T12:55:00+00:00"}


def test_operacao_sem_combinar_mantem_os_primeiros_parametros(sim: Any) -> None:  # A-20
    with operacao_de_teste():
        primeira = criar_de_teste(valor="10.00")
        segunda = agendar_chamada(
            CRIAR, "ref-teste", parametros={"valor": "99.00", "expira_em": AMANHA.isoformat()}
        )
        assert segunda.pk == primeira.pk
        assert unica().parametros["valor"] == "10.00"
