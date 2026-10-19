"""E07-03: registro dos pagamentos e reconhecimento único (acceptance A-1 a A-11 e A-15)."""

import logging
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.transaction import TransactionManagementError

from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from apps.pagamentos.models import ConsultaDoPagamento, PagamentoNoProvedor
from apps.pagamentos.provedor import NovaCobranca, SituacaoNoProvedor, obter_provedor
from apps.pagamentos.sinais import situacao_do_pagamento_mudou
from apps.pagamentos.sincronizacao import sincronizar_pagamento
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
ACAO = "pagamento.situacao"
CRIACAO = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
T = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)
AMANHA = datetime(2026, 11, 3, 13, 0, tzinfo=UTC)


class Sinais:
    """Receptor que registra cada envio do sinal."""

    def __init__(self) -> None:
        self.recebidos: list[tuple[PagamentoNoProvedor, Any, Any]] = []

    def __call__(self, sender: Any, pagamento: Any, anterior: Any, atual: Any, **kw: Any) -> None:
        self.recebidos.append((pagamento, anterior, atual))


@pytest.fixture
def sinais() -> Iterator[Sinais]:
    receptor = Sinais()
    situacao_do_pagamento_mudou.connect(receptor, weak=False, dispatch_uid="teste-sinais")
    yield receptor
    situacao_do_pagamento_mudou.disconnect(dispatch_uid="teste-sinais")


@pytest.fixture
def p(relogio: RelogioControlado, simulador_pagamentos: Any, sinais: Sinais) -> str:
    """A cobrança simulada pendente `P`, criada às 12:00; o relógio fica em 13:00."""
    relogio.congelar(CRIACAO)
    nova = NovaCobranca("k1", "ref-1", D("45.90"), "Pedido de teste", AMANHA)
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    relogio.congelar(T)
    return id_externo


def consulta(id_externo: str) -> Any:
    return obter_provedor().consultar_pagamento(id_externo)


def sincronizar(id_externo: str, origem: str = "tarefa", **kwargs: Any) -> Any:
    with transaction.atomic():
        return sincronizar_pagamento(consulta(id_externo), origem=origem, **kwargs)


def unico(itens: Any) -> Any:
    achados = list(itens)
    assert len(achados) == 1, f"esperava 1 registro, há {len(achados)}"
    return achados[0]


def registro() -> PagamentoNoProvedor:
    pagamento: PagamentoNoProvedor = unico(PagamentoNoProvedor.objects.all())
    return pagamento


def auditorias() -> list[EntradaAuditoria]:
    return list(EntradaAuditoria.objects.filter(acao=ACAO).order_by("pk"))


def aprovada_e_sincronizada(p: str, relogio: RelogioControlado, sim: Any) -> None:
    """O estado do A-2: registro pendente às 13:00, aprovado em 13:05 e sincronizado às 13:20."""
    sincronizar(p)
    sim.aprovar(p, em=T + timedelta(minutes=5))
    relogio.congelar(T + timedelta(minutes=20))
    sincronizar(p, "aviso", aviso_recebido_em=T + timedelta(minutes=19))


def test_a_primeira_consulta_cria_o_registro(p: str, sinais: Sinais) -> None:  # A-1
    resultado = sincronizar(p)
    pagamento = registro()
    assert pagamento.provedor == "simulador"
    assert pagamento.ambiente == "testes"
    assert pagamento.id_externo == p
    assert pagamento.referencia_externa == "ref-1"
    assert pagamento.valor == D("45.90")
    assert pagamento.situacao == SituacaoNoProvedor.PENDENTE
    assert pagamento.criado_no_provedor_em == CRIACAO
    assert pagamento.aprovado_no_provedor_em is None
    assert pagamento.primeira_consulta_em == T
    assert pagamento.ultima_consulta_em == T
    historico: ConsultaDoPagamento = unico(ConsultaDoPagamento.objects.all())
    assert historico.aplicada is True
    assert auditorias() == []
    assert sinais.recebidos == []
    assert resultado.mudou is False
    assert resultado.pagamento == pagamento


