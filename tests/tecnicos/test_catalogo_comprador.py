"""E03-08: catálogo do comprador (acceptance A-1 a A-6, A-9 a A-13)."""

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.urls import resolve

from apps.catalogo.consultas import fornecedores_no_catalogo, produtos_do_catalogo
from apps.catalogo.models import Produto, Unidade
from apps.catalogo.servicos import editar_produto
from apps.contas.models import Conta, Papel
from apps.contas.permissoes import Politica, politica_da_view
from apps.fornecedores.models import Fornecedor
from apps.interesses.models import SituacaoParcela
from apps.rodadas.models import Etapa
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


@pytest.fixture
def comprador_client(client: Client) -> Client:
    client.force_login(ContaFactory.create(email_normalizado="leitor@exemplo.com"))
    return client


def _pagina(cliente: Client, fornecedor: Fornecedor) -> str:
    resposta = cliente.get(f"/catalogo/{fornecedor.pk}/")
    assert resposta.status_code == 200
    return str(resposta.content.decode())


def _produto_na_rodada(rodada: Any, limite: str | None = "10", **campos: Any) -> Produto:
    produto = ProdutoFactory.create(fornecedor=rodada.fornecedor, **campos)
    EstoqueDaRodadaFactory.create(
        rodada=rodada, produto=produto, limite=None if limite is None else D(limite)
    )
    return produto


def _reservar(produto: Produto, quantidade: str) -> None:
    ParcelaFactory.create(
        produto=produto, quantidade_original=D(quantidade), quantidade_reservada=D(quantidade)
    )


def test_banana_mostra_preco_incremento_e_disponivel(comprador_client: Client) -> None:  # A-1
    rodada = RodadaFactory.create()
    banana = _produto_na_rodada(
        rodada,
        "10",
        nome="Banana",
        descricao="Banana prata",
        unidade=Unidade.KG,
        incremento=D("0.250"),
        preco=D("7.99"),
        multiplo=None,
    )
    _reservar(banana, "6")
    html = _pagina(comprador_client, rodada.fornecedor)
    for esperado in ("Banana", "Banana prata", "R$ 7,99 / kg", "0,25 kg", "4 kg disponível"):
        assert esperado in html, esperado
    assert "múltiplo de compra" not in html
    assert "Produto indisponível" not in html


def test_maca_mostra_multiplo_e_sem_limite(comprador_client: Client) -> None:  # A-2
    rodada = RodadaFactory.create()
    _produto_na_rodada(
        rodada,
        None,
        nome="Maçã",
        unidade=Unidade.UNIDADE,
        incremento=D("2.000"),
        multiplo=D("12.000"),
        preco=D("1.50"),
    )
    html = _pagina(comprador_client, rodada.fornecedor)
    assert "múltiplo de compra: 12" in html
    assert "Sem limite" in html
    assert "12,000" not in html
    assert "Esgotado" not in html


def test_estoque_zero_e_tudo_reservado_aparecem_como_esgotado(
    comprador_client: Client,
) -> None:  # A-3
    rodada = RodadaFactory.create()
    _produto_na_rodada(rodada, "0", nome="Zerado")
    cheio = _produto_na_rodada(rodada, "10", nome="Cheio")
    _reservar(cheio, "10")
    html = _pagina(comprador_client, rodada.fornecedor)
    assert html.count("Esgotado") == 2
    assert "disponível" not in html.replace("indisponível", "")


def test_produto_fora_da_rodada_nao_aparece_e_indisponivel_traz_a_marcacao(
    comprador_client: Client,
) -> None:  # A-4, D-1
    rodada = RodadaFactory.create()
    _produto_na_rodada(rodada, "5", nome="Produto Disponível", disponivel=True)
    _produto_na_rodada(rodada, "5", nome="Produto Fora de Estoque", disponivel=False)
    ProdutoFactory.create(fornecedor=rodada.fornecedor, nome="Produto Sem Inclusão")
    html = _pagina(comprador_client, rodada.fornecedor)
    assert "Produto Sem Inclusão" not in html
    assert "Produto Disponível" in html
    assert html.count("Produto indisponível") == 1
    indisponivel = html.index("Produto Fora de Estoque")
    marcacao = html.index("Produto indisponível")
    disponivel = html.index("Produto Disponível")
    # a marcação fica junto da descrição do indisponível, longe do disponível
    assert abs(marcacao - indisponivel) < abs(marcacao - disponivel)


