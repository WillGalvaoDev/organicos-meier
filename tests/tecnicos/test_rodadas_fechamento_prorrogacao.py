"""E06-04: prorrogação do fechamento (acceptance A-1 a A-9)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from apps.catalogo.models import Produto
from apps.contas.models import Conta
from apps.interesses.servicos import adicionar_interesse, reduzir_interesse
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.tempo import InstanteSemFuso
from apps.rodadas.fechamento import (
    TransicaoRecusada,
    iniciar_fechamento,
    prazo_do_fechamento,
    prorrogar_fechamento,
)
from apps.rodadas.models import Etapa, OrigemDoPrazo, PrazoDoFechamento, Rodada
from tests.apoio.interesses import cenario, reservada
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, RodadaFactory

pytestmark = pytest.mark.django_db

D = Decimal
T0 = datetime(2026, 11, 2, 13, 30, tzinfo=UTC)
T = datetime(2026, 11, 3, 13, 30, tzinfo=UTC)
H = timedelta(hours=1)
MS = timedelta(milliseconds=1)
ACAO = "rodada.prorrogar_fechamento"


def admin() -> Conta:
    return Conta.objects.get(papel="administrador")


def em_fechamento(relogio: RelogioControlado) -> tuple[Rodada, Produto, Conta]:
    relogio.congelar(T0)
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    a = ContaFactory.create()
    reservada(a, produto, 10)
    iniciar_fechamento(admin(), rodada)
    return rodada, produto, a


def linhas() -> int:
    return PrazoDoFechamento.objects.count()


def nada_mudou(rodada: Rodada) -> None:
    assert linhas() == 1
    assert prazo_do_fechamento(rodada) == T
    assert EntradaAuditoria.objects.filter(acao=ACAO).count() == 0


@pytest.mark.acceptance
def test_prorrogacao_estende_o_prazo_e_audita(relogio: RelogioControlado) -> None:
    # A-1, cenário 28
    rodada, _, _ = em_fechamento(relogio)
    relogio.congelar(T - 2 * H)
    novo = T + 24 * H
    assert prorrogar_fechamento(admin(), rodada, novo) == novo
    assert prazo_do_fechamento(rodada) == novo
    origens = list(PrazoDoFechamento.objects.order_by("pk").values_list("origem", flat=True))
    assert origens == [OrigemDoPrazo.INICIO, OrigemDoPrazo.PRORROGACAO]
    (entrada,) = EntradaAuditoria.objects.filter(acao=ACAO)
    assert entrada.objeto_id == str(rodada.pk)
    ciclo = PrazoDoFechamento.objects.latest("pk").ciclo
    assert entrada.alteracoes == {
        "rodada": rodada.pk,
        "ciclo": ciclo.pk,
        "anterior": T.isoformat(),
        "novo": novo.isoformat(),
    }


def test_o_bloqueio_usa_o_prazo_novo(relogio: RelogioControlado) -> None:  # A-2
    rodada, produto, _ = em_fechamento(relogio)
    relogio.congelar(T - 2 * H)
    prorrogar_fechamento(admin(), rodada, T + 24 * H)
    relogio.congelar(T + H)
    b = ContaFactory.create()
    assert adicionar_interesse(b, produto, "1").reservado == D("1")


def test_prorrogacoes_sucessivas(relogio: RelogioControlado) -> None:  # A-3
    rodada, _, _ = em_fechamento(relogio)
    relogio.congelar(T - 2 * H)
    prorrogar_fechamento(admin(), rodada, T + 24 * H)
    prorrogar_fechamento(admin(), rodada, T + 48 * H)
    assert prazo_do_fechamento(rodada) == T + 48 * H
    assert linhas() == 3
    assert EntradaAuditoria.objects.filter(acao=ACAO).count() == 2


@pytest.mark.parametrize(
    ("instante", "aceita"), [(T - MS, True), (T, False), (T + MS, False)], ids=["-1ms", "0", "+1ms"]
)
def test_fronteira_da_prorrogacao(
    instante: datetime, aceita: bool, relogio: RelogioControlado
) -> None:  # A-4
    rodada, _, _ = em_fechamento(relogio)
    relogio.congelar(instante)
    if aceita:
        assert prorrogar_fechamento(admin(), rodada, T + H) == T + H
        return
    with pytest.raises(TransicaoRecusada) as erro:
        prorrogar_fechamento(admin(), rodada, T + H)
    assert erro.value.codigo == "prazo_encerrado"
    assert erro.value.mensagem == (
        "O prazo deste fechamento já terminou e não pode mais ser prorrogado."
    )
    nada_mudou(rodada)
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO


@pytest.mark.parametrize("novo", [T, T - H], ids=["igual", "anterior"])
def test_o_novo_prazo_tem_de_ser_posterior(novo: datetime, relogio: RelogioControlado) -> None:
    # A-5
    rodada, _, _ = em_fechamento(relogio)
    relogio.congelar(T - 2 * H)
    with pytest.raises(TransicaoRecusada) as erro:
        prorrogar_fechamento(admin(), rodada, novo)
    assert erro.value.codigo == "prazo_nao_posterior"
    assert erro.value.mensagem == (
        "O novo prazo precisa ser posterior ao prazo atual, 03/11/2026 às 10:30."
    )
    nada_mudou(rodada)


@pytest.mark.parametrize("situacao", ["interesse", "encerrado", "pagamento", "antiga"])
def test_so_um_fechamento_em_andamento_pode_ser_prorrogado(
    situacao: str, relogio: RelogioControlado
) -> None:  # A-6
    if situacao == "interesse":
        relogio.congelar(T0)
        rodada, _, _ = cenario("20")
    else:
        rodada, _, _ = em_fechamento(relogio)
        relogio.congelar(T - 2 * H)
        if situacao == "encerrado":
            Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.FECHAMENTO_ENCERRADO)
        elif situacao == "pagamento":
            Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.PAGAMENTO)
        else:
            Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.DISPONIVEL_PARA_RETIRADA)
            RodadaFactory.create(fornecedor=rodada.fornecedor)
    antes = linhas()
    with pytest.raises(TransicaoRecusada) as erro:
        prorrogar_fechamento(admin(), rodada, T + 24 * H)
    assert erro.value.codigo == "fora_de_fechamento"
    assert erro.value.mensagem == "Só um fechamento em andamento pode ser prorrogado."
    assert linhas() == antes
    assert EntradaAuditoria.objects.filter(acao=ACAO).count() == 0


@pytest.mark.parametrize("quem", ["comprador", "fornecedor", "anonimo"])
def test_so_o_administrador_prorroga(quem: str, relogio: RelogioControlado) -> None:  # A-7
    rodada, _, _ = em_fechamento(relogio)
    relogio.congelar(T - 2 * H)
    autor = {
        "comprador": lambda: ContaFactory.create(),
        "fornecedor": lambda: ContaFactory.create(fornecedor=True),
        "anonimo": lambda: None,
    }[quem]()
    with pytest.raises(PermissionDenied):
        prorrogar_fechamento(autor, rodada, T + 24 * H)
    nada_mudou(rodada)


def test_instante_sem_fuso_e_erro_de_programacao(relogio: RelogioControlado) -> None:  # A-8
    rodada, _, _ = em_fechamento(relogio)
    relogio.congelar(T - 2 * H)
    with pytest.raises(InstanteSemFuso):
        prorrogar_fechamento(admin(), rodada, datetime(2026, 11, 5, 10, 0))  # noqa: DTZ001
    nada_mudou(rodada)


@pytest.mark.acceptance
def test_a_queda_do_minimo_nao_prorroga(relogio: RelogioControlado) -> None:  # A-9, cenário 5
    rodada, produto, a = em_fechamento(relogio)
    relogio.congelar(T - 2 * H)
    reduzir_interesse(a, produto, "9")
    assert prazo_do_fechamento(rodada) == T
    assert not PrazoDoFechamento.objects.filter(origem=OrigemDoPrazo.PRORROGACAO).exists()