def test_a_aprovacao_e_aplicada_com_os_quatro_instantes(
    p: str, relogio: RelogioControlado, simulador_pagamentos: Any, sinais: Sinais
) -> None:  # A-2
    aprovada_e_sincronizada(p, relogio, simulador_pagamentos)
    pagamento = registro()
    assert pagamento.situacao == SituacaoNoProvedor.APROVADO
    assert pagamento.aprovado_no_provedor_em == T + timedelta(minutes=5)
    assert pagamento.primeiro_aviso_em == T + timedelta(minutes=19)
    assert pagamento.ultima_consulta_em == T + timedelta(minutes=20)
    assert pagamento.criado_no_provedor_em == CRIACAO
    entrada: EntradaAuditoria = unico(auditorias())
    assert entrada.objeto_id == str(pagamento.pk)
    assert entrada.alteracoes == {
        "id_externo": p,
        "anterior": "pendente",
        "atual": "aprovado",
        "aprovado_em": "2026-11-02T13:05:00+00:00",
        "origem": "aviso",
    }
    assert sinais.recebidos == [
        (pagamento, SituacaoNoProvedor.PENDENTE, SituacaoNoProvedor.APROVADO)
    ]


@pytest.mark.acceptance
def test_consultas_repetidas_nao_repetem_efeitos(
    p: str, relogio: RelogioControlado, simulador_pagamentos: Any, sinais: Sinais
) -> None:  # A-3, cenário 17 (pagamento)
    aprovada_e_sincronizada(p, relogio, simulador_pagamentos)
    sincronizar(p)
    sincronizar(p)
    sincronizar(p, aviso_recebido_em=T + timedelta(minutes=40))
    assert len(auditorias()) == 1
    assert len(sinais.recebidos) == 1
    assert registro().primeiro_aviso_em == T + timedelta(minutes=19)
    historico = list(ConsultaDoPagamento.objects.order_by("pk"))
    assert len(historico) == 5
    assert [h.aplicada for h in historico[-3:]] == [False, False, False]


def test_o_primeiro_registro_ja_aprovado(
    p: str, simulador_pagamentos: Any, sinais: Sinais
) -> None:  # A-4
    simulador_pagamentos.aprovar(p, em=T)
    sincronizar(p, "busca")
    assert registro().situacao == SituacaoNoProvedor.APROVADO
    entrada: EntradaAuditoria = unico(auditorias())
    assert entrada.alteracoes["anterior"] is None
    assert entrada.alteracoes["atual"] == "aprovado"
    assert [(a, b) for _, a, b in sinais.recebidos] == [(None, SituacaoNoProvedor.APROVADO)]


def test_leitura_atrasada_nao_volta_atras(
    p: str, relogio: RelogioControlado, simulador_pagamentos: Any, sinais: Sinais
) -> None:  # A-5
    aprovada_e_sincronizada(p, relogio, simulador_pagamentos)
    simulador_pagamentos.atrasar_consistencia(p, consultas=1)
    sincronizar(p)
    assert registro().situacao == SituacaoNoProvedor.APROVADO
    ultima = ConsultaDoPagamento.objects.latest("pk")
    assert ultima.situacao == "pendente"
    assert ultima.aplicada is False
    assert len(auditorias()) == 1
    assert len(sinais.recebidos) == 1


def test_cancelado_pode_virar_aprovado(
    p: str, simulador_pagamentos: Any, sinais: Sinais
) -> None:  # A-6
    obter_provedor().cancelar_cobranca(p)
    sincronizar(p)
    assert registro().situacao == SituacaoNoProvedor.CANCELADO
    simulador_pagamentos.aprovar(p, em=T + timedelta(minutes=30))
    sincronizar(p)
    pagamento = registro()
    assert pagamento.situacao == SituacaoNoProvedor.APROVADO
    assert pagamento.aprovado_no_provedor_em == T + timedelta(minutes=30)
    assert [(a, b) for _, a, b in sinais.recebidos][-1] == (
        SituacaoNoProvedor.CANCELADO,
        SituacaoNoProvedor.APROVADO,
    )
    assert len(auditorias()) == 2


