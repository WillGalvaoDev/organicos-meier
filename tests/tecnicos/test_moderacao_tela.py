"""E02-08: tela de usuários (acceptance A-13 e A-18)."""

from typing import Any

import pytest
from django.test import Client

from apps.contas.models import Conta, EmailBanido, Situacao
from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

LISTA = "/administracao/usuarios/"


def _acoes(pk: int) -> list[str]:
    return [
        f"/administracao/usuarios/{pk}/{acao}/" for acao in ("suspender", "reativar", "remover")
    ]


@pytest.mark.parametrize("fornecedor", [False, True], ids=["comprador", "fornecedor"])
def test_outros_papeis_recebem_403_e_nada_muda(client: Client, fornecedor: bool) -> None:  # A-13
    alvo = ContaFactory.create(email_normalizado="alvo@x.com")
    client.force_login(ContaFactory.create(fornecedor=fornecedor))
    assert client.get(LISTA).status_code == 403
    assert client.post(LISTA).status_code == 403
    for rota in _acoes(alvo.pk):
        assert client.get(rota).status_code == 403
        assert client.post(rota).status_code == 403
    alvo.refresh_from_db()
    assert alvo.situacao == Situacao.ATIVA
    assert EmailBanido.objects.count() == 0


def test_visitante_anonimo_vai_para_o_login(client: Client) -> None:  # A-13
    alvo = ContaFactory.create()
    for rota in [LISTA, *_acoes(alvo.pk)]:
        for resposta in (client.get(rota), client.post(rota)):
            assert resposta.status_code == 302
            assert resposta["Location"].startswith("/entrar/")
    alvo.refresh_from_db()
    assert alvo.situacao == Situacao.ATIVA


def test_lista_mostra_so_compradores_e_fornecedores_com_os_botoes_permitidos(
    client: Client, webauthn: Any
) -> None:  # A-18
    admin = administrador_logado(client)
    ativo = ContaFactory.create(email_normalizado="ativo@x.com", nome="Comprador Ativo")
    suspenso = ContaFactory.create(
        email_normalizado="suspenso@x.com", nome="Comprador Suspenso", suspensa=True
    )
    fornecedor = ContaFactory.create(
        fornecedor=True, email_normalizado="forn@x.com", nome="Fornecedor Um"
    )
    removido = ContaFactory.create(
        email_normalizado="removido@x.com", nome="Comprador Removido", situacao=Situacao.REMOVIDA
    )
    html = client.get(LISTA).content.decode()
    assert admin.email_normalizado not in html
    for conta in (ativo, suspenso, fornecedor, removido):
        assert conta.email_normalizado in html
        assert conta.nome in html
    assert fornecedor.fornecedor is not None
    assert fornecedor.fornecedor.nome in html

    esperados = {
        ativo.pk: {"suspender", "remover"},
        suspenso.pk: {"reativar", "remover"},
        fornecedor.pk: {"remover"},
        removido.pk: set(),
    }
    for pk, permitidas in esperados.items():
        for acao in ("suspender", "reativar", "remover"):
            presente = f"/administracao/usuarios/{pk}/{acao}/" in html
            assert presente == (acao in permitidas), (pk, acao)


def test_acoes_pela_tela_suspendem_e_reativam(client: Client, webauthn: Any) -> None:
    administrador_logado(client)
    alvo = ContaFactory.create(email_normalizado="ana@x.com")
    resposta = client.post(f"/administracao/usuarios/{alvo.pk}/suspender/")
    assert resposta.status_code == 302
    alvo.refresh_from_db()
    assert alvo.situacao == Situacao.SUSPENSA
    client.post(f"/administracao/usuarios/{alvo.pk}/reativar/")
    alvo.refresh_from_db()
    assert alvo.situacao == Situacao.ATIVA


def test_acao_invalida_aparece_como_mensagem_sem_erro_500(client: Client, webauthn: Any) -> None:
    administrador_logado(client)
    fornecedor = ContaFactory.create(fornecedor=True)
    resposta = client.post(f"/administracao/usuarios/{fornecedor.pk}/suspender/", follow=True)
    assert resposta.status_code == 200
    assert "não é permitida" in resposta.content.decode()
    fornecedor.refresh_from_db()
    assert fornecedor.situacao == Situacao.ATIVA


def test_acao_desconhecida_ou_conta_inexistente_da_404(client: Client, webauthn: Any) -> None:
    administrador_logado(client)
    alvo = ContaFactory.create()
    assert client.post(f"/administracao/usuarios/{alvo.pk}/apagar/").status_code == 404
    assert client.post("/administracao/usuarios/999999/suspender/").status_code == 404
    assert client.get("/administracao/usuarios/999999/remover/").status_code == 404
    assert Conta.objects.filter(pk=alvo.pk).exists()


def test_o_administrador_nao_pode_ser_alvo_pela_tela(client: Client, webauthn: Any) -> None:
    admin = administrador_logado(client)
    for acao in ("suspender", "reativar", "remover"):
        resposta = client.post(f"/administracao/usuarios/{admin.pk}/{acao}/", follow=True)
        assert resposta.status_code in (200, 404)
    admin.refresh_from_db()
    assert admin.situacao == Situacao.ATIVA
    assert EmailBanido.objects.count() == 0
