"""E16-09 A-2 a A-7: reservado e pendente atuais na tela "Meus pedidos" (`GET /pedidos/`)."""

import re
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from apps.catalogo.models import Unidade
from apps.contas.models import Conta
from apps.interesses.models import ParcelaDeInteresse
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.admin_fluxos import administrador_logado
from tests.apoio.interesses import cenario, pendente, reservada
from tests.fabricas import ContaFactory, FornecedorFactory, ParcelaFactory, ProdutoFactory

pytestmark = pytest.mark.django_db

D = Decimal
TITULO = "Interesses reservados e pendentes"
SEM_INTERESSES = "Você não tem interesses reservados nem pendentes."
SEM_PEDIDOS = "Você ainda não tem pedidos."


def _entrar(conta: Conta) -> Client:
    cliente = Client()
    cliente.force_login(conta)
    return cliente


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _secao(resposta: Any) -> str:
    """O HTML da seção de interesses: do título ao fim da página."""
    html: str = resposta.content.decode()
    assert f"<h2>{TITULO}</h2>" in html
    return html.split(f"<h2>{TITULO}</h2>", 1)[1]


def _pares(html: str) -> list[tuple[str, str, str]]:
    """(produto, reservado, pendente) de cada item da página, na ordem em que aparecem."""
    pares = []
    for item in html.split("<li>")[1:]:
        nome = re.search(r"<(?:h3|strong)>(.*?)</(?:h3|strong)>", item, re.S)
        reservado = re.search(r"Reservado: ([\d,.]+)", item)
        pendente_ = re.search(r"Pendente: ([\d,.]+)", item)
        if nome and reservado and pendente_:
            pares.append((nome.group(1).strip(), reservado.group(1), pendente_.group(1)))
    return pares


def _arranjo_do_a1() -> tuple[Conta, Any]:
    """A com 6 reservados e 4 pendentes de P, estoque livre zero."""
    _, p, _ = cenario("6", nome="Banana")
    a = ContaFactory.create()
    ParcelaFactory.create(
        comprador=a,
        produto=p,
        quantidade_original=D("10"),
        quantidade_reservada=D("6"),
        quantidade_pendente=D("4"),
    )
    return a, p


def test_historico_e_carrinho_mostram_os_mesmos_pares() -> None:  # A-2
    a, _ = _arranjo_do_a1()
    _, q, _ = cenario("5", nome="Alface")
    reservada(a, q, 2)
    cliente = _entrar(a)
    carrinho_html = cliente.get("/carrinho/").content.decode()
    historico_resposta = cliente.get("/pedidos/")
    historico = _texto(historico_resposta)
    pares_do_carrinho = sorted(_pares(carrinho_html))
    pares_do_historico = sorted(_pares(_secao(historico_resposta)))
    assert pares_do_historico == pares_do_carrinho
    assert len(pares_do_historico) == 2
    assert "Reservado: 2" in historico
    assert "Pendente: 0" in historico
    assert "Reservado: 6" in historico
    assert "Pendente: 4" in historico


def _secao_texto(texto: str) -> str:
    assert TITULO in texto
    return texto.split(TITULO, 1)[1]


def test_pendente_sem_rodada_ativa_e_produto_indisponivel_aparece_com_a_unidade() -> None:  # A-3
    z = FornecedorFactory.create(nome="Zeta Sitio")
    produto = ProdutoFactory.create(
        fornecedor=z, unidade=Unidade.KG, nome="Cenoura", disponivel=False
    )
    a = ContaFactory.create()
    pendente(a, produto, 4)
    texto = _texto(_entrar(a).get("/pedidos/"))
    secao = _secao_texto(texto)
    assert "Zeta Sitio" in secao
    assert "Cenoura" in secao
    assert "Reservado: 0" in secao
    assert "Pendente: 4" in secao
    assert "kg" in secao.lower()


def test_comprador_so_ve_as_proprias_linhas_e_a_url_nao_escolhe_outro() -> None:  # A-4
    a, p = _arranjo_do_a1()
    _, q, _ = cenario("5", nome="Alface")
    b = ContaFactory.create()
    reservada(b, q, 1)
    cliente = _entrar(b)
    for url in ("/pedidos/", f"/pedidos/?comprador={a.pk}"):
        resposta = cliente.get(url)
        assert resposta.status_code == 200
        secao = _secao_texto(_texto(resposta))
        assert "Alface" in secao
        assert p.nome not in secao
        assert "Pendente: 4" not in secao
        assert "Reservado: 6" not in secao
        assert "Reservado: 1" in secao


def test_sem_pedidos_a_mensagem_continua_e_a_secao_aparece_do_mesmo_jeito() -> None:  # A-5
    vazio = _texto(_entrar(ContaFactory.create()).get("/pedidos/"))
    assert SEM_PEDIDOS in vazio
    assert SEM_INTERESSES in _secao_texto(vazio)
    comprador = ContaFactory.create()
    produto = ProdutoFactory.create(unidade=Unidade.UNIDADE, nome="Beterraba")
    pendente(comprador, produto, 3)
    com_pendentes = _texto(_entrar(comprador).get("/pedidos/"))
    assert SEM_PEDIDOS in com_pendentes
    assert "Pendente: 3" in _secao_texto(com_pendentes)
    assert SEM_INTERESSES not in com_pendentes


def test_a_politica_da_rota_nao_mudou(webauthn: Any) -> None:  # A-6 (regressão)
    administrador = Client()
    administrador_logado(administrador)
    fornecedor = ContaFactory.create(fornecedor=True)
    anonimo = Client().get("/pedidos/")
    assert anonimo.status_code == 302
    assert str(anonimo.get("Location")).startswith("/entrar/")
    for cliente in (_entrar(fornecedor), administrador):
        resposta = cliente.get("/pedidos/")
        assert resposta.status_code == 403
        assert TITULO not in resposta.content.decode()


def test_a_secao_e_so_de_leitura_e_a_requisicao_nao_grava() -> None:  # A-7
    a, _ = _arranjo_do_a1()
    antes = (
        ParcelaDeInteresse.objects.count(),
        EntradaAuditoria.objects.count(),
        Notificacao.objects.count(),
        list(
            ParcelaDeInteresse.objects.filter(comprador=a).values_list(
                "quantidade_reservada", "quantidade_pendente"
            )
        ),
    )
    resposta = _entrar(a).get("/pedidos/")
    secao = _secao(resposta)
    assert "<form" not in secao
    assert "<button" not in secao
    assert 'href="/carrinho/"' in secao
    assert "Alterar no carrinho" in secao
    depois = (
        ParcelaDeInteresse.objects.count(),
        EntradaAuditoria.objects.count(),
        Notificacao.objects.count(),
        list(
            ParcelaDeInteresse.objects.filter(comprador=a).values_list(
                "quantidade_reservada", "quantidade_pendente"
            )
        ),
    )
    assert depois == antes
