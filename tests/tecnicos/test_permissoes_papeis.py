"""E02-10: rotas protegidas por papel (acceptance A-1 a A-7 e A-9)."""

from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory

from apps.contas.models import Conta, Papel
from tests.apoio import views
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory, FornecedorFactory

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.apoio.urls")]

SENHA = "senha-forte-9271!"
HTMX: Any = {"HTTP_HX_REQUEST": "true"}
ROTAS_DE_COMPRA = ["/teste/carrinho/", "/teste/pagamento/"]
TODAS = [*ROTAS_DE_COMPRA, "/teste/meus-pedidos/", "/teste/fornecedor/painel/"]


@pytest.fixture(autouse=True)
def _zerar() -> None:
    views.zerar_chamadas()


def _logado(email: str = "ana@x.com", **campos: Any) -> Client:
    conta = ContaFactory.create(email_normalizado=email, **campos)
    conta.set_password(SENHA)
    conta.save()
    cliente = Client()
    cliente.post("/entrar/", {"login": email, "password": SENHA})
    assert "_auth_user_id" in cliente.session
    return cliente


@pytest.mark.tecnico
@pytest.mark.parametrize("cabecalhos", [{}, HTMX], ids=["sem_htmx", "com_htmx"])
def test_fornecedor_nao_compra_nem_por_chamada_direta(cabecalhos: Any) -> None:
    # A-1, T-25, cenário 61
    cliente = _logado(fornecedor=True)
    assert cliente.get("/teste/carrinho/", **cabecalhos).status_code == 403
    assert cliente.post("/teste/carrinho/", **cabecalhos).status_code == 403
    assert cliente.post("/teste/pagamento/", **cabecalhos).status_code == 403
    for metodo in (cliente.put, cliente.patch, cliente.delete):
        assert metodo("/teste/pagamento/", **cabecalhos).status_code == 403
    assert views.CHAMADAS == []


@pytest.mark.tecnico
def test_comprador_nao_entra_na_area_do_fornecedor() -> None:  # A-2, T-25
    cliente = _logado()
    assert cliente.get("/teste/fornecedor/painel/").status_code == 403
    assert cliente.post("/teste/fornecedor/painel/", **HTMX).status_code == 403
    assert views.CHAMADAS == []


def test_comprador_ativo_passa_nas_tres_rotas() -> None:  # A-3
    cliente = _logado()
    assert cliente.get("/teste/carrinho/").status_code == 200
    assert cliente.post("/teste/pagamento/").status_code == 200
    assert cliente.get("/teste/meus-pedidos/").status_code == 200
    assert views.CHAMADAS == ["carrinho:GET", "pagamento:POST", "meus-pedidos:GET"]


def test_comprador_suspenso_consulta_mas_nao_compra() -> None:  # A-4
    cliente = _logado(suspensa=True)
    assert cliente.get("/teste/carrinho/").status_code == 403
    assert cliente.post("/teste/carrinho/").status_code == 403
    assert cliente.post("/teste/pagamento/").status_code == 403
    assert views.CHAMADAS == []
    assert cliente.get("/teste/meus-pedidos/").status_code == 200


def test_fornecedor_vinculado_ve_o_proprio_fornecedor() -> None:  # A-5
    fornecedor = FornecedorFactory.create(nome="F")
    cliente = _logado(fornecedor=True, fornecedor_id=fornecedor.pk)
    resposta = cliente.get("/teste/fornecedor/painel/")
    assert resposta.status_code == 200
    assert resposta.json() == {"fornecedor": fornecedor.pk}


def test_administrador_nao_entra_nas_rotas_de_comprador_nem_de_fornecedor(
    client: Client, webauthn: Any
) -> None:  # A-6
    administrador_logado(client)
    for rota in TODAS:
        assert client.get(rota).status_code == 403, rota
        assert client.post(rota).status_code == 403, rota
    assert views.CHAMADAS == []


def test_visitante_anonimo_vai_para_o_login_e_a_view_nao_executa() -> None:  # A-7
    anonimo = Client()
    for rota in TODAS:
        for resposta in (anonimo.get(rota), anonimo.post(rota, **HTMX)):
            assert resposta.status_code == 302, rota
            assert resposta["Location"].startswith("/entrar/"), rota
    assert views.CHAMADAS == []


def test_fornecedor_sem_vinculo_e_recusado_em_profundidade() -> None:  # A-9
    requisicao = RequestFactory().get("/teste/fornecedor/painel/")
    requisicao.user = Conta(
        email_normalizado="orfa@x.com", nome="Órfã", papel=Papel.FORNECEDOR, fornecedor=None
    )
    with pytest.raises(PermissionDenied):
        views.painel_do_fornecedor(requisicao)
    assert views.CHAMADAS == []


def test_fornecedor_nunca_passa_em_decorador_de_comprador() -> None:
    requisicao = RequestFactory().get("/teste/meus-pedidos/")
    requisicao.user = ContaFactory.build(fornecedor=True)
    with pytest.raises(PermissionDenied):
        views.meus_pedidos(requisicao)
    requisicao.user = ContaFactory.build(fornecedor=True)
    with pytest.raises(PermissionDenied):
        views.carrinho(requisicao)


def test_comprador_nunca_passa_no_decorador_de_fornecedor() -> None:
    requisicao = RequestFactory().get("/teste/fornecedor/painel/")
    requisicao.user = ContaFactory.build()
    with pytest.raises(PermissionDenied):
        views.painel_do_fornecedor(requisicao)