def test_produtos_saem_em_ordem_de_nome(comprador_client: Client) -> None:
    rodada = RodadaFactory.create()
    for nome in ("Zebra", "Abacate", "Maracujá"):
        _produto_na_rodada(rodada, "5", nome=nome)
    html = _pagina(comprador_client, rodada.fornecedor)
    posicoes = [html.index(nome) for nome in ("Abacate", "Maracujá", "Zebra")]
    assert posicoes == sorted(posicoes)


def test_lista_de_fornecedores_com_rodada_e_produto(comprador_client: Client) -> None:  # A-5
    zeta = RodadaFactory.create(
        fornecedor=FornecedorFactory.create(nome="Zeta"), etapa=Etapa.FECHAMENTO
    )
    _produto_na_rodada(zeta, "5")
    alfa = RodadaFactory.create(fornecedor=FornecedorFactory.create(nome="Alfa"))
    _produto_na_rodada(alfa, "5")
    FornecedorFactory.create(nome="Sem")
    RodadaFactory.create(fornecedor=FornecedorFactory.create(nome="Vazio"))
    marcado = RodadaFactory.create(fornecedor=FornecedorFactory.create(nome="Marcado"))
    _produto_na_rodada(marcado, "5", disponivel=False)
    antigo = RodadaFactory.create(
        fornecedor=FornecedorFactory.create(nome="Antigo"), etapa=Etapa.DISPONIVEL_PARA_RETIRADA
    )
    _produto_na_rodada(antigo, "5")
    resposta = comprador_client.get("/catalogo/")
    assert resposta.status_code == 200
    html = resposta.content.decode()
    posicoes = [html.index(nome) for nome in ("Alfa", "Marcado", "Zeta")]
    assert posicoes == sorted(posicoes)
    assert "Interesse" in html
    assert "Fechamento" in html
    for ausente in ("Sem", "Vazio", "Antigo"):
        assert f">{ausente}<" not in html, ausente
    assert [r.fornecedor.nome for r in fornecedores_no_catalogo()] == ["Alfa", "Marcado", "Zeta"]


def test_lista_vazia_funciona(comprador_client: Client) -> None:
    resposta = comprador_client.get("/catalogo/")
    assert resposta.status_code == 200
    assert "Nenhum fornecedor" in resposta.content.decode()


def test_fornecedor_sem_rodada_ativa_ou_inexistente_da_404_igual(
    comprador_client: Client,
) -> None:  # A-6
    sem = FornecedorFactory.create(nome="Sem")
    terminada = RodadaFactory.create(etapa=Etapa.CANCELADA)
    respostas = [
        comprador_client.get(f"/catalogo/{sem.pk}/"),
        comprador_client.get("/catalogo/999999/"),
        comprador_client.get(f"/catalogo/{terminada.fornecedor_id}/"),
    ]
    assert [r.status_code for r in respostas] == [404, 404, 404]
    assert len({r.content for r in respostas}) == 1


def test_campos_internos_e_dados_de_compradores_nao_aparecem(
    comprador_client: Client,
) -> None:  # A-9
    fornecedor = FornecedorFactory.create(
        nome="Fornecedor Visivel",
        email_pedido="pedidos-secretos@fornecedor.com",
        minimo=D("987.65"),
        prazo_entrega_dias=33,
        informacoes_frete="Frete sigiloso de teste",
    )
    ContaFactory.create(
        fornecedor=True,
        fornecedor_id=fornecedor.pk,
        nome="Conta Vinculada Secreta",
        email_normalizado="vinculada@fornecedor.com",
    )
    rodada = RodadaFactory.create(fornecedor=fornecedor)
    produto = _produto_na_rodada(rodada, "20", nome="Banana")
    for nome, email in (("Ana Compradora", "ana@x.com"), ("Bia Compradora", "bia@x.com")):
        comprador = ContaFactory.create(nome=nome, email_normalizado=email)
        ParcelaFactory.create(
            comprador=comprador,
            produto=produto,
            quantidade_original=D("3"),
            quantidade_reservada=D("2"),
            quantidade_pendente=D("1"),
            situacao=SituacaoParcela.ATIVA,
        )
    html = _pagina(comprador_client, fornecedor)
    assert "Fornecedor Visivel" in html
    for proibido in (
        "pedidos-secretos@fornecedor.com",
        "987,65",
        "987.65",
        "33",
        "Frete sigiloso de teste",
        "Conta Vinculada Secreta",
        "vinculada@fornecedor.com",
        "Ana Compradora",
        "ana@x.com",
        "Bia Compradora",
        "bia@x.com",
    ):
        assert proibido not in html, proibido
    assert "reservad" not in html.lower()
    assert "pendente" not in html.lower()


