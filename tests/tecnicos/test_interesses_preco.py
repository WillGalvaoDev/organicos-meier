"""E05-06: aviso de alteração de preço (acceptance A-1 a A-9)."""

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from apps.catalogo.models import Produto, Unidade
from apps.catalogo.servicos import editar_produto
from apps.catalogo.sinais import preco_alterado
from apps.contas.models import Conta
from apps.interesses import avisos
from apps.interesses.avisos import avisar_preco_alterado
from apps.interesses.models import SituacaoParcela
from apps.notificacoes.models import Envio, Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.models import Etapa
from tests.apoio.interesses import cenario, pendente, reservada
from tests.fabricas import ContaFactory, ParcelaFactory

pytestmark = pytest.mark.django_db

D = Decimal


def admin() -> Conta:
    return Conta.objects.get(papel="administrador")


def produto_do_cenario(**campos: Any) -> Produto:
    padrao = {
        "unidade": Unidade.KG,
        "incremento": D("0.25"),
        "preco": D("7.99"),
        "nome": "P",
    }
    _, produto, _ = cenario(None, **{**padrao, **campos})
    return produto


def avisos_de(conta: Conta) -> list[Notificacao]:
    return list(Notificacao.objects.filter(conta=conta, evento="preco_alterado").order_by("pk"))


def test_so_quem_tem_reserva_e_avisado() -> None:  # A-1
    produto = produto_do_cenario()
    a, b, c, d = (ContaFactory.create() for _ in range(4))
    reservada(a, produto, "0.25")
    reservada(a, produto, "0.5")
    reservada(b, produto, "1")
    pendente(c, produto, "1")
    editar_produto(admin(), produto, preco="8.99")
    assert len(avisos_de(a)) == 1
    assert len(avisos_de(b)) == 1
    assert avisos_de(c) == []
    assert avisos_de(d) == []
    aviso = avisos_de(a)[0]
    assert aviso.titulo == "Preço alterado: P"
    assert aviso.corpo == (
        "O preço de P mudou de R$ 7,99 para R$ 8,99 por kg. "
        "Seu interesse reservado de 0,75 kg passa de R$ 5,99 para R$ 6,74."
    )
    assert aviso.link == "/carrinho/"
    assert Envio.objects.count() == 0


def test_cada_alteracao_gera_o_seu_aviso() -> None:  # A-2
    produto = produto_do_cenario()
    a, b = ContaFactory.create(), ContaFactory.create()
    reservada(a, produto, "0.75")
    reservada(b, produto, "1")
    editar_produto(admin(), produto, preco="8.99")
    editar_produto(admin(), produto, preco="9.99")
    entradas = list(EntradaAuditoria.objects.filter(acao="produto.alterar_preco").order_by("id"))
    assert len(entradas) == 2
    for conta in (a, b):
        chaves = [n.chave for n in avisos_de(conta)]
        assert chaves == [f"preco_alterado:{e.pk}:{conta.pk}" for e in entradas]


def test_mesmo_fato_nao_duplica() -> None:  # A-3
    produto = produto_do_cenario()
    a = ContaFactory.create()
    reservada(a, produto, "0.75")
    editar_produto(admin(), produto, preco="8.99")
    alteracao = EntradaAuditoria.objects.get(acao="produto.alterar_preco")
    from django.db import transaction

    with transaction.atomic():
        for _ in range(2):
            avisar_preco_alterado(
                Produto,
                produto=produto,
                anterior=D("7.99"),
                novo=D("8.99"),
                alteracao=alteracao,
            )
    assert len(avisos_de(a)) == 1


@pytest.mark.acceptance
def test_preco_alterado_no_fechamento_atinge_o_carrinho(client: Client) -> None:  # A-4, cenário 72
    _, produto, _ = cenario(None, etapa=Etapa.FECHAMENTO, unidade=Unidade.KG, preco=D("7.99"))
    a = ContaFactory.create()
    reservada(a, produto, "1")
    editar_produto(admin(), produto, preco="8.99")
    assert len(avisos_de(a)) == 1
    client.force_login(a)
    html = client.get("/carrinho/").content.decode()
    assert "Subtotal: R$ 8,99" in html


