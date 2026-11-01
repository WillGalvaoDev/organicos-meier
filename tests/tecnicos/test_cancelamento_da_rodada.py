"""E12-01: cancelamento da rodada, serviço e efeito nos interesses (acceptance A-1 a A-20)."""

import inspect
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.contas.models import Conta, Situacao
from apps.interesses.consultas import total_reservado
from apps.interesses.models import ParcelaDeInteresse
from apps.interesses.servicos import adicionar_interesse, remover_pendente
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.tempo import agora
from apps.rodadas.condicoes import CondicoesCongeladas, InteressesBloqueados
from apps.rodadas.estoque import alterar_estoque
from apps.rodadas.fechamento import TransicaoRecusada, iniciar_fechamento
from apps.rodadas.models import Ciclo, CondicaoDoProdutoNoCiclo, Etapa, PrazoDoFechamento, Rodada
from apps.rodadas.servicos import abrir_rodada
from tests.apoio.interesses import cenario
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, ParcelaFactory

pytestmark = pytest.mark.django_db

D = Decimal
COM_TRANSACAO = pytest.mark.django_db(transaction=True)


class Ci:
    """O arranjo CI: P1 com limite 11; C pendente (3), A (6), B (5) e D sem estoque (3)."""

    def __init__(self, *, etapa: str = Etapa.INTERESSE, limite: str = "11", a_pendente: int = 0):
        from apps.contas.models import Conta, Papel

        self.rodada, self.p1, self.estoque = cenario(limite=limite, etapa=etapa)
        self.admin = Conta.objects.get(papel=Papel.ADMINISTRADOR)
        self.a, self.b, self.c, self.d = (ContaFactory.create() for _ in range(4))
        self.pc = ParcelaFactory.create(
            comprador=self.c,
            produto=self.p1,
            quantidade_original=D("3"),
            quantidade_reservada=D("0"),
            quantidade_pendente=D("3"),
            situacao="pendente",
        )
        self.pa = ParcelaFactory.create(
            comprador=self.a,
            produto=self.p1,
            quantidade_original=D(6 + a_pendente),
            quantidade_reservada=D("6"),
            quantidade_pendente=D(a_pendente),
        )
        self.pb = ParcelaFactory.create(
            comprador=self.b,
            produto=self.p1,
            quantidade_original=D("5"),
            quantidade_reservada=D("5"),
        )
        self.pd = ParcelaFactory.create(
            comprador=self.d,
            produto=self.p1,
            quantidade_original=D("3"),
            quantidade_reservada=D("0"),
            quantidade_pendente=D("3"),
        )

    def cancelar(self, **kwargs: Any) -> Any:
        from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

        kwargs.setdefault("com_reembolso", False)
        return cancelar_rodada(self.admin, self.rodada, **kwargs)

    def parcela(self, parcela: ParcelaDeInteresse) -> ParcelaDeInteresse:
        parcela.refresh_from_db()
        return parcela


def _estado(parcela: ParcelaDeInteresse) -> tuple[Any, ...]:
    return (
        parcela.situacao,
        parcela.quantidade_reservada,
        parcela.quantidade_pendente,
        parcela.sequencia,
    )


def _foto(ci: Ci) -> tuple[Any, ...]:
    return (
        Rodada.objects.get(pk=ci.rodada.pk).etapa,
        list(
            ParcelaDeInteresse.objects.order_by("pk").values_list(
                "situacao", "quantidade_reservada"
            )
        ),
        EntradaAuditoria.objects.filter(acao="rodada.cancelar").count(),
    )


