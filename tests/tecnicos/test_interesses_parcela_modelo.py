"""E03-04: modelo da parcela de interesse (acceptance A-1 a A-5 e A-10)."""

from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction

from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from tests.fabricas import ContaFactory, ParcelaFactory, ProdutoFactory

pytestmark = pytest.mark.django_db

D = Decimal


def _gravar(parcela: ParcelaDeInteresse, campos: dict[str, Any]) -> None:
    with transaction.atomic():
        for nome, valor in campos.items():
            setattr(parcela, nome, valor)
        parcela.save(update_fields=list(campos))


def test_sequencias_distintas_e_crescentes_e_quantidades_exatas() -> None:  # A-1
    comprador = ContaFactory.create()
    produto = ProdutoFactory.create()
    parcelas = [
        ParcelaFactory.create(
            comprador=comprador,
            produto=produto,
            quantidade_original=D("2.5"),
            quantidade_reservada=D("2.5"),
        )
        for _ in range(3)
    ]
    sequencias = [p.sequencia for p in parcelas]
    assert len(set(sequencias)) == 3
    assert sequencias == sorted(sequencias)
    gravada = ParcelaDeInteresse.objects.get(pk=parcelas[0].pk)
    assert str(gravada.quantidade_original) == "2.500"
    assert str(gravada.quantidade_pendente) == "0.000"
    assert isinstance(gravada.quantidade_reservada, Decimal)


@pytest.mark.parametrize(
    "coluna", ["sequencia", "comprador_id", "produto_id", "quantidade_original"]
)
def test_banco_recusa_troca_das_colunas_imutaveis(coluna: str) -> None:  # A-2
    parcela = ParcelaFactory.create()
    outro = ParcelaFactory.create()
    novos: dict[str, Any] = {
        "sequencia": parcela.sequencia + 1000,
        "comprador_id": outro.comprador_id,
        "produto_id": outro.produto_id,
        "quantidade_original": D("9.000"),
    }
    sql = f"UPDATE interesses_parcela SET {coluna} = %s WHERE id = %s"  # noqa: S608
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, [novos[coluna], parcela.pk])
    parcela.refresh_from_db()
    assert parcela.sequencia != novos["sequencia"]
    assert parcela.quantidade_original == D("1.000")


def test_banco_recusa_exclusao() -> None:  # A-3
    parcela = ParcelaFactory.create()
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM interesses_parcela WHERE id = %s", [parcela.pk])
    assert ParcelaDeInteresse.objects.filter(pk=parcela.pk).exists()


# Cada caso é uma inserção inválida e, quando faz sentido, a atualização equivalente.
INSERCOES_INVALIDAS: dict[str, dict[str, Any]] = {
    "original_zero": {"quantidade_original": D("0"), "quantidade_reservada": D("0")},
    "reservada_negativa": {"quantidade_reservada": D("-1")},
    "pendente_negativa": {"quantidade_pendente": D("-1")},
    "soma_acima_do_original": {
        "quantidade_original": D("8"),
        "quantidade_reservada": D("5"),
        "quantidade_pendente": D("4"),
    },
    "removida_com_reserva": {"situacao": SituacaoParcela.REMOVIDA},
    "removida_com_pendencia": {
        "situacao": SituacaoParcela.REMOVIDA,
        "quantidade_reservada": D("0"),
        "quantidade_pendente": D("1"),
    },
    "pendente_com_reserva": {"situacao": SituacaoParcela.PENDENTE},
    "situacao_desconhecida": {"situacao": "sumida"},
}

ATUALIZACOES_INVALIDAS: dict[str, dict[str, Any]] = {
    nome: campos
    for nome, campos in INSERCOES_INVALIDAS.items()
    if "quantidade_original" not in campos
}


@pytest.mark.parametrize("campos", INSERCOES_INVALIDAS.values(), ids=INSERCOES_INVALIDAS.keys())
def test_banco_recusa_insercao_invalida(campos: dict[str, Any]) -> None:  # A-4
    with pytest.raises(IntegrityError), transaction.atomic():
        ParcelaFactory.create(**campos)
    assert ParcelaDeInteresse.objects.count() == 0


@pytest.mark.parametrize(
    "campos", ATUALIZACOES_INVALIDAS.values(), ids=ATUALIZACOES_INVALIDAS.keys()
)
def test_banco_recusa_atualizacao_invalida(campos: dict[str, Any]) -> None:  # A-4
    parcela = ParcelaFactory.create(
        quantidade_original=D("8"), quantidade_reservada=D("2"), quantidade_pendente=D("0")
    )
    with pytest.raises(IntegrityError):
        _gravar(parcela, campos)
    parcela.refresh_from_db()
    assert parcela.quantidade_reservada == D("2.000")
    assert parcela.situacao == SituacaoParcela.ATIVA


def test_banco_recusa_soma_acima_do_original_na_atualizacao() -> None:  # A-4
    parcela = ParcelaFactory.create(
        quantidade_original=D("8"), quantidade_reservada=D("2"), quantidade_pendente=D("0")
    )
    with pytest.raises(IntegrityError):
        _gravar(parcela, {"quantidade_reservada": D("5"), "quantidade_pendente": D("4")})
    parcela.refresh_from_db()
    assert parcela.quantidade_reservada == D("2.000")


def test_atualizacoes_validas_do_cenario_75() -> None:  # A-5
    parcela = ParcelaFactory.create(
        quantidade_original=D("8"), quantidade_reservada=D("8"), quantidade_pendente=D("0")
    )
    for situacao, reservada, pendente in (
        (SituacaoParcela.ATIVA, "4", "4"),
        (SituacaoParcela.PENDENTE, "0", "8"),
        (SituacaoParcela.REMOVIDA, "0", "0"),
    ):
        parcela.situacao = situacao
        parcela.quantidade_reservada = D(reservada)
        parcela.quantidade_pendente = D(pendente)
        parcela.save(update_fields=["situacao", "quantidade_reservada", "quantidade_pendente"])
        parcela.refresh_from_db()
        assert (parcela.situacao, parcela.quantidade_reservada, parcela.quantidade_pendente) == (
            situacao,
            D(reservada),
            D(pendente),
        )


def test_save_comum_do_orm_passa_pelo_gatilho() -> None:
    parcela = ParcelaFactory.create()
    sequencia = parcela.sequencia
    parcela.save()  # reenvia as colunas imutáveis com o mesmo valor
    parcela.refresh_from_db()
    assert parcela.sequencia == sequencia > 0


def test_sequencia_informada_na_criacao_e_ignorada() -> None:  # A-10
    primeira = ParcelaFactory.create()
    informada = ParcelaFactory.create(sequencia=1)
    assert informada.sequencia != 1
    informada.refresh_from_db()
    assert informada.sequencia != 1
    assert informada.sequencia > primeira.sequencia


def test_insercao_por_sql_tambem_ignora_a_sequencia_informada() -> None:  # A-10
    base = ParcelaFactory.create()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO interesses_parcela (sequencia, comprador_id, produto_id, "
            "quantidade_original, quantidade_reservada, quantidade_pendente, situacao, criada_em) "
            "VALUES (1, %s, %s, 1, 1, 0, 'ativa', now()) RETURNING sequencia",
            [base.comprador_id, base.produto_id],
        )
        (sequencia,) = cursor.fetchone()
    assert sequencia != 1
    assert sequencia > base.sequencia
