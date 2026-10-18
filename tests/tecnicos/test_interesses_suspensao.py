"""E05-07: interesses do comprador suspenso ou removido (acceptance A-1 a A-7, A-10 a A-13)."""

from decimal import Decimal

import pytest
from django.db import transaction
from django.db.transaction import TransactionManagementError

from apps.catalogo.models import Unidade
from apps.contas.models import Conta, EmailBanido, Situacao
from apps.contas.moderacao import reativar, remover, suspender
from apps.interesses import receptores
from apps.interesses.consultas import total_reservado
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.interesses.servicos import adicionar_interesse, remover_interesses_do_comprador
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.models import Etapa
from tests.apoio.interesses import auditorias, cenario, parcelas, pendente, reservada
from tests.fabricas import ContaFactory, ParcelaFactory, ProdutoFactory

pytestmark = pytest.mark.django_db

D = Decimal
SUSPENSAO = "interesse.remover_por_suspensao"
REMOCAO = "interesse.remover_por_remocao_da_conta"


def admin() -> Conta:
    return Conta.objects.get(papel="administrador")


def estado(parcela: ParcelaDeInteresse) -> tuple[str, Decimal, Decimal]:
    parcela.refresh_from_db()
    return (parcela.situacao, parcela.quantidade_reservada, parcela.quantidade_pendente)


@pytest.mark.acceptance
def test_suspensao_esvazia_os_interesses_e_a_reversao_nao_restaura() -> (
    None
):  # A-1, A-2, cenário 19
    _, p, _ = cenario("10", nome="P")
    _, q, _ = cenario("10", nome="Q")
    r = ProdutoFactory.create(fornecedor=p.fornecedor, unidade=Unidade.UNIDADE, nome="R")
    a = ContaFactory.create()
    adicionar_interesse(a, p, "4")
    adicionar_interesse(a, q, "2")
    espera = pendente(a, r, 3)
    antes = {x.pk: (x.sequencia, x.quantidade_original) for x in ParcelaDeInteresse.objects.all()}
    suspender(admin(), a)
    todas = list(ParcelaDeInteresse.objects.filter(comprador=a))
    assert len(todas) == 3
    for parcela in todas:
        assert (parcela.situacao, parcela.quantidade_reservada, parcela.quantidade_pendente) == (
            SituacaoParcela.REMOVIDA,
            D("0"),
            D("0"),
        )
        assert (parcela.sequencia, parcela.quantidade_original) == antes[parcela.pk]
    assert total_reservado(p) == 0
    assert total_reservado(q) == 0
    (entrada,) = auditorias(SUSPENSAO)
    assert entrada.autor_tipo == EntradaAuditoria.AutorTipo.SISTEMA
    assert entrada.objeto_id == str(a.pk)
    assert {x[0] for x in entrada.alteracoes["parcelas"]} == {x.pk for x in todas}
    assert espera.pk in {x[0] for x in entrada.alteracoes["parcelas"]}
    reativar(admin(), a)
    assert not ParcelaDeInteresse.objects.filter(
        comprador=a, situacao__in=(SituacaoParcela.ATIVA, SituacaoParcela.PENDENTE)
    ).exists()
    adicionar_interesse(a, p, "1")
    nova = parcelas(p, a)[-1]
    assert nova.sequencia > max(sequencia for sequencia, _ in antes.values())


def test_reserva_liberada_vai_para_a_fila_na_mesma_transacao() -> None:  # A-3
    _, p, _ = cenario("4")
    a, c = ContaFactory.create(), ContaFactory.create()
    adicionar_interesse(a, p, "4")
    pc = pendente(c, p, 3)
    suspender(admin(), a)
    assert estado(pc) == (SituacaoParcela.ATIVA, D("3"), D("0"))
    assert total_reservado(p) == D("3")


def test_rodada_que_nao_aceita_reservas_so_libera() -> None:  # A-4
    _, p, _ = cenario("10", etapa=Etapa.FECHAMENTO_ENCERRADO)
    a, c = ContaFactory.create(), ContaFactory.create()
    parcela = reservada(a, p, 2)
    pc = pendente(c, p, 2)
    suspender(admin(), a)
    assert estado(parcela)[0] == SituacaoParcela.REMOVIDA
    assert estado(pc) == (SituacaoParcela.PENDENTE, D("0"), D("2"))


def test_parcela_em_pedido_nao_muda() -> None:  # A-5
    _, p, _ = cenario("10")
    a = ContaFactory.create()
    em_pedido = ParcelaFactory.create(
        comprador=a,
        produto=p,
        quantidade_original=D("2"),
        quantidade_reservada=D("2"),
        situacao=SituacaoParcela.EM_PEDIDO,
    )
    suspender(admin(), a)
    assert estado(em_pedido) == (SituacaoParcela.EM_PEDIDO, D("2"), D("0"))
    assert auditorias(SUSPENSAO) == []


