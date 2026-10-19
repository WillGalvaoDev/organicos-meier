"""E06-01: início do fechamento e prazo de 24 horas (acceptance A-1 a A-10)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction

from apps.catalogo.servicos import alterar_incremento, alterar_multiplo, editar_produto
from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import alterar_minimo
from apps.interesses.fila import alocar_pendentes
from apps.interesses.servicos import adicionar_interesse
from apps.notificacoes.processamento import processar_envios
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.estoque import alterar_estoque
from apps.rodadas.fechamento import (
    HORAS_DO_FECHAMENTO,
    TransicaoRecusada,
    iniciar_fechamento,
    prazo_do_fechamento,
)
from apps.rodadas.models import Ciclo, Etapa, OrigemDoPrazo, PrazoDoFechamento, Rodada
from tests.apoio.interesses import cenario, pendente, reservada
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
ACAO = "rodada.iniciar_fechamento"
T0 = datetime(2026, 11, 2, 13, 30, tzinfo=UTC)


def admin() -> Conta:
    return Conta.objects.get(papel="administrador")


def nada_gravado() -> None:
    assert Ciclo.objects.count() == 0
    assert PrazoDoFechamento.objects.count() == 0
    assert EntradaAuditoria.objects.filter(acao=ACAO).count() == 0
    assert EntradaAuditoria.objects.filter(acao="ciclo.registrar_condicoes").count() == 0


def etapa(rodada: Rodada) -> str:
    return str(Rodada.objects.get(pk=rodada.pk).etapa)


@pytest.mark.acceptance
def test_inicio_registra_ciclo_prazo_de_24_horas_e_auditoria(relogio: RelogioControlado) -> None:
    # A-1, cenário 5
    relogio.congelar(T0)
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    ciclo = iniciar_fechamento(admin(), rodada)
    assert etapa(rodada) == Etapa.FECHAMENTO
    assert ciclo.numero == 1
    assert ciclo.iniciado_em == T0
    (prazo,) = PrazoDoFechamento.objects.filter(ciclo=ciclo)
    assert prazo.origem == OrigemDoPrazo.INICIO
    assert prazo.termina_em == datetime(2026, 11, 3, 13, 30, tzinfo=UTC)
    assert prazo.termina_em == ciclo.iniciado_em + timedelta(hours=HORAS_DO_FECHAMENTO)
    assert prazo.autor_id == admin().pk
    assert prazo_do_fechamento(rodada) == prazo.termina_em
    (entrada,) = EntradaAuditoria.objects.filter(acao=ACAO)
    assert entrada.objeto_id == str(rodada.pk)
    assert entrada.alteracoes == {
        "rodada": rodada.pk,
        "ciclo": ciclo.pk,
        "termina_em": prazo.termina_em.isoformat(),
        "valor_elegivel": "100.00",
        "minimo": "100.00",
    }


@pytest.mark.acceptance
def test_minimo_nao_conta_pendentes(relogio: RelogioControlado) -> None:  # A-2, cenário 104
    relogio.congelar(T0)
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 8)
    pendente(ContaFactory.create(), produto, 5)
    with pytest.raises(TransicaoRecusada) as erro:
        iniciar_fechamento(admin(), rodada)
    assert erro.value.codigo == "minimo_nao_atingido"
    assert erro.value.mensagem == "O fechamento só pode começar com o mínimo elegível atingido."
    assert etapa(rodada) == Etapa.INTERESSE
    nada_gravado()


def test_so_conta_a_quantidade_em_caixas_completas() -> None:  # A-3
    rodada, produto, _ = cenario("20", preco=D("10.00"), multiplo=D("12"))
    a, b = ContaFactory.create(), ContaFactory.create()
    reservada(a, produto, 11)
    with pytest.raises(TransicaoRecusada) as erro:
        iniciar_fechamento(admin(), rodada)
    assert erro.value.codigo == "minimo_nao_atingido"
    nada_gravado()
    adicionar_interesse(b, produto, "1")
    iniciar_fechamento(admin(), rodada)
    assert etapa(rodada) == Etapa.FECHAMENTO


@pytest.mark.acceptance
def test_atingir_o_minimo_nao_inicia_nada_sozinho(relogio: RelogioControlado) -> None:  # A-4
    # cenário 4
    relogio.congelar(T0)
    rodada, produto, _ = cenario("30", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 20)
    relogio.avancar(timedelta(days=30))
    processar_envios()
    with transaction.atomic():
        alocar_pendentes(rodada.fornecedor)
    assert etapa(rodada) == Etapa.INTERESSE
    nada_gravado()
    assert prazo_do_fechamento(rodada) is None


@pytest.mark.parametrize("quem", ["comprador", "fornecedor", "anonimo"])
def test_so_o_administrador_inicia(quem: str) -> None:  # A-5
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    autor = {
        "comprador": lambda: ContaFactory.create(),
        "fornecedor": lambda: ContaFactory.create(fornecedor=True),
        "anonimo": lambda: None,
    }[quem]()
    with pytest.raises(PermissionDenied):
        iniciar_fechamento(autor, rodada)
    assert etapa(rodada) == Etapa.INTERESSE
    nada_gravado()


def test_rodada_ja_em_fechamento_nao_inicia_de_novo() -> None:  # A-6 (a)
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    iniciar_fechamento(admin(), rodada)
    with pytest.raises(TransicaoRecusada) as erro:
        iniciar_fechamento(admin(), rodada)
    assert erro.value.codigo == "fora_de_interesse"
    assert erro.value.mensagem == "O fechamento só pode começar com a rodada em interesse."
    assert Ciclo.objects.count() == 1
    assert PrazoDoFechamento.objects.count() == 1


def test_rodada_em_pagamento_nao_inicia() -> None:  # A-6 (b)
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.PAGAMENTO)
    with pytest.raises(TransicaoRecusada) as erro:
        iniciar_fechamento(admin(), rodada)
    assert erro.value.codigo == "fora_de_interesse"
    nada_gravado()


def test_sem_rodada_ativa_nao_inicia() -> None:  # A-6 (c)
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.DISPONIVEL_PARA_RETIRADA)
    with pytest.raises(TransicaoRecusada) as erro:
        iniciar_fechamento(admin(), rodada)
    assert erro.value.codigo == "sem_rodada_ativa"
    assert erro.value.mensagem == "Este fornecedor não tem rodada ativa."
    nada_gravado()


def test_exatamente_no_minimo_e_aceito() -> None:  # A-7
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    iniciar_fechamento(admin(), rodada)
    assert etapa(rodada) == Etapa.FECHAMENTO


def test_minimo_zero_sem_reservas_e_aceito() -> None:  # A-7
    rodada, _, _ = cenario("20", preco=D("10.00"))
    with (
        connection.cursor() as cursor
    ):  # o banco recusa mínimo zero; a restrição sai só neste teste
        cursor.execute(
            "ALTER TABLE fornecedores_fornecedor DROP CONSTRAINT fornecedor_minimo_positivo"
        )
    Fornecedor.objects.filter(pk=rodada.fornecedor_id).update(minimo=D("0.00"))
    iniciar_fechamento(admin(), rodada)
    assert etapa(rodada) == Etapa.FECHAMENTO


def test_prazo_vale_24_horas_corridas_mesmo_de_madrugada(relogio: RelogioControlado) -> None:
    # A-8: 23:30 de 01/11 em São Paulo
    relogio.congelar(datetime(2026, 11, 2, 2, 30, tzinfo=UTC))
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    iniciar_fechamento(admin(), rodada)
    assert prazo_do_fechamento(rodada) == datetime(2026, 11, 3, 2, 30, tzinfo=UTC)


def test_condicoes_congeladas_mas_o_preco_continua_editavel() -> None:  # A-9, cenários 72 e 107
    rodada, produto, estoque = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    iniciar_fechamento(admin(), rodada)
    recusas: list[Any] = [
        lambda: alterar_minimo(admin(), rodada.fornecedor, "50,00"),
        lambda: alterar_estoque(admin(), estoque, "15"),
        lambda: alterar_multiplo(admin(), produto, "2"),
        lambda: alterar_incremento(admin(), produto, "2"),
    ]
    for acao in recusas:
        with pytest.raises(CondicoesCongeladas):
            acao()
    editar_produto(admin(), produto, preco="12.00")
    produto.refresh_from_db()
    assert produto.preco == D("12.00")


def test_prazo_so_aceita_insercao() -> None:  # A-10
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    ciclo = iniciar_fechamento(admin(), rodada)
    prazo = PrazoDoFechamento.objects.get(ciclo=ciclo)
    antes = prazo.termina_em
    prazo.termina_em = antes + timedelta(hours=1)
    with pytest.raises(RegistroImutavel):
        prazo.save()
    with pytest.raises(RegistroImutavel):
        prazo.delete()
    with pytest.raises(RegistroImutavel):
        PrazoDoFechamento.objects.filter(pk=prazo.pk).update(termina_em=antes)
    with pytest.raises(RegistroImutavel):
        PrazoDoFechamento.objects.filter(pk=prazo.pk).delete()
    for sql in (
        "UPDATE rodadas_prazodofechamento SET termina_em = now() WHERE id = %s",
        "DELETE FROM rodadas_prazodofechamento WHERE id = %s",
    ):
        with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql, [prazo.pk])
    assert PrazoDoFechamento.objects.get(pk=prazo.pk).termina_em == antes


def test_uma_so_linha_de_inicio_por_ciclo() -> None:  # A-10
    rodada, produto, _ = cenario("20", preco=D("10.00"))
    reservada(ContaFactory.create(), produto, 10)
    ciclo = iniciar_fechamento(admin(), rodada)
    with pytest.raises(IntegrityError), transaction.atomic():
        PrazoDoFechamento.objects.create(
            ciclo=ciclo, termina_em=ciclo.iniciado_em, origem="inicio", autor=admin()
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        PrazoDoFechamento.objects.create(
            ciclo=ciclo, termina_em=ciclo.iniciado_em, origem="outra", autor=admin()
        )
    PrazoDoFechamento.objects.create(
        ciclo=ciclo, termina_em=ciclo.iniciado_em, origem="prorrogacao", autor=admin()
    )
    assert PrazoDoFechamento.objects.filter(ciclo=ciclo).count() == 2