def test_cancela_a_rodada_em_interesse_e_zera_as_reservas(relogio: RelogioControlado) -> None:
    # A-1
    from apps.pedidos.models import CancelamentoDaRodada

    relogio.congelar(T0)
    ci = Ci()
    cancelamento = ci.cancelar(com_reembolso=False)
    assert Rodada.objects.get(pk=ci.rodada.pk).etapa == "cancelada"
    registro = CancelamentoDaRodada.objects.get()
    assert registro == cancelamento
    assert (
        registro.autor,
        registro.cancelada_em,
        registro.com_reembolso,
        registro.mensagem,
        registro.etapa_anterior,
    ) == (ci.admin, T0, False, "", "interesse")
    for parcela in (ci.pa, ci.pb):
        assert _estado(ci.parcela(parcela))[:3] == ("removida", D("0"), D("0"))
    assert total_reservado(ci.p1) == D("0")


def test_os_pendentes_da_fila_ficam(relogio: RelogioControlado) -> None:  # A-2
    ci = Ci()
    antes = {p.pk: p.sequencia for p in (ci.pc, ci.pd)}
    total = ParcelaDeInteresse.objects.count()
    ci.cancelar()
    for parcela in (ci.pc, ci.pd):
        estado = _estado(ci.parcela(parcela))
        assert estado == ("pendente", D("0"), D("3"), antes[parcela.pk])
    assert ParcelaDeInteresse.objects.count() == total


def test_a_parte_pendente_de_uma_parcela_ativa_continua_na_fila(
    relogio: RelogioControlado,
) -> None:  # A-3
    ci = Ci(a_pendente=2)
    sequencia = ci.pa.sequencia
    assert (ci.pa.quantidade_original, ci.pa.quantidade_pendente) == (D("8"), D("2"))
    ci.cancelar()
    assert _estado(ci.parcela(ci.pa)) == ("pendente", D("0"), D("2"), sequencia)


def test_com_reembolso_sem_pagamento_tem_o_mesmo_efeito_e_apara_a_mensagem(
    relogio: RelogioControlado,
) -> None:  # A-4
    from apps.financeiro.models import ObrigacaoComComprador, Reembolso

    ci = Ci()
    registro = ci.cancelar(com_reembolso=True, mensagem="  Fornecedor sem estoque  ")
    assert registro.com_reembolso is True
    assert registro.mensagem == "Fornecedor sem estoque"
    assert total_reservado(ci.p1) == D("0")
    assert Reembolso.objects.count() == 0
    assert ObrigacaoComComprador.objects.count() == 0


def test_so_o_administrador_ativo_cancela(relogio: RelogioControlado) -> None:  # A-5
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    ci = Ci()
    fornecedor = ContaFactory.create(fornecedor=True)
    # o banco não admite administrador suspenso (conta_administrador_ativo): a guarda é
    # exercida com a conta inativa em memória
    suspenso = Conta.objects.get(pk=ci.admin.pk)
    suspenso.situacao = Situacao.SUSPENSA
    antes = _foto(ci)
    for autor in (ci.a, fornecedor, suspenso, None):
        with pytest.raises(PermissionDenied):
            cancelar_rodada(autor, ci.rodada, com_reembolso=False)
    assert _foto(ci) == antes


def test_cancelar_de_novo_e_recusado(relogio: RelogioControlado) -> None:  # A-6
    from apps.pedidos.cancelamento_da_rodada import CancelamentoRecusado
    from apps.pedidos.models import CancelamentoDaRodada

    ci = Ci()
    ci.cancelar()
    for indicacao in (False, True):
        with pytest.raises(CancelamentoRecusado) as recusa:
            ci.cancelar(com_reembolso=indicacao)
        assert recusa.value.codigo == "ja_cancelada"
        assert str(recusa.value) == "Esta rodada já foi cancelada."
    assert CancelamentoDaRodada.objects.count() == 1
    assert EntradaAuditoria.objects.filter(acao="rodada.cancelar").count() == 1


@pytest.mark.parametrize("indicacao", [None, "sim", 1])
def test_a_indicacao_de_reembolso_e_obrigatoria(
    relogio: RelogioControlado, indicacao: Any
) -> None:  # A-7
    from apps.pedidos.cancelamento_da_rodada import CancelamentoRecusado

    ci = Ci()
    antes = _foto(ci)
    with pytest.raises(CancelamentoRecusado) as recusa:
        ci.cancelar(com_reembolso=indicacao)
    assert recusa.value.codigo == "indicacao_obrigatoria"
    assert str(recusa.value) == "Informe se existe reembolso devido."
    assert _foto(ci) == antes