def test_falha_do_receptor_desfaz_a_suspensao(monkeypatch: pytest.MonkeyPatch) -> None:  # A-6
    _, p, _ = cenario("10")
    a = ContaFactory.create()
    adicionar_interesse(a, p, "4")

    def estoura(*args: object, **kwargs: object) -> int:
        raise RuntimeError("falha no receptor")

    monkeypatch.setattr(receptores, "remover_interesses_do_comprador", estoura)
    with pytest.raises(RuntimeError):
        suspender(admin(), a)
    a.refresh_from_db()
    assert a.situacao == Situacao.ATIVA
    assert parcelas(p, a)[0].situacao == SituacaoParcela.ATIVA
    assert parcelas(p, a)[0].quantidade_reservada == D("4")
    assert auditorias(SUSPENSAO) == []
    assert not EntradaAuditoria.objects.filter(acao="conta.suspender").exists()


@pytest.mark.django_db(transaction=True)
def test_exige_transacao_e_motivo_valido() -> None:  # A-7
    a = ContaFactory.create()
    with pytest.raises(TransactionManagementError):
        remover_interesses_do_comprador(a, motivo="suspensao")
    with transaction.atomic(), pytest.raises(ValueError, match="motivo"):
        remover_interesses_do_comprador(a, motivo="outro")


@pytest.mark.acceptance
def test_remocao_da_conta_trata_os_interesses_como_a_suspensao() -> None:  # A-10
    _, p, _ = cenario("4", nome="P")
    _, q, _ = cenario("10", nome="Q")
    r = ProdutoFactory.create(fornecedor=p.fornecedor, unidade=Unidade.UNIDADE, nome="R")
    a, c = ContaFactory.create(), ContaFactory.create()
    adicionar_interesse(a, p, "4")
    adicionar_interesse(a, q, "2")
    pendente(a, r, 3)
    pc = pendente(c, p, 2)
    antes = {
        x.pk: (x.sequencia, x.quantidade_original)
        for x in ParcelaDeInteresse.objects.filter(comprador=a)
    }
    remover(admin(), a)
    for parcela in ParcelaDeInteresse.objects.filter(comprador=a):
        assert estado(parcela) == (SituacaoParcela.REMOVIDA, D("0"), D("0"))
        assert (parcela.sequencia, parcela.quantidade_original) == antes[parcela.pk]
    assert estado(pc) == (SituacaoParcela.ATIVA, D("2"), D("0"))
    (entrada,) = auditorias(REMOCAO)
    assert entrada.autor_tipo == EntradaAuditoria.AutorTipo.SISTEMA
    a.refresh_from_db()
    assert a.situacao == Situacao.REMOVIDA
    assert EmailBanido.objects.filter(email_normalizado=a.email_normalizado).exists()


@pytest.mark.acceptance
def test_remocao_preserva_em_pedido_e_nao_apaga_parcelas() -> None:  # A-11, cenário 20
    _, p, _ = cenario("10", nome="P")
    _, q, _ = cenario("10", nome="Q")
    a = ContaFactory.create()
    em_pedido = ParcelaFactory.create(
        comprador=a,
        produto=p,
        quantidade_original=D("3"),
        quantidade_reservada=D("3"),
        situacao=SituacaoParcela.EM_PEDIDO,
    )
    adicionar_interesse(a, q, "2")
    total = ParcelaDeInteresse.objects.count()
    remover(admin(), a)
    assert estado(em_pedido) == (SituacaoParcela.EM_PEDIDO, D("3"), D("0"))
    assert parcelas(q, a)[0].situacao == SituacaoParcela.REMOVIDA
    assert ParcelaDeInteresse.objects.count() == total


def test_remover_conta_suspensa_ou_de_fornecedor_nao_mexe_em_parcelas() -> None:  # A-12
    _, p, _ = cenario("10")
    a = ContaFactory.create()
    adicionar_interesse(a, p, "2")
    suspender(admin(), a)
    fornecedor = ContaFactory.create(fornecedor=True)
    antes = list(ParcelaDeInteresse.objects.values_list("pk", "situacao"))
    remover(admin(), a)
    remover(admin(), fornecedor)
    assert auditorias(REMOCAO) == []
    assert list(ParcelaDeInteresse.objects.values_list("pk", "situacao")) == antes


def test_falha_do_receptor_desfaz_a_remocao(monkeypatch: pytest.MonkeyPatch) -> None:  # A-13
    _, p, _ = cenario("10")
    a = ContaFactory.create()
    adicionar_interesse(a, p, "4")

    def estoura(*args: object, **kwargs: object) -> int:
        raise RuntimeError("falha no receptor")

    monkeypatch.setattr(receptores, "remover_interesses_do_comprador", estoura)
    with pytest.raises(RuntimeError):
        remover(admin(), a)
    a.refresh_from_db()
    assert a.situacao == Situacao.ATIVA
    assert not EmailBanido.objects.filter(email_normalizado=a.email_normalizado).exists()
    assert parcelas(p, a)[0].quantidade_reservada == D("4")
