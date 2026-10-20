"""E07-06: consulta ao provedor antes de decisões irreversíveis (acceptance A-1 a A-9)."""

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction

from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou, consultar_antes_de_decidir
from apps.pagamentos.models import ConsultaDoPagamento, PagamentoNoProvedor
from apps.pagamentos.provedor import (
    NovaCobranca,
    PagamentoConsultado,
    ProvedorIndisponivel,
    SituacaoNoProvedor,
    obter_provedor,
)
from apps.pagamentos.sinais import situacao_do_pagamento_mudou
from apps.pagamentos.sincronizacao import sincronizar_pagamento
from apps.simulador_pagamentos.provedor import ProvedorSimulado
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
REFERENCIA = "ref-1"
CRIACAO = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
T = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)
AMANHA = datetime(2026, 11, 3, 13, 0, tzinfo=UTC)
MIN = timedelta(minutes=1)


class Sinais:
    def __init__(self) -> None:
        self.recebidos: list[tuple[Any, Any]] = []

    def __call__(self, sender: Any, anterior: Any, atual: Any, **kwargs: Any) -> None:
        self.recebidos.append((anterior, atual))


@pytest.fixture
def sinais() -> Iterator[Sinais]:
    receptor = Sinais()
    situacao_do_pagamento_mudou.connect(receptor, weak=False, dispatch_uid="consulta")
    yield receptor
    situacao_do_pagamento_mudou.disconnect(dispatch_uid="consulta")


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any, sinais: Sinais) -> Any:
    relogio.congelar(T)
    return simulador_pagamentos


def cobranca(
    relogio: RelogioControlado, chave: str = "k1", referencia: str = REFERENCIA, criada: int = 0
) -> str:
    """Cria uma cobrança às 12:00 mais `criada` minutos; o relógio volta para 13:00."""
    relogio.congelar(CRIACAO + criada * MIN)
    nova = NovaCobranca(chave, referencia, D("45.90"), "Pedido de teste", AMANHA)
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    relogio.congelar(T)
    return id_externo


def registrar(id_externo: str, origem: str = "tarefa") -> None:
    with transaction.atomic():
        sincronizar_pagamento(obter_provedor().consultar_pagamento(id_externo), origem=origem)


def auditorias() -> int:
    return EntradaAuditoria.objects.filter(acao="pagamento.situacao").count()


def so_o_primeiro(monkeypatch: pytest.MonkeyPatch, ids: list[str]) -> None:
    """A busca do simulador devolve só os pagamentos de `ids`, os demais ficam de fora."""
    original = ProvedorSimulado.buscar_por_referencia

    def parcial(self: ProvedorSimulado, referencia: str) -> list[PagamentoConsultado]:
        return [p for p in original(self, referencia) if p.id_externo in ids]

    monkeypatch.setattr(ProvedorSimulado, "buscar_por_referencia", parcial)


@pytest.mark.acceptance
def test_pagamento_aprovado_sem_aviso_e_identificado(
    sim: Any, relogio: RelogioControlado, sinais: Sinais
) -> None:  # A-1, §8.3 identificado na apuração
    p = cobranca(relogio)
    aprovada_em = CRIACAO + 30 * MIN
    sim.aprovar(p, em=aprovada_em)
    registros = consultar_antes_de_decidir(REFERENCIA)
    assert [r.id_externo for r in registros] == [p]
    assert registros[0].situacao == SituacaoNoProvedor.APROVADO
    assert registros[0].aprovado_no_provedor_em == aprovada_em
    assert registros[0].primeiro_aviso_em is None
    assert [c.origem for c in ConsultaDoPagamento.objects.all()] == ["busca"]
    assert auditorias() == 1
    assert len(sinais.recebidos) == 1