@pytest.mark.parametrize("quantidade", [1, 20])
def test_numero_de_consultas_nao_cresce_com_os_produtos(
    comprador_client: Client, django_assert_max_num_queries: Any, quantidade: int
) -> None:  # A-10
    rodada = RodadaFactory.create()
    for numero in range(quantidade):
        produto = _produto_na_rodada(rodada, "10", nome=f"Produto {numero:02d}")
        _reservar(produto, "3")
    with django_assert_max_num_queries(8):
        resposta = comprador_client.get(f"/catalogo/{rodada.fornecedor_id}/")
    assert resposta.status_code == 200
    assert resposta.content.decode().count("7 kg disponível") == quantidade


def test_fornecedor_com_rodada_sem_produto_mostra_a_mensagem(
    comprador_client: Client,
) -> None:  # A-11
    rodada = RodadaFactory.create()
    html = _pagina(comprador_client, rodada.fornecedor)
    assert "Nenhum produto nesta rodada." in html


def test_as_duas_rotas_declaram_a_politica_de_comprador() -> None:  # A-12
    for caminho in ("/catalogo/", "/catalogo/1/"):
        assert politica_da_view(resolve(caminho).func) is Politica.COMPRADOR


def test_marcacao_some_quando_o_produto_volta_a_ficar_disponivel(
    comprador_client: Client,
) -> None:  # A-13, D-1
    rodada = RodadaFactory.create()
    produto = _produto_na_rodada(rodada, "5", disponivel=False)
    assert "Produto indisponível" in _pagina(comprador_client, rodada.fornecedor)
    admin = Conta.objects.get(papel=Papel.ADMINISTRADOR)
    editar_produto(admin, produto, disponivel=True)
    assert "Produto indisponível" not in _pagina(comprador_client, rodada.fornecedor)


def test_etapas_fora_de_interesse_ainda_mostram_o_catalogo_com_a_etapa(
    comprador_client: Client,
) -> None:
    rodada = RodadaFactory.create(etapa=Etapa.PAGAMENTO)
    _produto_na_rodada(rodada, "5", nome="Banana")
    html = _pagina(comprador_client, rodada.fornecedor)
    assert "Banana" in html
    assert "Pagamento" in html


def test_consulta_devolve_produto_estoque_e_livre() -> None:
    rodada = RodadaFactory.create()
    p = _produto_na_rodada(rodada, "10", nome="A")
    _reservar(p, "6")
    sem_limite = _produto_na_rodada(rodada, None, nome="B")
    itens = produtos_do_catalogo(rodada.fornecedor)
    assert [(i.produto.pk, i.livre) for i in itens] == [(p.pk, D("4.000")), (sem_limite.pk, None)]


def test_precos_grandes_usam_milhar_com_ponto(comprador_client: Client) -> None:
    rodada = RodadaFactory.create()
    _produto_na_rodada(rodada, "5", nome="Caro", preco=D("1234.56"), unidade=Unidade.CAIXA)
    assert "R$ 1.234,56 / caixa" in _pagina(comprador_client, rodada.fornecedor)


def test_inicio_do_comprador_tem_link_para_o_catalogo(comprador_client: Client) -> None:
    html = comprador_client.get("/inicio/").content.decode()
    assert 'href="/catalogo/"' in html