def test_mensagem_longa_e_recusada_e_a_de_mil_caracteres_passa(
    relogio: RelogioControlado,
) -> None:  # A-8
    from apps.pedidos.cancelamento_da_rodada import CancelamentoRecusado

    ci = Ci()
    antes = _foto(ci)
    with pytest.raises(CancelamentoRecusado) as recusa:
        ci.cancelar(mensagem="x" * 1001)
    assert recusa.value.codigo == "mensagem_longa"
    assert str(recusa.value) == "A mensagem passa de 1000 caracteres."
    assert _foto(ci) == antes
    assert ci.cancelar(mensagem="x" * 1000).mensagem == "x" * 1000


def test_a_assinatura_nao_aceita_lista_de_compradores_nem_motivo(
    relogio: RelogioControlado,
) -> None:  # A-9
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    parametros = list(inspect.signature(cancelar_rodada).parameters)
    assert parametros == ["autor", "rodada", "com_reembolso", "mensagem"]
    ci = Ci()
    antes = _foto(ci)
    with pytest.raises(TypeError):
        cancelar_rodada(ci.admin, ci.rodada, com_reembolso=False, compradores=[ci.a])  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        cancelar_rodada(ci.admin, ci.rodada, com_reembolso=False, motivo="x")  # type: ignore[call-arg]
    assert _foto(ci) == antes


def test_dentro_de_transacao_aberta_e_recusado(relogio: RelogioControlado) -> None:  # A-10
    ci = Ci()
    antes = _foto(ci)
    with pytest.raises(RuntimeError), transaction.atomic():
        ci.cancelar()
    assert _foto(ci) == antes


@pytest.mark.parametrize("etapa", [Etapa.FECHAMENTO, Etapa.FECHAMENTO_ENCERRADO])
def test_cancela_em_fechamento_e_em_fechamento_encerrado(
    relogio: RelogioControlado, etapa: str
) -> None:  # A-11
    ci = Ci(etapa=etapa)
    prazos = list(PrazoDoFechamento.objects.values_list("pk", "termina_em"))
    ciclos = list(Ciclo.objects.values_list("pk", "numero", "minimo"))
    registro = ci.cancelar()
    assert registro.etapa_anterior == etapa
    assert Rodada.objects.get(pk=ci.rodada.pk).etapa == "cancelada"
    assert list(PrazoDoFechamento.objects.values_list("pk", "termina_em")) == prazos
    assert list(Ciclo.objects.values_list("pk", "numero", "minimo")) == ciclos


def test_rodada_encerrada_nao_e_cancelada(relogio: RelogioControlado) -> None:  # A-12
    from apps.pedidos.cancelamento_da_rodada import CancelamentoRecusado

    ci = Ci()
    Rodada.objects.filter(pk=ci.rodada.pk).update(etapa=Etapa.DISPONIVEL_PARA_RETIRADA)
    antes = _foto(ci)
    with pytest.raises(CancelamentoRecusado) as recusa:
        ci.cancelar()
    assert recusa.value.codigo == "rodada_encerrada"
    assert str(recusa.value) == "A rodada já foi encerrada e não pode ser cancelada."
    assert _foto(ci) == antes


