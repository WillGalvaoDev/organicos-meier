"""E05-05: carrinho e formulários de interesse (acceptance A-1 a A-16, A-18 e A-19)."""

import re
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.catalogo.models import Produto, Unidade
from apps.contas.models import Conta
from apps.fornecedores.models import Fornecedor
from apps.interesses import views
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.interesses.servicos import adicionar_interesse, interesse_do_comprador
from apps.rodadas.models import Etapa, Rodada
from tests.apoio.admin_fluxos import administrador_logado
from tests.apoio.interesses import cenario, parcelas, pendente, reservada
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ParcelaFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = pytest.mark.django_db

D = Decimal
AVISO = "Os itens do carrinho são interesses, não compras pagas."
BLOQUEADO = "Os interesses deste fornecedor não podem ser alterados nesta etapa."


def entrar(conta: Conta) -> Client:
    cliente = Client()
    cliente.force_login(conta)
    return cliente


def pagina(cliente: Client, url: str = "/carrinho/") -> str:
    resposta = cliente.get(url)
    assert resposta.status_code == 200
    return str(resposta.content.decode())


def formularios(html: str, produto: Produto, acao: str = "/interesses/") -> list[str]:
    """Os `<form>` da ação cujo campo `produto` é o produto informado."""
    todos = re.findall(r"<form\b.*?</form>", html, re.S)
    return [
        f
        for f in todos
        if f'action="{acao}"' in f and re.search(rf'name="produto"\s+value="{produto.pk}"', f)
    ]


def nomear(rodada: Rodada, nome: str) -> None:
    Fornecedor.objects.filter(pk=rodada.fornecedor_id).update(nome=nome)


def valor_do_campo(formulario: str) -> str:
    achado = re.search(r'name="quantidade"\s+value="([^"]*)"', formulario)
    assert achado is not None, formulario
    return achado.group(1)


def test_carrinho_agrupa_por_fornecedor_e_nao_mostra_o_minimo() -> None:  # A-1
    rodada_x, p, _ = cenario("20", nome="Banana", preco=D("10.00"))
    nomear(rodada_x, "Alfa Hortifruti")
    rodada_y, q, _ = cenario(None, etapa=Etapa.FECHAMENTO, nome="Tomate", preco=D("3.50"))
    nomear(rodada_y, "Beta Granja")
    a = ContaFactory.create()
    adicionar_interesse(a, p, "4")
    adicionar_interesse(a, q, "2")
    html = pagina(entrar(a))
    assert "Alfa Hortifruti" in html
    assert "Beta Granja" in html
    assert html.index("Alfa Hortifruti") < html.index("Beta Granja")
    assert "Etapa: Interesse" in html
    assert "Etapa: Fechamento" in html
    assert "Progresso do mínimo: 40%" in html
    assert "Mínimo atingido." not in html
    for proibido in ("100,00", "60,00"):
        assert proibido not in html
    for texto in ("Reservado: 4", "Pendente: 0", "Subtotal: R$ 40,00"):
        assert texto in html
    assert "Total reservado: R$ 40,00" in html
    assert "Total reservado: R$ 7,00" in html
    assert AVISO in html


@pytest.mark.acceptance
def test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado() -> None:  # A-2, cenário 96
    _, produto, _ = cenario("6", nome="Banana")
    a = ContaFactory.create()
    ParcelaFactory.create(
        comprador=a,
        produto=produto,
        quantidade_original=D("10"),
        quantidade_reservada=D("6"),
        quantidade_pendente=D("4"),
    )
    html = pagina(entrar(a))
    assert "Reservado: 6" in html
    assert "Pendente: 4" in html
    assert len(formularios(html, produto, "/interesses/pendentes/remover/")) == 1
    assert "Remover pendentes" in html


def test_pendente_sem_rodada_ativa() -> None:  # A-3
    z = FornecedorFactory.create(nome="Zeta Sitio")
    r = ProdutoFactory.create(fornecedor=z, unidade=Unidade.UNIDADE, nome="Alface")
    a = ContaFactory.create()
    pendente(a, r, 3)
    html = pagina(entrar(a))
    assert "Zeta Sitio" in html
    assert "Sem rodada ativa." in html
    assert "Reservado: 0" in html
    assert "Pendente: 3" in html
    assert len(formularios(html, r, "/interesses/pendentes/remover/")) == 1
    assert formularios(html, r) == []


