"""E03-01: cadastro de fornecedores (acceptance A-1 a A-7, A-11 e A-13)."""

from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import Client

from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import criar_fornecedor, editar_fornecedor
from apps.nucleo.auditoria import EntradaAuditoria
from apps.nucleo.valores import ValorInvalido
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, FornecedorFactory

pytestmark = pytest.mark.django_db

NOVO = "/administracao/fornecedores/novo/"


def _dados(**campos: Any) -> dict[str, Any]:
    base = {
        "nome": " Sítio Boa Terra ",
        "email_pedido": " Pedidos@BoaTerra.com ",
        "minimo": "150,00",
        "prazo_entrega_dias": "7",
        "informacoes_frete": "Entrega às terças",
    }
    return {**base, **campos}


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def test_cadastro_grava_dados_normalizados_e_redireciona_para_o_detalhe(
    admin_client: Client,
) -> None:  # A-1
    resposta = admin_client.post(NOVO, _dados())
    fornecedor = Fornecedor.objects.get()
    assert resposta.status_code == 302
    assert resposta["Location"] == f"/administracao/fornecedores/{fornecedor.pk}/"
    assert fornecedor.nome == "Sítio Boa Terra"
    assert fornecedor.email_pedido == "pedidos@boaterra.com"
    assert fornecedor.minimo == Decimal("150.00")
    assert str(fornecedor.minimo) == "150.00"
    assert fornecedor.prazo_entrega_dias == 7
    assert fornecedor.informacoes_frete == "Entrega às terças"
    assert fornecedor.criado_em is not None


def test_minimo_com_ponto_tem_o_mesmo_valor(admin_client: Client) -> None:  # A-2
    admin_client.post(NOVO, _dados(minimo="150.00"))
    assert Fornecedor.objects.get().minimo == Decimal("150.00")


@pytest.mark.parametrize("minimo", ["0", "-1", "0,001", "abc", "1.000,00", "0,00", ""])
def test_minimo_invalido_e_recusado(admin_client: Client, minimo: str) -> None:  # A-3
    resposta = admin_client.post(NOVO, _dados(minimo=minimo))
    assert resposta.status_code == 200
    assert "minimo" in resposta.context["form"].errors
    assert Fornecedor.objects.count() == 0


def test_minimo_de_um_centavo_e_aceito(admin_client: Client) -> None:
    admin_client.post(NOVO, _dados(minimo="0,01"))
    assert Fornecedor.objects.get().minimo == Decimal("0.01")


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("nome", ""),
        ("nome", "   "),
        ("nome", "x" * 151),
        ("email_pedido", "nao-e-email"),
        ("email_pedido", ""),
        ("prazo_entrega_dias", "0"),
        ("prazo_entrega_dias", "366"),
        ("prazo_entrega_dias", "2,5"),
        ("prazo_entrega_dias", ""),
        ("informacoes_frete", "x" * 1001),
    ],
)
def test_campo_invalido_e_recusado(admin_client: Client, campo: str, valor: str) -> None:  # A-4
    resposta = admin_client.post(NOVO, _dados(**{campo: valor}))
    assert resposta.status_code == 200
    assert campo in resposta.context["form"].errors
    assert Fornecedor.objects.count() == 0


@pytest.mark.parametrize("prazo", ["1", "365"])
def test_prazos_limite_e_frete_vazio_sao_aceitos(admin_client: Client, prazo: str) -> None:  # A-5
    resposta = admin_client.post(NOVO, _dados(prazo_entrega_dias=prazo, informacoes_frete=""))
    assert resposta.status_code == 302
    fornecedor = Fornecedor.objects.get()
    assert fornecedor.prazo_entrega_dias == int(prazo)
    assert fornecedor.informacoes_frete == ""


def test_servico_recusa_float_no_minimo() -> None:  # A-6
    admin = ContaFactory.create(administrador=True)
    with pytest.raises((ValidationError, ValorInvalido)):
        criar_fornecedor(
            admin,
            nome="X",
            email_pedido="x@x.com",
            minimo=150.0,  # type: ignore[arg-type]
            prazo_entrega_dias=7,
        )
    assert Fornecedor.objects.count() == 0


def test_servico_valida_todos_os_campos_com_mensagem_por_campo() -> None:
    admin = ContaFactory.create(administrador=True)
    with pytest.raises(ValidationError) as erro:
        criar_fornecedor(admin, nome="", email_pedido="lixo", minimo="0", prazo_entrega_dias=0)
    assert set(erro.value.message_dict) == {"nome", "email_pedido", "minimo", "prazo_entrega_dias"}
    assert Fornecedor.objects.count() == 0


def test_servico_aceita_minimo_decimal_e_texto() -> None:
    admin = ContaFactory.create(administrador=True)
    a = criar_fornecedor(
        admin, nome="A", email_pedido="a@x.com", minimo=Decimal("10.5"), prazo_entrega_dias=3
    )
    b = criar_fornecedor(
        admin, nome="B", email_pedido="b@x.com", minimo="10,50", prazo_entrega_dias=3
    )
    assert a.minimo == b.minimo == Decimal("10.50")


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE fornecedores_fornecedor SET minimo = 0 WHERE id = %s",
        "UPDATE fornecedores_fornecedor SET prazo_entrega_dias = 0 WHERE id = %s",
        "UPDATE fornecedores_fornecedor SET prazo_entrega_dias = 366 WHERE id = %s",
    ],
)
def test_banco_recusa_minimo_zero_e_prazo_fora_da_faixa(sql: str) -> None:  # A-7
    fornecedor = FornecedorFactory.create()
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(sql, [fornecedor.pk])
    fornecedor.refresh_from_db()
    assert fornecedor.minimo == Decimal("100.00")
    assert fornecedor.prazo_entrega_dias == 7


def test_auditoria_do_cadastro_nao_tem_o_email(admin_client: Client) -> None:  # A-11
    admin_client.post(NOVO, _dados())
    fornecedor = Fornecedor.objects.get()
    entrada = EntradaAuditoria.objects.get(acao="fornecedor.criar")
    assert entrada.autor_tipo == "usuario"
    assert entrada.alteracoes == {"fornecedor": fornecedor.pk}
    assert "boaterra" not in str(entrada.alteracoes)
    assert entrada.objeto_id == str(fornecedor.pk)


def test_so_o_administrador_cria_e_edita_pelo_servico() -> None:  # A-13
    comprador = ContaFactory.create()
    fornecedor = FornecedorFactory.create(nome="Original")
    with pytest.raises(PermissionDenied):
        criar_fornecedor(
            comprador, nome="X", email_pedido="x@x.com", minimo="10", prazo_entrega_dias=3
        )
    with pytest.raises(PermissionDenied):
        editar_fornecedor(comprador, fornecedor, nome="Invadido")
    for autor in (ContaFactory.create(fornecedor=True), None):
        with pytest.raises(PermissionDenied):
            criar_fornecedor(
                autor,  # type: ignore[arg-type]
                nome="X",
                email_pedido="x@x.com",
                minimo="10",
                prazo_entrega_dias=3,
            )
    assert Fornecedor.objects.count() == 1 + 1  # o original e o da conta de fornecedor
    fornecedor.refresh_from_db()
    assert fornecedor.nome == "Original"
    assert EntradaAuditoria.objects.count() == 0
