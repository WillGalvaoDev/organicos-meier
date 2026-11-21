"""Cenário 85 (§16) pela rota: "as validações de quantidade ocorrem no servidor, inclusive pela API"
(E16-07 regra 2-J). "API" é a rota HTTP `POST /interesses/` chamada direto, com os campos montados
pelo teste (a aplicação não tem API separada; infraestrutura §2). Os cinco casos do cenário, com a
unidade do produto explícita: os aceitos ficam reservados com o valor e os recusados não gravam."""

from decimal import Decimal

import pytest
from django.test import Client

from apps.catalogo.models import Unidade
from apps.interesses.consultas import total_reservado
from apps.interesses.models import ParcelaDeInteresse
from tests.apoio.interesses import cenario
from tests.fabricas import ContaFactory

pytestmark = [pytest.mark.django_db, pytest.mark.acceptance]

D = Decimal
MENSAGEM = "A quantidade deve ser maior que zero e múltipla do incremento do produto."


@pytest.mark.parametrize(
    ("unidade", "incremento", "entrada", "aceita"),
    [
        (Unidade.LITRO, "0.5", "1.5", True),
        (Unidade.LITRO, "0.5", "1.2", False),
        (Unidade.UNIDADE, "1", "2", True),
        (Unidade.UNIDADE, "1", "2.5", False),
        (Unidade.KG, "0.25", "0.75", True),
    ],
)
def test_cenario_85_rota_valida_as_quantidades_no_servidor(
    unidade: str, incremento: str, entrada: str, aceita: bool
) -> None:
    _, produto, _ = cenario(None, unidade=unidade, incremento=D(incremento), preco=D("12.00"))
    assert produto.unidade == unidade
    comprador = ContaFactory.create()
    cliente = Client()
    cliente.force_login(comprador)
    resposta = cliente.post(
        "/interesses/", {"produto": produto.pk, "quantidade": entrada, "origem": "carrinho"}
    )
    parcelas = list(ParcelaDeInteresse.objects.filter(comprador=comprador, produto=produto))
    if aceita:
        assert resposta.status_code == 302
        (parcela,) = parcelas
        assert parcela.quantidade_reservada == D(entrada)
        assert total_reservado(produto) == D(entrada)
    else:
        assert resposta.status_code == 200
        assert MENSAGEM in resposta.content.decode()
        assert "Interesse atualizado" not in resposta.content.decode()
        assert parcelas == []
        assert total_reservado(produto) == D("0.000")
