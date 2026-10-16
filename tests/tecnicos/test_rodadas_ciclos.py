"""E03-07: condições registradas por ciclo (acceptance A-1 a A-8)."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.transaction import TransactionManagementError

from apps.catalogo.servicos import alterar_incremento, alterar_multiplo
from apps.contas.models import Conta
from apps.fornecedores.servicos import alterar_minimo
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.so_insercao import RegistroImutavel
from apps.rodadas.ciclos import ciclo_vigente, registrar_condicoes_do_ciclo
from apps.rodadas.condicoes import CondicoesCongeladas
from apps.rodadas.estoque import alterar_estoque, incluir_produto_na_rodada
from apps.rodadas.models import Ciclo, CondicaoDoProdutoNoCiclo, Etapa, Rodada
from tests.apoio.ciclos import simular_inicio_do_fechamento, simular_volta_para_interesse
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = pytest.mark.django_db

D = Decimal


def _cenario() -> dict[str, Any]:
    """Mínimo 150; P (0,5; múltiplo 3; estoque 10); Q (sem múltiplo, sem limite); R fora."""
    admin = ContaFactory.create(administrador=True)
    fornecedor = FornecedorFactory.create(minimo=D("150.00"))
    rodada = RodadaFactory.create(fornecedor=fornecedor)
    p = ProdutoFactory.create(fornecedor=fornecedor, incremento=D("0.500"), multiplo=D("3.000"))
    q = ProdutoFactory.create(fornecedor=fornecedor, incremento=D("1.000"), multiplo=None)
    r = ProdutoFactory.create(fornecedor=fornecedor, incremento=D("0.250"))
    estoque_p = EstoqueDaRodadaFactory.create(rodada=rodada, produto=p, limite=D("10"))
    EstoqueDaRodadaFactory.create(rodada=rodada, produto=q, limite=None)
    return {
        "admin": admin,
        "fornecedor": fornecedor,
        "rodada": rodada,
        "p": p,
        "q": q,
        "r": r,
        "estoque_p": estoque_p,
    }


def _condicoes(ciclo: Ciclo) -> dict[int, tuple[Any, Any, Any]]:
    return {
        c.produto_id: (c.incremento, c.multiplo, c.limite_estoque)
        for c in CondicaoDoProdutoNoCiclo.objects.filter(ciclo=ciclo)
    }


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_inicio_do_fechamento_registra_as_condicoes_vigentes() -> None:  # A-1
    c = _cenario()
    ciclo = simular_inicio_do_fechamento(c["rodada"])
    assert ciclo.numero == 1
    assert ciclo.rodada_id == c["rodada"].pk
    assert ciclo.minimo == D("150.00")
    assert str(ciclo.minimo) == "150.00"
    assert _condicoes(ciclo) == {
        c["p"].pk: (D("0.500"), D("3.000"), D("10.000")),
        c["q"].pk: (D("1.000"), None, None),
    }
    entrada = EntradaAuditoria.objects.get(acao="ciclo.registrar_condicoes")
    assert entrada.alteracoes == {"rodada": c["rodada"].pk, "ciclo": ciclo.pk, "numero": 1}
    assert entrada.autor_tipo == "sistema"
    c["rodada"].refresh_from_db()
    assert c["rodada"].etapa == Etapa.FECHAMENTO


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_cenario_73_ciclos_anteriores_nao_mudam() -> None:  # A-2, cenário 73
    c = _cenario()
    admin: Conta = c["admin"]
    ciclo1 = simular_inicio_do_fechamento(c["rodada"])
    simular_volta_para_interesse(c["rodada"])
    alterar_minimo(admin, c["fornecedor"], "200,00")
    alterar_multiplo(admin, c["p"], "6")
    alterar_estoque(admin, c["estoque_p"], "20")
    incluir_produto_na_rodada(admin, c["rodada"], c["r"], "5")
    ciclo2 = simular_inicio_do_fechamento(c["rodada"])
    ciclo1.refresh_from_db()
    assert ciclo1.minimo == D("150.00")
    assert _condicoes(ciclo1) == {
        c["p"].pk: (D("0.500"), D("3.000"), D("10.000")),
        c["q"].pk: (D("1.000"), None, None),
    }
    assert ciclo2.numero == 2
    assert ciclo2.minimo == D("200.00")
    assert _condicoes(ciclo2) == {
        c["p"].pk: (D("0.500"), D("6.000"), D("20.000")),
        c["q"].pk: (D("1.000"), None, None),
        c["r"].pk: (D("0.250"), None, D("5.000")),
    }
    assert [x.numero for x in Ciclo.objects.filter(rodada=c["rodada"]).order_by("numero")] == [1, 2]


@pytest.mark.acceptance
@pytest.mark.tecnico
def test_condicoes_voltam_a_ser_editaveis_na_volta_para_interesse() -> None:  # A-3, cenário 73
    c = _cenario()
    admin: Conta = c["admin"]
    simular_inicio_do_fechamento(c["rodada"])
    with pytest.raises(CondicoesCongeladas):
        alterar_minimo(admin, c["fornecedor"], "200,00")
    simular_volta_para_interesse(c["rodada"])
    alterar_minimo(admin, c["fornecedor"], "200,00")
    alterar_multiplo(admin, c["p"], "6")
    alterar_incremento(admin, c["p"], "0.25")
    alterar_estoque(admin, c["estoque_p"], "20")
    c["fornecedor"].refresh_from_db()
    c["p"].refresh_from_db()
    c["estoque_p"].refresh_from_db()
    assert c["fornecedor"].minimo == D("200.00")
    assert (c["p"].multiplo, c["p"].incremento) == (D("6.000"), D("0.250"))
    assert c["estoque_p"].limite == D("20.000")


def test_ciclo_e_condicoes_so_aceitam_insercao_no_orm() -> None:  # A-4
    c = _cenario()
    ciclo = simular_inicio_do_fechamento(c["rodada"])
    condicao = CondicaoDoProdutoNoCiclo.objects.filter(ciclo=ciclo).first()
    assert condicao is not None
    ciclo.minimo = D("1.00")
    condicao.incremento = D("9")
    with pytest.raises(RegistroImutavel):
        ciclo.save()
    with pytest.raises(RegistroImutavel):
        condicao.save()
    with pytest.raises(RegistroImutavel):
        ciclo.delete()
    with pytest.raises(RegistroImutavel):
        condicao.delete()
    with pytest.raises(RegistroImutavel):
        Ciclo.objects.filter(pk=ciclo.pk).update(minimo=D("1.00"))
    with pytest.raises(RegistroImutavel):
        CondicaoDoProdutoNoCiclo.objects.filter(pk=condicao.pk).delete()


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE rodadas_ciclo SET minimo = 1 WHERE id = %s",
        "DELETE FROM rodadas_ciclo WHERE id = %s",
    ],
)
def test_banco_recusa_alterar_ou_apagar_ciclo(sql: str) -> None:  # A-4
    c = _cenario()
    ciclo = simular_inicio_do_fechamento(c["rodada"])
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, [ciclo.pk])
    ciclo.refresh_from_db()
    assert ciclo.minimo == D("150.00")


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE rodadas_condicaodoprodutonociclo SET incremento = 9 WHERE id = %s",
        "DELETE FROM rodadas_condicaodoprodutonociclo WHERE id = %s",
    ],
)
def test_banco_recusa_alterar_ou_apagar_condicao(sql: str) -> None:  # A-4
    c = _cenario()
    ciclo = simular_inicio_do_fechamento(c["rodada"])
    condicao = CondicaoDoProdutoNoCiclo.objects.filter(ciclo=ciclo).first()
    assert condicao is not None
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, [condicao.pk])
    assert CondicaoDoProdutoNoCiclo.objects.filter(pk=condicao.pk).exists()


def test_registro_fora_de_interesse_e_recusado() -> None:  # A-5
    rodada = RodadaFactory.create(etapa=Etapa.FECHAMENTO)
    with pytest.raises(CondicoesCongeladas), transaction.atomic():
        registrar_condicoes_do_ciclo(rodada)
    assert Ciclo.objects.count() == 0
    assert EntradaAuditoria.objects.count() == 0


def test_segunda_chamada_no_mesmo_ciclo_e_recusada() -> None:
    c = _cenario()
    simular_inicio_do_fechamento(c["rodada"])
    with pytest.raises(CondicoesCongeladas), transaction.atomic():
        registrar_condicoes_do_ciclo(c["rodada"])
    assert Ciclo.objects.count() == 1


def test_registro_de_rodada_antiga_e_recusado() -> None:
    antiga = RodadaFactory.create(etapa=Etapa.DISPONIVEL_PARA_RETIRADA)
    RodadaFactory.create(fornecedor=antiga.fornecedor)
    with pytest.raises(CondicoesCongeladas), transaction.atomic():
        registrar_condicoes_do_ciclo(antiga)
    assert Ciclo.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_registro_fora_de_transacao_falha() -> None:  # A-6
    rodada = RodadaFactory.create()
    assert not connection.in_atomic_block
    with pytest.raises(TransactionManagementError):
        registrar_condicoes_do_ciclo(rodada)
    assert Ciclo.objects.count() == 0


def test_ciclo_vigente() -> None:  # A-7
    c = _cenario()
    assert ciclo_vigente(c["rodada"]) is None
    simular_inicio_do_fechamento(c["rodada"])
    simular_volta_para_interesse(c["rodada"])
    segundo = simular_inicio_do_fechamento(c["rodada"])
    vigente = ciclo_vigente(c["rodada"])
    assert vigente is not None
    assert vigente.pk == segundo.pk
    assert vigente.numero == 2
    outra = RodadaFactory.create()
    assert ciclo_vigente(outra) is None


def test_banco_recusa_segundo_ciclo_com_o_mesmo_numero() -> None:  # A-8
    c = _cenario()
    simular_inicio_do_fechamento(c["rodada"])
    sql = (
        "INSERT INTO rodadas_ciclo (rodada_id, numero, iniciado_em, minimo) "
        "VALUES (%s, 1, now(), 10)"
    )
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, [c["rodada"].pk])
    assert Ciclo.objects.count() == 1


def test_banco_recusa_numero_zero_e_condicao_repetida() -> None:
    c = _cenario()
    ciclo = simular_inicio_do_fechamento(c["rodada"])
    sql = (
        "INSERT INTO rodadas_ciclo (rodada_id, numero, iniciado_em, minimo) "
        "VALUES (%s, 0, now(), 10)"
    )
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, [c["rodada"].pk])
    with pytest.raises(IntegrityError), transaction.atomic():
        CondicaoDoProdutoNoCiclo.objects.create(ciclo=ciclo, produto=c["p"], incremento=D("1"))


def test_rodada_sem_produtos_registra_ciclo_sem_condicoes() -> None:
    rodada = RodadaFactory.create()
    ciclo = simular_inicio_do_fechamento(rodada)
    assert ciclo.numero == 1
    assert CondicaoDoProdutoNoCiclo.objects.filter(ciclo=ciclo).count() == 0
    assert Rodada.objects.get(pk=rodada.pk).etapa == Etapa.FECHAMENTO


def test_ciclos_de_outra_rodada_do_mesmo_fornecedor_tem_numeracao_propria() -> None:
    c = _cenario()
    simular_inicio_do_fechamento(c["rodada"])
    Rodada.objects.filter(pk=c["rodada"].pk).update(etapa=Etapa.DISPONIVEL_PARA_RETIRADA)
    nova = RodadaFactory.create(fornecedor=c["fornecedor"])
    assert simular_inicio_do_fechamento(nova).numero == 1