def test_caixas_so_com_as_unidades_do_proprio_comprador() -> None:  # A-4, cenário 7
    _, produto, _ = cenario(None, multiplo=D("12"))
    a = ContaFactory.create(nome="Ana Reservada", email_normalizado="ana@reservada.example")
    b = ContaFactory.create(nome="Beto Reservado", email_normalizado="beto@reservado.example")
    adicionar_interesse(a, produto, "8")
    adicionar_interesse(b, produto, "10")
    html_a = pagina(entrar(a))
    html_b = pagina(entrar(b))
    for texto in (
        "Total agregado: 18",
        "Caixas completas: 1",
        "Faltam 6 para a próxima caixa",
        "Suas unidades em caixas: 8",
        "Suas unidades excedentes: 0",
    ):
        assert texto in html_a, texto
    assert "Suas unidades em caixas: 4" in html_b
    assert "Suas unidades excedentes: 6" in html_b
    for html, outro in ((html_a, ("Beto", "beto@")), (html_b, ("Ana", "ana@"))):
        for segredo in outro:
            assert segredo not in html


def test_produto_indisponivel_no_carrinho_e_no_catalogo() -> None:  # A-5
    rodada, produto, _ = cenario("20", disponivel=False)
    a = ContaFactory.create()
    reservada(a, produto, 2)
    cliente = entrar(a)
    for url in ("/carrinho/", f"/catalogo/{rodada.fornecedor_id}/"):
        html = pagina(cliente, url)
        assert "Produto indisponível" in html, url
        assert len(formularios(html, produto)) >= 1, url


def test_definir_e_idempotente_e_zero_remove() -> None:  # A-6
    _, produto, _ = cenario("20", nome="Banana")
    a = ContaFactory.create()
    reservada(a, produto, 4)
    cliente = entrar(a)
    corpo = {"produto": produto.pk, "quantidade": "6", "origem": "carrinho"}
    primeira = cliente.post("/interesses/", corpo)
    assert (primeira.status_code, primeira.get("Location")) == (302, "/carrinho/")
    assert "Interesse atualizado: Banana, reservado 6." in pagina(cliente)
    segunda = cliente.post("/interesses/", corpo)
    assert (segunda.status_code, segunda.get("Location")) == (302, "/carrinho/")
    assert [p.quantidade_original for p in parcelas(produto, a)] == [D("4"), D("2")]
    terceira = cliente.post("/interesses/", {**corpo, "quantidade": "0"})
    assert (terceira.status_code, terceira.get("Location")) == (302, "/carrinho/")
    assert interesse_do_comprador(a, produto).reservado == 0


def test_origem_catalogo_volta_para_o_catalogo() -> None:  # A-7
    rodada, produto, _ = cenario("20")
    a = ContaFactory.create()
    cliente = entrar(a)
    url = f"/catalogo/{rodada.fornecedor_id}/"
    resposta = cliente.post(
        "/interesses/", {"produto": produto.pk, "quantidade": "3", "origem": "catalogo"}
    )
    assert (resposta.status_code, resposta.get("Location")) == (302, url)
    assert "Seu interesse: reservado 3, pendente 0" in pagina(cliente, url)


@pytest.mark.parametrize(
    "texto", ["2,5", "abc", "-1", "1000000000,000", '"><b>x</b>', "25"], ids=str
)
def test_quantidade_recusada_volta_no_formulario_do_produto(texto: str) -> None:  # A-8
    _, p, _ = cenario("20", nome="Banana")
    q = ProdutoFactory.create(fornecedor=p.fornecedor, unidade=Unidade.UNIDADE, nome="Cebola")
    EstoqueDaRodadaFactory.create(
        rodada=Rodada.objects.get(fornecedor=p.fornecedor), produto=q, limite=D("20")
    )
    a = ContaFactory.create()
    reservada(a, p, 4)
    reservada(a, q, 1)
    resposta = entrar(a).post("/interesses/", {"produto": p.pk, "quantidade": texto})
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert len(formularios(html, p)) == 1
    assert len(formularios(html, q)) == 1
    (do_p,) = formularios(html, p)
    (do_q,) = formularios(html, q)
    assert 'role="alert"' in do_p
    assert "<b>x</b>" not in html
    if texto.startswith('"'):
        assert "&quot;&gt;&lt;b&gt;" in do_p
    assert valor_do_campo(do_p) != "4"
    assert valor_do_campo(do_q) == "1"
    assert 'role="alert"' not in do_q
    if texto == "25":
        assert "Há apenas 16 unidade disponível." in do_p
    assert interesse_do_comprador(a, p).reservado == D("4")


@pytest.mark.parametrize("produto", ["abc", "0", "²", "99999999999999999999"])
def test_produto_invalido_nao_derruba(produto: str) -> None:  # A-9
    _, p, _ = cenario("20")
    a = ContaFactory.create()
    reservada(a, p, 4)
    resposta = entrar(a).post("/interesses/", {"produto": produto, "quantidade": "5"})
    assert resposta.status_code == 200
    assert "Produto inválido." in resposta.content.decode()
    assert interesse_do_comprador(a, p).reservado == D("4")


