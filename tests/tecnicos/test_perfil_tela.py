"""E02-09: tela de perfil (acceptance A-1 a A-3 e A-16 a A-18)."""

import logging
from typing import Any

import pytest
from django.test import Client

from apps.contas.models import Conta, Papel, Situacao
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

SENHA = "senha-forte-9271!"


def _logado(email: str = "ana@x.com", **campos: Any) -> tuple[Client, Conta]:
    conta = ContaFactory.create(email_normalizado=email, nome="Ana", **campos)
    conta.set_password(SENHA)
    conta.save()
    cliente = Client()
    cliente.post("/entrar/", {"login": email, "password": SENHA})
    return cliente, conta


def test_perfil_mostra_os_campos_e_o_email_so_leitura() -> None:  # A-1
    cliente, _ = _logado(telefone="+5521999998888")
    resposta = cliente.get("/perfil/")
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert 'name="nome"' in html
    assert 'name="telefone"' in html
    assert 'name="avatar"' in html
    assert 'name="whatsapp"' in html
    assert "ana@x.com" in html
    assert 'name="email"' not in html
    assert "99999-8888" in html or "+5521999998888" in html


def test_perfil_exige_login() -> None:
    resposta = Client().get("/perfil/")
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")
    assert Client().post("/perfil/", {"nome": "X"}).status_code == 302


def test_nome_com_espacos_nas_pontas_e_aparado() -> None:  # A-2
    cliente, conta = _logado()
    resposta = cliente.post("/perfil/", {"nome": " Ana Souza ", "telefone": ""})
    assert resposta.status_code == 302
    conta.refresh_from_db()
    assert conta.nome == "Ana Souza"


@pytest.mark.parametrize("nome", ["", "   ", "x" * 151])
def test_nome_invalido_nao_altera_nada(nome: str) -> None:  # A-3
    cliente, conta = _logado()
    resposta = cliente.post("/perfil/", {"nome": nome, "telefone": "21999998888"})
    assert resposta.status_code == 200
    assert resposta.context["form"].errors
    conta.refresh_from_db()
    assert conta.nome == "Ana"
    assert conta.telefone is None


def test_telefone_invalido_devolve_erro_e_nao_grava() -> None:
    cliente, conta = _logado()
    resposta = cliente.post("/perfil/", {"nome": "Ana", "telefone": "+1 212 555 0100"})
    assert resposta.status_code == 200
    assert "telefone" in resposta.context["form"].errors
    conta.refresh_from_db()
    assert conta.telefone is None


def test_telefone_e_gravado_normalizado() -> None:
    cliente, conta = _logado()
    cliente.post("/perfil/", {"nome": "Ana", "telefone": "(21) 99999-8888"})
    conta.refresh_from_db()
    assert conta.telefone == "+5521999998888"


def test_campos_extras_do_post_nao_mudam_a_conta() -> None:  # A-16
    cliente, conta = _logado()
    antes = {
        campo: getattr(conta, campo)
        for campo in ("email_normalizado", "papel", "fornecedor_id", "situacao")
    }
    outro_fornecedor = ContaFactory.create(fornecedor=True).fornecedor_id
    resposta = cliente.post(
        "/perfil/",
        {
            "nome": "Ana Nova",
            "email": "invasor@x.com",
            "email_normalizado": "invasor@x.com",
            "papel": "administrador",
            "fornecedor": outro_fornecedor,
            "situacao": "removida",
        },
    )
    assert resposta.status_code == 302
    conta.refresh_from_db()
    assert conta.nome == "Ana Nova"
    assert {campo: getattr(conta, campo) for campo in antes} == antes


@pytest.mark.parametrize("caso", ["fornecedor", "suspenso"])
def test_fornecedor_e_suspenso_editam_o_perfil(caso: str) -> None:  # A-17
    campos: dict[str, Any] = {"fornecedor": True} if caso == "fornecedor" else {"suspensa": True}
    cliente, conta = _logado(**campos)
    assert cliente.get("/perfil/").status_code == 200
    assert cliente.post("/perfil/", {"nome": "Novo Nome"}).status_code == 302
    conta.refresh_from_db()
    assert conta.nome == "Novo Nome"


def test_administrador_edita_o_perfil(client: Client, webauthn: Any) -> None:  # A-17
    admin = administrador_logado(client)
    assert client.get("/perfil/").status_code == 200
    assert client.post("/perfil/", {"nome": "Administradora"}).status_code == 302
    admin.refresh_from_db()
    assert admin.nome == "Administradora"
    assert admin.papel == Papel.ADMINISTRADOR
    assert admin.situacao == Situacao.ATIVA


def test_cada_conta_so_ve_e_altera_o_proprio_perfil() -> None:
    cliente_a, conta_a = _logado("a@x.com")
    _, conta_b = _logado("b@x.com")
    cliente_a.post("/perfil/", {"nome": "Só A", "pk": conta_b.pk, "id": conta_b.pk})
    conta_a.refresh_from_db()
    conta_b.refresh_from_db()
    assert conta_a.nome == "Só A"
    assert conta_b.nome == "Ana"
    assert cliente_a.get(f"/perfil/?id={conta_b.pk}").context["form"].initial["nome"] == "Só A"


def test_logs_da_requisicao_nao_contem_telefone_nem_email(caplog: pytest.LogCaptureFixture) -> None:
    # A-18
    cliente, _ = _logado()
    with caplog.at_level(logging.DEBUG):
        cliente.post("/perfil/", {"nome": "Ana", "telefone": "(21) 99999-8888", "whatsapp": "on"})
        cliente.post("/perfil/", {"nome": "Ana", "telefone": "099999888"})
    texto = caplog.text
    for dado in ("99999", "999998888", "ana@x.com"):
        assert dado not in texto
