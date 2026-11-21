"""Cenário 63 (§16): a recusa de 1,2 kg vale também pela rota `POST /interesses/` (E16-07 A-41).

"Pela API" é a rota HTTP chamada direto, com os campos montados pelo teste (a aplicação não tem
API separada; infraestrutura §2). Produto em kg, R$ 12,00, incremento 0,5.
"""

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from apps.catalogo.models import Produto, Unidade
from apps.contas.models import Conta
from apps.interesses.consultas import total_reservado
from apps.interesses.models import ParcelaDeInteresse
from tests.apoio.interesses import cenario, reservada
from tests.fabricas import ContaFactory

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal
MENSAGEM = "A quantidade deve ser maior que zero e múltipla do incremento do produto."


def _produto_em_kg() -> Produto:
    _, produto, _ = cenario("20", unidade=Unidade.KG, incremento=D("0.5"), preco=D("12.00"))
    return produto


def _enviar_1_2(comprador: Conta, produto: Produto) -> Any:
    cliente = Client()
    cliente.force_login(comprador)
    return cliente.post(
        "/interesses/", {"produto": produto.pk, "quantidade": "1.2", "origem": "carrinho"}
    )


def test_cenario_63_rota_recusa_1_2_kg_sem_gravar() -> None:
    produto = _produto_em_kg()
    sem_interesse = ContaFactory.create()
    antes = total_reservado(produto)
    resposta = _enviar_1_2(sem_interesse, produto)
    assert resposta.status_code == 200
    assert MENSAGEM in resposta.content.decode()
    assert "Interesse atualizado" not in resposta.content.decode()
    assert not ParcelaDeInteresse.objects.filter(comprador=sem_interesse, produto=produto).exists()
    assert total_reservado(produto) == antes == D("0.000")
    # segundo caso: o comprador já tem 1,5 kg reservado; o mesmo POST não altera a parcela
    com_1_5 = ContaFactory.create()
    parcela = reservada(com_1_5, produto, "1.5")
    original = ParcelaDeInteresse.objects.filter(pk=parcela.pk).values().get()
    resposta = _enviar_1_2(com_1_5, produto)
    assert resposta.status_code == 200
    assert "Interesse atualizado" not in resposta.content.decode()
    assert total_reservado(produto) == D("1.500")
    assert ParcelaDeInteresse.objects.filter(pk=parcela.pk).values().get() == original
    assert ParcelaDeInteresse.objects.filter(comprador=com_1_5, produto=produto).count() == 1