def test_produto_inexistente_da_404() -> None:  # A-9
    _, p, _ = cenario("20")
    a = ContaFactory.create()
    resposta = entrar(a).post("/interesses/", {"produto": p.pk + 100000, "quantidade": "5"})
    assert resposta.status_code == 404


@pytest.mark.parametrize("origem", ["carrinho", "catalogo"])
def test_etapa_mudou_entre_a_pagina_e_o_envio(origem: str) -> None:  # A-10
    rodada, p, _ = cenario("20")
    a = ContaFactory.create()
    reservada(a, p, 4)
    Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.FECHAMENTO_ENCERRADO)
    resposta = entrar(a).post(
        "/interesses/", {"produto": p.pk, "quantidade": "5", "origem": origem}
    )
    assert resposta.status_code == 409
    html = resposta.content.decode()
    assert BLOQUEADO in html
    assert "Etapa: Fechamento com prazo encerrado" in html
    assert formularios(html, p) == []
    assert interesse_do_comprador(a, p).reservado == D("4")


def test_produto_fora_da_rodada_e_rodada_inexistente() -> None:  # A-11
    rodada, _, _ = cenario("20")
    fora = ProdutoFactory.create(fornecedor=rodada.fornecedor, unidade=Unidade.UNIDADE)
    a = ContaFactory.create()
    cliente = entrar(a)
    resposta = cliente.post("/interesses/", {"produto": fora.pk, "quantidade": "1"})
    assert resposta.status_code == 409
    assert "Este produto não está disponível para interesse agora." in resposta.content.decode()
    Rodada.objects.filter(pk=rodada.pk).update(etapa=Etapa.CANCELADA)
    resposta = cliente.post(
        "/interesses/", {"produto": fora.pk, "quantidade": "1", "origem": "catalogo"}
    )
    assert resposta.status_code == 409
    html = resposta.content.decode()
    assert "Seu carrinho" in html or "Carrinho" in html
    assert BLOQUEADO in html


@pytest.mark.acceptance
def test_remover_pendentes_pela_rota() -> None:  # A-12, cenário 97
    _, produto, _ = cenario("20", nome="Banana")
    a = ContaFactory.create()
    ParcelaFactory.create(
        comprador=a,
        produto=produto,
        quantidade_original=D("10"),
        quantidade_reservada=D("6"),
        quantidade_pendente=D("4"),
    )
    cliente = entrar(a)
    resposta = cliente.post(
        "/interesses/pendentes/remover/", {"produto": produto.pk, "quantidade": "2"}
    )
    assert (resposta.status_code, resposta.get("Location")) == (302, "/carrinho/")
    assert "Pendência removida: Banana, pendente 2." in pagina(cliente)
    resumo = interesse_do_comprador(a, produto)
    assert (resumo.reservado, resumo.pendente) == (D("6"), D("2"))


@pytest.mark.acceptance
def test_remocao_de_pendentes_recusada_e_campos_extras_ignorados() -> None:  # A-13
    _, p, _ = cenario("20", nome="Banana")
    _, outro, _ = cenario("20", nome="Manga")
    a = ContaFactory.create()
    pendente(a, p, 4)
    em_pedido = ParcelaFactory.create(
        comprador=a,
        produto=outro,
        quantidade_original=D("3"),
        quantidade_reservada=D("2"),
        quantidade_pendente=D("1"),
        situacao=SituacaoParcela.EM_PEDIDO,
    )
    cliente = entrar(a)
    for texto in ("5", "1.5"):
        resposta = cliente.post(
            "/interesses/pendentes/remover/", {"produto": p.pk, "quantidade": texto}
        )
        assert resposta.status_code == 200
        (formulario,) = formularios(resposta.content.decode(), p, "/interesses/pendentes/remover/")
        assert 'role="alert"' in formulario
    resposta = cliente.post(
        "/interesses/pendentes/remover/",
        {"produto": p.pk, "quantidade": "1", "parcela": em_pedido.pk, "item": em_pedido.pk},
    )
    assert resposta.status_code == 302
    assert interesse_do_comprador(a, p).pendente == D("3")
    em_pedido.refresh_from_db()
    assert (em_pedido.quantidade_reservada, em_pedido.quantidade_pendente) == (D("2"), D("1"))


