"""E03-01: telas de fornecedores (acceptance A-8 a A-10 e A-14 a A-16)."""

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from apps.contas.models import Situacao
from apps.fornecedores.models import Fornecedor
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, FornecedorFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client: Client, webauthn: Any) -> Client:
    administrador_logado(client)
    return client


def _editar(cliente: Client, fornecedor: Fornecedor, **campos: Any) -> Any:
    dados = {
        "nome": fornecedor.nome,
        "email_pedido": fornecedor.email_pedido,
        "prazo_entrega_dias": str(fornecedor.prazo_entrega_dias),
        "informacoes_frete": fornecedor.informacoes_frete,
        **campos,
    }
    return cliente.post(f"/administracao/fornecedores/{fornecedor.pk}/editar/", dados)


def test_edicao_grava_os_quatro_campos_e_audita_so_os_nomes(admin_client: Client) -> None:  # A-8
    fornecedor = FornecedorFactory.create(nome="Antigo", email_pedido="velho@x.com")
    resposta = _editar(
        admin_client,
        fornecedor,
        nome=" Novo Nome ",
        email_pedido=" Novo@Fornecedor.COM ",
        prazo_entrega_dias="10",
        informacoes_frete="Retirada no sítio",
    )
    assert resposta.status_code == 302
    assert resposta["Location"] == f"/administracao/fornecedores/{fornecedor.pk}/"
    fornecedor.refresh_from_db()
    assert fornecedor.nome == "Novo Nome"
    assert fornecedor.email_pedido == "novo@fornecedor.com"
    assert fornecedor.prazo_entrega_dias == 10
    assert fornecedor.informacoes_frete == "Retirada no sítio"
    entrada = EntradaAuditoria.objects.get(acao="fornecedor.editar")
    assert entrada.alteracoes == {
        "fornecedor": fornecedor.pk,
        "campos": ["nome", "email_pedido", "prazo_entrega_dias", "informacoes_frete"],
    }
    assert "Novo" not in str(entrada.alteracoes)
    assert "fornecedor.com" not in str(entrada.alteracoes)


def test_minimo_enviado_na_edicao_e_ignorado(admin_client: Client) -> None:  # A-9
    fornecedor = FornecedorFactory.create(minimo=Decimal("150.00"))
    resposta = _editar(admin_client, fornecedor, nome="Outro Nome", minimo="10")
    assert resposta.status_code == 302
    fornecedor.refresh_from_db()
    assert fornecedor.nome == "Outro Nome"
    assert fornecedor.minimo == Decimal("150.00")
    entrada = EntradaAuditoria.objects.get(acao="fornecedor.editar")
    assert entrada.alteracoes["campos"] == ["nome"]
    assert "minimo" not in str(entrada.alteracoes)


def test_formulario_de_edicao_nao_tem_o_campo_minimo(admin_client: Client) -> None:
    fornecedor = FornecedorFactory.create()
    pagina = admin_client.get(f"/administracao/fornecedores/{fornecedor.pk}/editar/")
    assert pagina.status_code == 200
    assert "minimo" not in pagina.context["form"].fields
    assert 'name="minimo"' not in pagina.content.decode()


def test_edicao_sem_mudanca_nao_audita(admin_client: Client) -> None:  # A-10
    fornecedor = FornecedorFactory.create()
    resposta = _editar(admin_client, fornecedor)
    assert resposta.status_code == 302
    assert EntradaAuditoria.objects.filter(acao="fornecedor.editar").count() == 0


def test_edicao_invalida_devolve_o_formulario_sem_gravar(admin_client: Client) -> None:
    fornecedor = FornecedorFactory.create(nome="Intacto")
    resposta = _editar(admin_client, fornecedor, nome="", prazo_entrega_dias="999")
    assert resposta.status_code == 200
    assert {"nome", "prazo_entrega_dias"} <= set(resposta.context["form"].errors)
    fornecedor.refresh_from_db()
    assert fornecedor.nome == "Intacto"
    assert EntradaAuditoria.objects.count() == 0


def test_detalhe_mostra_so_as_contas_do_fornecedor(admin_client: Client) -> None:  # A-14
    f = FornecedorFactory.create(nome="Fornecedor F")
    g = FornecedorFactory.create(nome="Fornecedor G")
    ContaFactory.create(
        fornecedor=True, fornecedor_id=f.pk, nome="Conta Ativa de F", email_normalizado="a@f.com"
    )
    ContaFactory.create(
        fornecedor=True,
        fornecedor_id=f.pk,
        nome="Conta Removida de F",
        email_normalizado="r@f.com",
        situacao=Situacao.REMOVIDA,
    )
    ContaFactory.create(
        fornecedor=True, fornecedor_id=g.pk, nome="Conta de G", email_normalizado="c@g.com"
    )
    html = admin_client.get(f"/administracao/fornecedores/{f.pk}/").content.decode()
    for esperado in ("Conta Ativa de F", "a@f.com", "Conta Removida de F", "r@f.com", "removida"):
        assert esperado in html
    assert "Conta de G" not in html
    assert "c@g.com" not in html
    assert "Fornecedor F" in html


def test_detalhe_mostra_os_dados_do_fornecedor(admin_client: Client) -> None:
    f = FornecedorFactory.create(
        nome="Boa Terra",
        email_pedido="pedidos@boaterra.com",
        minimo=Decimal("150.00"),
        prazo_entrega_dias=7,
        informacoes_frete="Entrega às terças",
    )
    html = admin_client.get(f"/administracao/fornecedores/{f.pk}/").content.decode()
    for esperado in ("Boa Terra", "pedidos@boaterra.com", "150,00", "7", "Entrega às terças"):
        assert esperado in html


def test_lista_ordenada_por_nome_com_minimo_e_prazo(admin_client: Client) -> None:  # A-15
    FornecedorFactory.create(nome="Zeta", minimo=Decimal("30.00"), prazo_entrega_dias=3)
    FornecedorFactory.create(nome="Alfa", minimo=Decimal("10.00"), prazo_entrega_dias=1)
    FornecedorFactory.create(nome="Meio", minimo=Decimal("20.00"), prazo_entrega_dias=2)
    html = admin_client.get("/administracao/fornecedores/").content.decode()
    posicoes = [html.index(nome) for nome in ("Alfa", "Meio", "Zeta")]
    assert posicoes == sorted(posicoes)
    for minimo in ("10,00", "20,00", "30,00"):
        assert minimo in html


def test_lista_vazia_funciona(admin_client: Client) -> None:
    assert admin_client.get("/administracao/fornecedores/").status_code == 200


def test_id_inexistente_da_404(admin_client: Client) -> None:  # A-16
    assert admin_client.get("/administracao/fornecedores/999999/").status_code == 404
    assert admin_client.get("/administracao/fornecedores/999999/editar/").status_code == 404
    resposta = admin_client.post("/administracao/fornecedores/999999/editar/", {"nome": "X"})
    assert resposta.status_code == 404