def test_dois_pagamentos_aprovados_da_mesma_referencia(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-2
    p1 = cobranca(relogio, "k1", criada=0)
    p2 = cobranca(relogio, "k2", criada=5)
    cobranca(relogio, "k3", "ref-outra", criada=6)
    sim.aprovar(p1)
    sim.aprovar(p2)
    registros = consultar_antes_de_decidir(REFERENCIA)
    assert [r.id_externo for r in registros] == [p1, p2]
    assert PagamentoNoProvedor.objects.count() == 2


def test_busca_atrasada_e_corrigida_pela_reconsulta(
    sim: Any, relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-3
    p = cobranca(relogio)
    registrar(p)
    sim.aprovar(p)
    so_o_primeiro(monkeypatch, [])
    registros = consultar_antes_de_decidir(REFERENCIA)
    assert [(r.id_externo, r.situacao) for r in registros] == [(p, SituacaoNoProvedor.APROVADO)]
    assert ConsultaDoPagamento.objects.latest("pk").origem == "decisao"


def test_provedor_fora_do_ar_bloqueia(
    sim: Any, relogio: RelogioControlado, caplog: pytest.LogCaptureFixture
) -> None:  # A-4
    p = cobranca(relogio)
    registrar(p)
    sim.indisponivel()
    caplog.set_level(logging.INFO)
    with pytest.raises(ConsultaAoProvedorFalhou) as erro:
        consultar_antes_de_decidir(REFERENCIA)
    assert erro.value.motivo == "indisponivel"
    assert isinstance(erro.value.__cause__, ProvedorIndisponivel)
    assert ConsultaDoPagamento.objects.count() == 1
    mensagens = [r.getMessage() for r in caplog.records if r.name.startswith("apps.pagamentos")]
    assert any(REFERENCIA in m and "indisponivel" in m for m in mensagens)


def test_falha_numa_reconsulta_bloqueia_mas_mantem_o_que_foi_sincronizado(
    sim: Any, relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-5
    p1 = cobranca(relogio, "k1", criada=0)
    p2 = cobranca(relogio, "k2", criada=5)
    registrar(p1)
    registrar(p2)
    sim.aprovar(p1)
    so_o_primeiro(monkeypatch, [p1])
    sim.falhar_proximas(1, operacao="consultar_pagamento")
    with pytest.raises(ConsultaAoProvedorFalhou) as erro:
        consultar_antes_de_decidir(REFERENCIA)
    assert erro.value.motivo == "indisponivel"
    assert PagamentoNoProvedor.objects.get(id_externo=p1).situacao == SituacaoNoProvedor.APROVADO


def test_pagamento_registrado_que_o_provedor_nao_conhece_bloqueia(
    sim: Any, relogio: RelogioControlado
) -> None:  # A-6
    resposta = PagamentoConsultado(
        provedor="simulador",
        id_externo="sim-777",
        referencia_externa=REFERENCIA,
        valor=D("45.90"),
        situacao=SituacaoNoProvedor.PENDENTE,
        criado_em=CRIACAO,
        aprovado_em=None,
        expira_em=AMANHA,
        consultado_em=T,
    )
    with transaction.atomic():
        sincronizar_pagamento(resposta, origem="tarefa")
    with pytest.raises(ConsultaAoProvedorFalhou) as erro:
        consultar_antes_de_decidir(REFERENCIA)
    assert erro.value.motivo == "nao_encontrado"


def test_referencia_sem_pagamento_devolve_lista_vazia(sim: Any) -> None:  # A-7
    assert consultar_antes_de_decidir(REFERENCIA) == []


def test_consultas_repetidas_so_acrescentam_historico(
    sim: Any, relogio: RelogioControlado, sinais: Sinais
) -> None:  # A-8
    p = cobranca(relogio)
    sim.aprovar(p)
    registrar(p)
    antes = ConsultaDoPagamento.objects.count()
    consultar_antes_de_decidir(REFERENCIA)
    consultar_antes_de_decidir(REFERENCIA)
    novas = list(ConsultaDoPagamento.objects.order_by("pk"))[antes:]
    assert [c.origem for c in novas] == ["busca", "busca"]
    assert auditorias() == 1
    assert len(sinais.recebidos) == 1


def test_a_falha_nao_revela_valor_descricao_nem_dados_para_pagar(
    sim: Any, relogio: RelogioControlado, caplog: pytest.LogCaptureFixture
) -> None:  # A-9
    p = cobranca(relogio)
    registrar(p)
    sim.indisponivel()
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ConsultaAoProvedorFalhou) as erro:
        consultar_antes_de_decidir(REFERENCIA)
    textos = [str(erro.value)] + [
        r.getMessage() for r in caplog.records if r.name.startswith("apps.pagamentos")
    ]
    for texto in textos:
        for proibido in ("45.90", "45,90", "Pedido de teste", "SIMULADO-"):
            assert proibido not in texto, texto