def test_quem_pode_ver_e_quem_pode_gravar(webauthn: Any) -> None:  # A-14
    administrador = Client()
    administrador_logado(administrador)  # antes da rodada: há um único administrador
    _, p, _ = cenario("20")
    suspenso = ContaFactory.create(suspensa=True)
    reservada(suspenso, p, 2)
    fornecedor = ContaFactory.create(fornecedor=True)
    corpo = {"produto": p.pk, "quantidade": "3"}
    html = pagina(entrar(suspenso))
    assert "Reservado: 2" in html
    assert formularios(html, p) == []
    assert formularios(html, p, "/interesses/pendentes/remover/") == []
    for rota in ("/interesses/", "/interesses/pendentes/remover/"):
        assert entrar(suspenso).post(rota, corpo).status_code == 403
    for cliente in (entrar(fornecedor), administrador):
        assert cliente.get("/carrinho/").status_code == 403
        for rota in ("/interesses/", "/interesses/pendentes/remover/"):
            assert cliente.post(rota, corpo).status_code == 403
    anonimo = Client()
    for resposta in (
        anonimo.get("/carrinho/"),
        anonimo.post("/interesses/", corpo),
        anonimo.post("/interesses/pendentes/remover/", corpo),
    ):
        assert resposta.status_code == 302
        assert str(resposta.get("Location")).startswith("/entrar/")
    assert interesse_do_comprador(suspenso, p).reservado == D("2")
    assert ParcelaDeInteresse.objects.count() == 1


def test_suspensao_entre_a_politica_e_a_trava(monkeypatch: pytest.MonkeyPatch) -> None:  # A-15
    _, p, _ = cenario("20")
    a = ContaFactory.create()
    original = views.definir_interesse  # type: ignore[attr-defined]

    def suspendendo(comprador: Conta, produto: Produto, total: Any) -> Any:
        Conta.objects.filter(pk=comprador.pk).update(situacao="suspensa")
        return original(comprador, produto, total)

    monkeypatch.setattr(views, "definir_interesse", suspendendo)
    resposta = entrar(a).post("/interesses/", {"produto": p.pk, "quantidade": "3"})
    assert resposta.status_code == 403
    assert ParcelaDeInteresse.objects.count() == 0


def _consultas(cliente: Client) -> int:
    with CaptureQueriesContext(connection) as consultas:
        assert cliente.get("/carrinho/").status_code == 200
    return len(consultas)


def _fornecedor_com_produtos(
    comprador: Conta, produtos: int, parcelas_por_produto: int = 1
) -> None:
    rodada = RodadaFactory.create()
    for _ in range(produtos):
        produto = ProdutoFactory.create(fornecedor=rodada.fornecedor, unidade=Unidade.UNIDADE)
        EstoqueDaRodadaFactory.create(rodada=rodada, produto=produto, limite=None)
        reservada(comprador, produto, 1)
        for _ in range(parcelas_por_produto - 1):
            reservada(ContaFactory.create(), produto, 1)


def _comprador_com(fornecedores: int, produtos: int, parcelas_por_produto: int = 1) -> Client:
    comprador = ContaFactory.create()
    for _ in range(fornecedores):
        _fornecedor_com_produtos(comprador, produtos, parcelas_por_produto)
    return entrar(comprador)


def test_numero_de_consultas_do_carrinho() -> None:  # A-16
    um = _consultas(_comprador_com(1, 1))
    assert _consultas(_comprador_com(1, 10, 4)) == um
    dois = _consultas(_comprador_com(2, 1))
    tres = _consultas(_comprador_com(3, 1))
    assert tres - dois == dois - um
    assert 0 < tres - dois <= 6


def test_get_nas_rotas_de_gravacao_responde_405() -> None:  # A-17
    cliente = entrar(ContaFactory.create())
    assert cliente.get("/interesses/").status_code == 405
    assert cliente.get("/interesses/pendentes/remover/").status_code == 405


def test_link_do_carrinho_so_para_comprador() -> None:  # A-18
    comprador = ContaFactory.create()
    assert 'href="/carrinho/"' in pagina(entrar(comprador), "/inicio/")
    fornecedor = ContaFactory.create(fornecedor=True)
    assert "/carrinho/" not in pagina(entrar(fornecedor), "/inicio/")


def test_so_o_percentual_do_minimo_chega_ao_comprador() -> None:  # A-19
    rodada, produto, _ = cenario(None, nome="Banana", preco=D("10.00"))
    Fornecedor.objects.filter(pk=rodada.fornecedor_id).update(minimo=D("987.65"))
    a = ContaFactory.create()
    b = ContaFactory.create(nome="Beto Oculto", email_normalizado="beto@oculto.example")
    reservada(a, produto, 47)
    reservada(b, produto, 3)
    cliente = entrar(a)
    url = f"/catalogo/{rodada.fornecedor_id}/"
    for endereco in ("/carrinho/", url):
        html = pagina(cliente, endereco)
        assert "Progresso do mínimo: 50%" in html, endereco
        for proibido in ("987,65", "987.65", "500,00", "487,65", "Beto", "beto@oculto"):
            assert proibido not in html, (endereco, proibido)
    resposta = cliente.post("/interesses/", {"produto": produto.pk, "quantidade": "96"})
    assert resposta.status_code == 302
    for endereco in ("/carrinho/", url):
        html = pagina(cliente, endereco)
        assert "Progresso do mínimo: 100%" in html, endereco
        assert "Mínimo atingido." in html
        assert "990,00" not in html