def test_a_auditoria_traz_o_que_aconteceu_sem_motivo(relogio: RelogioControlado) -> None:  # A-13
    relogio.congelar(T0)
    ci = Ci()
    ci.cancelar()
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.cancelar")
    assert auditoria.autor_id == str(ci.admin.pk)
    dados = auditoria.alteracoes
    assert dados["rodada"] == ci.rodada.pk
    assert dados["etapa_anterior"] == "interesse"
    assert dados["com_reembolso"] is False
    assert dados["com_mensagem"] is False
    assert dados["cancelada_em"] == T0.isoformat()
    por_parcela = {p["parcela"]: p for p in dados["parcelas"]}
    # D (ativa, sem reserva, 3 pendentes) também é alterada: passa a pendente (regra 6)
    assert set(por_parcela) == {ci.pa.pk, ci.pb.pk, ci.pd.pk}
    linha_d = por_parcela[ci.pd.pk]
    assert (linha_d["situacao_anterior"], linha_d["situacao_nova"]) == ("ativa", "pendente")
    assert (linha_d["reservada_anterior"], linha_d["pendente_mantida"]) == ("0.000", "3.000")
    for parcela, reservada in ((ci.pa, "6.000"), (ci.pb, "5.000")):
        linha = por_parcela[parcela.pk]
        assert (linha["situacao_anterior"], linha["situacao_nova"]) == ("ativa", "removida")
        assert linha["reservada_anterior"] == reservada
        assert linha["comprador"] == parcela.comprador_id
    assert "motivo" not in dados
    assert auditoria.motivo in (None, "")
    for lista in ("pedidos_cancelados", "cobrancas", "reembolsos"):
        assert dados[lista] == []


def test_depois_de_cancelada_os_interesses_e_o_fechamento_ficam_recusados(
    relogio: RelogioControlado,
) -> None:  # A-14
    ci = Ci()
    ci.cancelar()
    antes = _foto(ci)
    with pytest.raises(InteressesBloqueados):
        adicionar_interesse(ci.a, ci.p1, "1")
    with pytest.raises(TransicaoRecusada):
        iniciar_fechamento(ci.admin, ci.rodada)
    with pytest.raises(CondicoesCongeladas):
        alterar_estoque(ci.admin, ci.estoque, "20")
    assert _foto(ci) == antes


def test_remover_pendente_continua_aceito(relogio: RelogioControlado) -> None:  # A-15
    ci = Ci()
    ci.cancelar()
    remover_pendente(ci.c, ci.p1, "1")
    assert ci.parcela(ci.pc).quantidade_pendente == D("2")


def test_nova_rodada_atende_a_fila_pela_regra_da_e05(relogio: RelogioControlado) -> None:  # A-16
    from apps.rodadas.estoque import incluir_produto_na_rodada

    ci = Ci()
    ci.cancelar()
    nova = abrir_rodada(ci.admin, ci.rodada.fornecedor)
    assert nova.etapa == "interesse"
    incluir_produto_na_rodada(ci.admin, nova, ci.p1, "11")
    assert _estado(ci.parcela(ci.pc))[:3] == ("ativa", D("3"), D("0"))
    assert _estado(ci.parcela(ci.pd))[:3] == ("ativa", D("3"), D("0"))
    assert Rodada.objects.get(pk=ci.rodada.pk).etapa == "cancelada"


def test_ciclos_condicoes_e_prazos_ficam_como_estavam(relogio: RelogioControlado) -> None:  # A-17
    ci = Ci(etapa=Etapa.FECHAMENTO)
    antes = (
        list(Ciclo.objects.values_list("pk", "numero", "minimo", "iniciado_em")),
        list(CondicaoDoProdutoNoCiclo.objects.values_list("pk")),
        list(PrazoDoFechamento.objects.values_list("pk", "termina_em")),
    )
    ci.cancelar()
    depois = (
        list(Ciclo.objects.values_list("pk", "numero", "minimo", "iniciado_em")),
        list(CondicaoDoProdutoNoCiclo.objects.values_list("pk")),
        list(PrazoDoFechamento.objects.values_list("pk", "termina_em")),
    )
    assert depois == antes


# --- concorrência (A-18 a A-20) -------------------------------------------------------------------