@pytest.mark.parametrize(
    ("campo", "mudanca"),
    [
        ("referencia", {"referencia_externa": "ref-outra"}),
        ("valor", {"valor": D("50.00")}),
        ("criacao", {"criado_em": CRIACAO + timedelta(hours=1)}),
        ("aprovacao", {"aprovado_em": T + timedelta(minutes=50)}),
    ],
)
def test_resposta_divergente_nao_altera_a_identidade(
    campo: str,
    mudanca: dict[str, Any],
    p: str,
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-7
    aprovada_e_sincronizada(p, relogio, simulador_pagamentos)
    original = registro()
    caplog.set_level(logging.INFO)
    resposta = replace(consulta(p), **mudanca)
    with transaction.atomic():
        sincronizar_pagamento(resposta, origem="tarefa")
    atual = registro()
    assert atual.referencia_externa == original.referencia_externa == "ref-1"
    assert atual.valor == original.valor == D("45.90")
    assert atual.criado_no_provedor_em == original.criado_no_provedor_em == CRIACAO
    assert atual.aprovado_no_provedor_em == original.aprovado_no_provedor_em
    ultima = ConsultaDoPagamento.objects.latest("pk")
    assert ultima.divergencia == campo
    assert ultima.aplicada is False
    assert len(auditorias()) == 1
    mensagens = [r.getMessage() for r in caplog.records]
    assert any(f"divergência em {campo}" in m and p in m for m in mensagens)
    for m in mensagens:
        for proibido in ("ref-outra", "50.00", "45.90", "ref-1"):
            assert proibido not in m, m


def test_o_historico_so_aceita_insercao(p: str) -> None:  # A-8
    sincronizar(p)
    historico: ConsultaDoPagamento = unico(ConsultaDoPagamento.objects.all())
    historico.aplicada = False
    with pytest.raises(RegistroImutavel):
        historico.save()
    with pytest.raises(RegistroImutavel):
        historico.delete()
    with pytest.raises(RegistroImutavel):
        ConsultaDoPagamento.objects.all().update(aplicada=False)
    for sql in (
        "UPDATE pagamentos_consultadopagamento SET aplicada = false",
        "DELETE FROM pagamentos_consultadopagamento",
    ):
        with (
            pytest.raises(DatabaseError, match="só aceita inserção"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(sql)
    assert unico(ConsultaDoPagamento.objects.all()).aplicada is True


def test_restricoes_do_banco(p: str) -> None:  # A-9
    sincronizar(p)
    existente = registro()
    campos: dict[str, Any] = {
        "provedor": existente.provedor,
        "ambiente": "testes",
        "id_externo": existente.id_externo,
        "referencia_externa": "ref-9",
        "valor": D("10.00"),
        "situacao": "pendente",
        "criado_no_provedor_em": CRIACAO,
        "expira_em": AMANHA,
    }
    casos = [
        campos,
        {**campos, "id_externo": "sim-outro", "valor": D("0")},
        {**campos, "id_externo": "sim-outro", "situacao": "paga"},
    ]
    for caso in casos:
        with pytest.raises(IntegrityError), transaction.atomic():
            PagamentoNoProvedor.objects.create(**caso)
    assert PagamentoNoProvedor.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_exige_transacao_e_origem_valida(p: str) -> None:  # A-10
    resposta = consulta(p)
    with pytest.raises(TransactionManagementError):
        sincronizar_pagamento(resposta, origem="tarefa")
    with pytest.raises(ValueError, match="origem"), transaction.atomic():
        sincronizar_pagamento(resposta, origem="manual")
    assert PagamentoNoProvedor.objects.count() == 0
    assert ConsultaDoPagamento.objects.count() == 0


def test_receptor_que_falha_desfaz_a_sincronizacao(
    p: str, simulador_pagamentos: Any, sinais: Sinais
) -> None:  # A-11
    simulador_pagamentos.aprovar(p, em=T)

    def estoura(sender: Any, **kwargs: Any) -> None:
        raise RuntimeError("receptor com defeito")

    situacao_do_pagamento_mudou.connect(estoura, weak=False, dispatch_uid="teste-estoura")
    try:
        with transaction.atomic(), pytest.raises(RuntimeError):
            sincronizar_pagamento(consulta(p), origem="tarefa")
        assert PagamentoNoProvedor.objects.count() == 0
        assert ConsultaDoPagamento.objects.count() == 0
        assert auditorias() == []
    finally:
        situacao_do_pagamento_mudou.disconnect(dispatch_uid="teste-estoura")
    sincronizar(p)
    assert registro().situacao == SituacaoNoProvedor.APROVADO
    assert len(auditorias()) == 1


def test_os_registros_nao_guardam_dados_do_pagador(
    p: str, caplog: pytest.LogCaptureFixture
) -> None:
    # A-15
    caplog.set_level(logging.DEBUG)
    sincronizar(p)
    nomes = {
        campo.name
        for modelo in (PagamentoNoProvedor, ConsultaDoPagamento)
        for campo in modelo._meta.get_fields()
    }
    for nome in nomes:
        for proibido in ("nome", "email", "documento", "cpf", "telefone", "pix", "pagar"):
            assert proibido not in nome, nome
    for registro_do_log in caplog.records:
        if registro_do_log.name.startswith("apps.pagamentos"):
            mensagem = registro_do_log.getMessage()
            for proibido in ("45.90", "ref-1", "SIMULADO-"):
                assert proibido not in mensagem, mensagem