def test_parcela_em_pedido_nao_e_avisada() -> None:  # A-5
    produto = produto_do_cenario()
    a = ContaFactory.create()
    ParcelaFactory.create(
        comprador=a,
        produto=produto,
        quantidade_original=D("1"),
        quantidade_reservada=D("1"),
        situacao=SituacaoParcela.EM_PEDIDO,
    )
    editar_produto(admin(), produto, preco="8.99")
    assert Notificacao.objects.filter(evento="preco_alterado").count() == 0


def test_sem_parcelas_e_edicao_so_de_descricao_nao_avisam() -> None:  # A-6
    produto = produto_do_cenario()
    recebido: list[Any] = []

    def ouvir(sender: Any, **kwargs: Any) -> None:
        recebido.append(kwargs)

    a = ContaFactory.create()
    reservada(a, produto, "1")
    preco_alterado.connect(ouvir, weak=False)
    try:
        editar_produto(admin(), produto, descricao="Nova descrição")
    finally:
        preco_alterado.disconnect(ouvir)
    assert recebido == []
    assert Notificacao.objects.filter(evento="preco_alterado").count() == 0
    sem_parcelas = produto_do_cenario(nome="Sem parcelas")
    editar_produto(admin(), sem_parcelas, preco="9.99")
    assert Notificacao.objects.filter(evento="preco_alterado").count() == 0


def test_falha_na_emissao_desfaz_a_alteracao(monkeypatch: pytest.MonkeyPatch) -> None:  # A-7
    produto = produto_do_cenario()
    a = ContaFactory.create()
    reservada(a, produto, "1")

    def estoura(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("falha na emissão")

    monkeypatch.setattr(avisos, "emitir_evento", estoura)
    with pytest.raises(RuntimeError):
        editar_produto(admin(), produto, preco="8.99")
    produto.refresh_from_db()
    assert produto.preco == D("7.99")
    assert EntradaAuditoria.objects.filter(acao="produto.alterar_preco").count() == 0
    assert Notificacao.objects.filter(evento="preco_alterado").count() == 0


def test_titulo_cortado_em_150_caracteres() -> None:  # A-8
    produto = produto_do_cenario(nome="N" * 150, unidade=Unidade.UNIDADE, incremento=D("1"))
    a = ContaFactory.create()
    reservada(a, produto, "1")
    editar_produto(admin(), produto, preco="9.99")
    recebidos = avisos_de(a)
    assert len(recebidos) == 1
    aviso = recebidos[0]
    assert len(aviso.titulo) == 150
    assert aviso.titulo.startswith("Preço alterado: ")


@pytest.fixture
def espiao() -> Iterator[list[dict[str, Any]]]:
    recebido: list[dict[str, Any]] = []

    def ouvir(sender: Any, **kwargs: Any) -> None:
        recebido.append(kwargs)

    preco_alterado.connect(ouvir, weak=False)
    yield recebido
    preco_alterado.disconnect(ouvir)


def test_o_sinal_leva_a_entrada_de_auditoria(espiao: list[dict[str, Any]]) -> None:  # A-9
    produto = produto_do_cenario()
    editar_produto(admin(), produto, preco="8.99")
    (chamada,) = espiao
    assert chamada["produto"].pk == produto.pk
    assert (chamada["anterior"], chamada["novo"]) == (D("7.99"), D("8.99"))
    assert "alteracao" in chamada
    alteracao = chamada["alteracao"]
    assert isinstance(alteracao, EntradaAuditoria)
    assert alteracao.acao == "produto.alterar_preco"
    assert alteracao.objeto_id == str(produto.pk)