@pytest.mark.concorrencia
@COM_TRANSACAO
def test_dois_cancelamentos_em_paralelo_gravam_um(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-18
    from apps.pedidos import cancelamento_da_rodada as modulo
    from apps.pedidos.cancelamento_da_rodada import CancelamentoRecusado
    from apps.pedidos.models import CancelamentoDaRodada
    from tests.apoio.corrida import Corrida

    ci = Ci()
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "_gravar_o_cancelamento")
    ra, rb = corrida.rodar(
        lambda: ci.cancelar(), lambda: ci.cancelar(), a_atomica=False, b_atomica=False
    )
    assert ra.excecao is None, ra.excecao
    assert isinstance(rb.excecao, CancelamentoRecusado), rb.excecao
    assert rb.excecao.codigo == "ja_cancelada"
    assert corrida.b_esperou
    assert CancelamentoDaRodada.objects.count() == 1
    assert EntradaAuditoria.objects.filter(acao="rodada.cancelar").count() == 1


@pytest.mark.concorrencia
@COM_TRANSACAO
def test_cancelamento_espera_o_interesse_que_ja_travou(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-19 (i)
    from apps.interesses import servicos
    from tests.apoio.corrida import Corrida

    ci = Ci(limite="20")
    corrida = Corrida()
    corrida.depois_de(monkeypatch, servicos, "_acrescentar")
    ra, rb = corrida.rodar(
        lambda: adicionar_interesse(ci.a, ci.p1, "2"), lambda: ci.cancelar(), b_atomica=False
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    assert total_reservado(ci.p1) == D("0")
    assert Rodada.objects.get(pk=ci.rodada.pk).etapa == "cancelada"
    assert _estado(ci.parcela(ci.pa))[:3] == ("removida", D("0"), D("0"))


@pytest.mark.concorrencia
@COM_TRANSACAO
def test_interesse_espera_o_cancelamento_que_ja_travou(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-19 (ii)
    from apps.pedidos import cancelamento_da_rodada as modulo
    from tests.apoio.corrida import Corrida

    ci = Ci(limite="20")
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "_gravar_o_cancelamento")
    ra, rb = corrida.rodar(
        lambda: ci.cancelar(), lambda: adicionar_interesse(ci.a, ci.p1, "2"), a_atomica=False
    )
    assert ra.excecao is None, ra.excecao
    assert isinstance(rb.excecao, InteressesBloqueados), rb.excecao
    assert corrida.b_esperou
    assert total_reservado(ci.p1) == D("0")


def _fechamento_vencido(relogio: RelogioControlado) -> Ci:
    from datetime import timedelta

    ci = Ci(etapa=Etapa.FECHAMENTO)
    relogio.congelar(agora() + timedelta(hours=25))
    return ci


@pytest.mark.concorrencia
@COM_TRANSACAO
def test_cancelamento_depois_do_encerramento_que_ja_travou(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-20 (encerramento primeiro)
    from apps.pedidos.models import CancelamentoDaRodada
    from apps.rodadas import fechamento
    from tests.apoio.corrida import Corrida

    ci = _fechamento_vencido(relogio)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, fechamento, "avisar_excedentes_removidos")
    ra, rb = corrida.rodar(
        lambda: fechamento.encerrar_fechamento(ci.rodada), lambda: ci.cancelar(), b_atomica=False
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    assert Rodada.objects.get(pk=ci.rodada.pk).etapa == "cancelada"
    assert CancelamentoDaRodada.objects.get().etapa_anterior == "fechamento_encerrado"


@pytest.mark.concorrencia
@COM_TRANSACAO
def test_encerramento_nao_faz_nada_depois_do_cancelamento_que_ja_travou(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-20 (cancelamento primeiro)
    from apps.pedidos import cancelamento_da_rodada as modulo
    from apps.rodadas import fechamento
    from tests.apoio.corrida import Corrida

    ci = _fechamento_vencido(relogio)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "_gravar_o_cancelamento")
    ra, rb = corrida.rodar(
        lambda: ci.cancelar(), lambda: fechamento.encerrar_fechamento(ci.rodada), a_atomica=False
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert rb.valor is None
    assert corrida.b_esperou
    assert Rodada.objects.get(pk=ci.rodada.pk).etapa == "cancelada"
