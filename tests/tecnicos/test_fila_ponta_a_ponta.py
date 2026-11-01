"""E11-08: a fila de pendentes de ponta a ponta, com os pendentes reais da apuração (A-1 a A-13).

O arranjo FP: a rodada R1 de F (mínimo 50,00) com P (10,00, múltiplo 20: A 6, C 8 e B 6, uma caixa
só) e Q (10,00, A 10); A e C pagam, B não; a apuração invalida a caixa de P, estorna A e C e leva as
parcelas de A e de C em P para a fila; o resultado válido é aprovado; R1 sai das etapas ativas; e
uma rodada R2 de F é aberta em interesse, sem o múltiplo de P (E11-08, `spec.md`).
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.test import Client

from apps.catalogo.models import Produto, Unidade
from apps.catalogo.quantidades import QuantidadeRecusada
from apps.catalogo.servicos import alterar_multiplo
from apps.contas.models import Conta
from apps.financeiro.models import ObrigacaoComComprador, Reembolso
from apps.fornecedores.models import Fornecedor
from apps.fornecedores.servicos import alterar_minimo
from apps.interesses.consultas import total_reservado
from apps.interesses.fila import alocar_pendentes
from apps.interesses.models import ParcelaDeInteresse
from apps.interesses.progresso import progresso_da_rodada
from apps.interesses.servicos import (
    EstoqueInsuficiente,
    RemocaoAcimaDoPendente,
    adicionar_interesse,
    reduzir_interesse,
    remover_pendente,
)
from apps.pedidos.abertura import abrir_pagamento
from apps.pedidos.apuracao import aprovar_resultado, iniciar_apuracao
from apps.pedidos.models import ItemDoPedido
from apps.rodadas.estoque import alterar_estoque, incluir_produto_na_rodada
from apps.rodadas.fechamento import TransicaoRecusada, encerrar_fechamento, iniciar_fechamento
from apps.rodadas.models import EstoqueDaRodada, Etapa, Rodada
from apps.rodadas.servicos import abrir_rodada
from tests.apoio.apuracao import H, pagar
from tests.apoio.pedidos import T0, administrador, pedido_de
from tests.conftest import RelogioControlado
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
PRAZO = T0 + 48 * H
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


@dataclass
class FP:
    fornecedor: Fornecedor
    r1: Rodada
    p: Produto
    q: Produto
    a: Conta
    b: Conta
    c: Conta
    admin: Conta


def montar_fp(relogio: RelogioControlado, sim: Any) -> FP:
    """Os passos 1 a 6 do arranjo FP: R1 apurada, aprovada e fora das etapas ativas."""
    relogio.congelar(T0 - 25 * H)
    fornecedor = FornecedorFactory.create(nome="F", minimo=D("50.00"))
    r1 = RodadaFactory.create(fornecedor=fornecedor)
    admin = administrador()
    p = ProdutoFactory.create(
        fornecedor=fornecedor,
        nome="P",
        unidade=Unidade.UNIDADE,
        preco=D("10.00"),
        multiplo=D("20.000"),
    )
    q = ProdutoFactory.create(
        fornecedor=fornecedor, nome="Q", unidade=Unidade.UNIDADE, preco=D("10.00")
    )
    for produto in (p, q):
        EstoqueDaRodadaFactory.create(rodada=r1, produto=produto, limite=None)
    a = ContaFactory.create(nome="Comprador A")
    b = ContaFactory.create(nome="Comprador B")
    c = ContaFactory.create(nome="Comprador C")
    for dono, produto, quantidade in ((a, p, 6), (c, p, 8), (b, p, 6), (a, q, 10)):
        ParcelaFactory.create(
            comprador=dono,
            produto=produto,
            quantidade_original=D(quantidade),
            quantidade_reservada=D(quantidade),
        )
    iniciar_fechamento(admin, r1)
    relogio.congelar(T0)
    encerrar_fechamento(r1)
    r1.refresh_from_db()
    abrir_pagamento(admin, r1, D("20.00"))
    pagar(relogio, sim, pedido_de(a))
    pagar(relogio, sim, pedido_de(c))
    relogio.congelar(PRAZO)
    iniciar_apuracao(admin, r1)
    relogio.congelar(T0 + 49 * H)
    aprovar_resultado(admin, r1)
    Rodada.objects.filter(pk=r1.pk).update(etapa=Etapa.DISPONIVEL_PARA_RETIRADA)
    r1.refresh_from_db()
    return FP(fornecedor, r1, p, q, a, b, c, admin)


def abrir_r2(fp: FP, limite_de_p: int | None = 10, *, com_q: bool = False) -> Rodada:
    """O passo 7: R2 em interesse, sem o múltiplo de P, com P no estoque pelo serviço."""
    r2 = abrir_rodada(fp.admin, fp.fornecedor)
    alterar_multiplo(fp.admin, fp.p, "")
    fp.p.refresh_from_db()
    if com_q:
        incluir_produto_na_rodada(fp.admin, r2, fp.q, None)
    incluir_produto_na_rodada(fp.admin, r2, fp.p, None if limite_de_p is None else D(limite_de_p))
    return r2


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _parcela(conta: Conta, produto: Produto) -> ParcelaDeInteresse:
    return ParcelaDeInteresse.objects.exclude(situacao="removida").get(
        comprador=conta, produto=produto
    )


def _estado(conta: Conta, produto: Produto) -> tuple[str, Decimal, Decimal]:
    parcela = _parcela(conta, produto)
    return parcela.situacao, parcela.quantidade_reservada, parcela.quantidade_pendente


def _sequencias(produto: Produto) -> dict[int, int]:
    return {p.pk: p.sequencia for p in ParcelaDeInteresse.objects.filter(produto=produto)}


def _invariantes(fp: FP, limite: int | None) -> None:
    """Total reservado dentro do estoque; reservado + pendente dentro do original."""
    if limite is not None:
        assert total_reservado(fp.p) <= D(limite)
    for parcela in ParcelaDeInteresse.objects.all():
        assert parcela.quantidade_reservada + parcela.quantidade_pendente <= (
            parcela.quantidade_original
        )


def test_arranjo_fp_deixa_as_pendentes_reais_da_apuracao(
    relogio: RelogioControlado, sim: Any
) -> None:
    fp = montar_fp(relogio, sim)
    assert _estado(fp.a, fp.p) == ("pendente", D("0.000"), D("6.000"))
    assert _estado(fp.c, fp.p) == ("pendente", D("0.000"), D("8.000"))
    assert _parcela(fp.a, fp.p).sequencia < _parcela(fp.c, fp.p).sequencia
    assert Reembolso.objects.filter(motivo="caixa_invalidada").count() == 2


def test_inclusao_do_produto_atende_a_fila_pela_sequencia_original(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    fp = montar_fp(relogio, sim)
    antes = _sequencias(fp.p)
    abrir_r2(fp, 10)
    assert _estado(fp.a, fp.p) == ("ativa", D("6.000"), D("0.000"))
    assert _estado(fp.c, fp.p) == ("ativa", D("4.000"), D("4.000"))
    assert total_reservado(fp.p) == D("10.000")
    assert _sequencias(fp.p) == antes
    _invariantes(fp, 10)


def test_adicao_sem_estoque_e_recusada_e_o_aumento_atende_c_antes_de_d(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    fp = montar_fp(relogio, sim)
    r2 = abrir_r2(fp, 10)
    d = ContaFactory.create(nome="Comprador D")
    with pytest.raises(EstoqueInsuficiente):
        adicionar_interesse(d, fp.p, D("3"))
    assert not ParcelaDeInteresse.objects.filter(comprador=d).exists()
    estoque = EstoqueDaRodada.objects.get(rodada=r2, produto=fp.p)
    alterar_estoque(fp.admin, estoque, D("14"))
    assert _estado(fp.c, fp.p) == ("ativa", D("8.000"), D("0.000"))
    assert total_reservado(fp.p) == D("14.000")
    _invariantes(fp, 14)


def test_progresso_e_pedido_so_contam_as_reservadas(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-3
    fp = montar_fp(relogio, sim)
    r2 = abrir_r2(fp, 10, com_q=True)
    adicionar_interesse(fp.a, fp.q, D("10"))
    progresso = progresso_da_rodada(Rodada.objects.select_related("fornecedor").get(pk=r2.pk))
    assert progresso.valor_elegivel == D("200.00")  # P: 10 reservadas; Q: 10
    iniciar_fechamento(fp.admin, r2)
    relogio.congelar(T0 + 80 * H)
    encerrar_fechamento(r2)
    r2.refresh_from_db()
    abrir_pagamento(fp.admin, r2, D("10.00"))
    item = ItemDoPedido.objects.get(
        pedido__comprador=fp.c, produto=fp.p, pedido__abertura__rodada=r2
    )
    assert item.quantidade == D("4.000")
    parcela = _parcela(fp.c, fp.p)
    assert (parcela.situacao, parcela.quantidade_pendente) == ("pendente", D("4.000"))


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_inclusao_em_paralelo_com_adicao_de_e_atende_a_fila_primeiro(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-4
    from apps.interesses import receptores
    from tests.apoio.corrida import Corrida

    fp = montar_fp(relogio, simulador_pagamentos)
    r2 = abrir_rodada(fp.admin, fp.fornecedor)
    alterar_multiplo(fp.admin, fp.p, "")
    fp.p.refresh_from_db()
    e = ContaFactory.create(nome="Comprador E")
    corrida = Corrida()
    corrida.depois_de(monkeypatch, receptores, "_alocar_produto")
    ra, rb = corrida.rodar(
        lambda: incluir_produto_na_rodada(fp.admin, r2, fp.p, D("10")),
        lambda: adicionar_interesse(e, fp.p, D("5")),
    )
    assert ra.excecao is None, ra.excecao
    assert corrida.b_esperou
    assert isinstance(rb.excecao, EstoqueInsuficiente), rb.excecao
    assert _estado(fp.a, fp.p) == ("ativa", D("6.000"), D("0.000"))
    assert _estado(fp.c, fp.p) == ("ativa", D("4.000"), D("4.000"))
    assert not ParcelaDeInteresse.objects.filter(comprador=e).exists()
    assert total_reservado(fp.p) == D("10.000")


def test_alocar_de_novo_nao_muda_nada(relogio: RelogioControlado, sim: Any) -> None:  # A-5
    fp = montar_fp(relogio, sim)
    abrir_r2(fp, 10)
    antes = [
        (p.pk, p.situacao, p.quantidade_reservada, p.quantidade_pendente)
        for p in ParcelaDeInteresse.objects.order_by("pk")
    ]
    with transaction.atomic():
        alocar_pendentes(fp.fornecedor)
        alocar_pendentes(fp.fornecedor)
    depois = [
        (p.pk, p.situacao, p.quantidade_reservada, p.quantidade_pendente)
        for p in ParcelaDeInteresse.objects.order_by("pk")
    ]
    assert depois == antes
    assert total_reservado(fp.p) == D("10.000")


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def test_carrinho_separa_reservado_e_pendente_com_o_livre_zero(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    fp = montar_fp(relogio, sim)
    abrir_r2(fp, 10)
    cliente = Client()
    cliente.force_login(fp.c)
    texto = _texto(cliente.get("/carrinho/"))
    assert "Reservado: 4" in texto
    assert "Pendente: 4" in texto
    outro = Client()
    outro.force_login(fp.a)
    texto_de_a = _texto(outro.get("/carrinho/"))
    assert "Pendente: 4" not in texto_de_a
    assert "Reservado: 6" in texto_de_a


def test_remover_pendentes_nao_mexe_nas_reservas_nem_no_estorno(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    fp = montar_fp(relogio, sim)
    abrir_r2(fp, 10)
    sequencias = _sequencias(fp.p)
    estorno = list(
        Reembolso.objects.filter(pedido__comprador=fp.c).values_list(
            "chave", "produtos", "servico", "frete"
        )
    )
    obrigacao = list(
        ObrigacaoComComprador.objects.filter(comprador=fp.c).values_list(
            "pk", "produtos", "servico", "frete"
        )
    )
    remover_pendente(fp.c, fp.p, D("2"))
    assert _estado(fp.c, fp.p) == ("ativa", D("4.000"), D("2.000"))
    remover_pendente(fp.c, fp.p, D("2"))
    assert _estado(fp.c, fp.p) == ("ativa", D("4.000"), D("0.000"))
    assert _estado(fp.a, fp.p) == ("ativa", D("6.000"), D("0.000"))
    assert _sequencias(fp.p) == sequencias
    assert (
        list(
            Reembolso.objects.filter(pedido__comprador=fp.c).values_list(
                "chave", "produtos", "servico", "frete"
            )
        )
        == estorno
    )
    assert (
        list(
            ObrigacaoComComprador.objects.filter(comprador=fp.c).values_list(
                "pk", "produtos", "servico", "frete"
            )
        )
        == obrigacao
    )


def test_remocoes_invalidas_sao_recusadas_sem_escrita(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    fp = montar_fp(relogio, sim)
    abrir_r2(fp, 10)
    antes = _estado(fp.c, fp.p)
    with pytest.raises(RemocaoAcimaDoPendente):
        remover_pendente(fp.c, fp.p, D("5"))
    with pytest.raises(QuantidadeRecusada):
        remover_pendente(fp.c, fp.p, D("0.5"))
    assert _estado(fp.c, fp.p) == antes


def test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    fp = montar_fp(relogio, sim)
    item_de_a_em_q = ItemDoPedido.objects.get(pedido__comprador=fp.a, produto=fp.q)
    antes = (
        list(ItemDoPedido.objects.order_by("pk").values()),
        list(Reembolso.objects.order_by("pk").values()),
        _estado(fp.a, fp.q),
    )
    cliente = Client()
    cliente.force_login(fp.a)
    for produto_id in (item_de_a_em_q.pk + 10_000, fp.q.pk):
        resposta = cliente.post(
            "/interesses/pendentes/remover/", {"produto": produto_id, "quantidade": "1"}
        )
        assert resposta.status_code in (200, 404, 409)
    assert (
        list(ItemDoPedido.objects.order_by("pk").values()),
        list(Reembolso.objects.order_by("pk").values()),
        _estado(fp.a, fp.q),
    ) == antes


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_remocao_de_pendentes_em_paralelo_com_a_inclusao(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-10
    from apps.interesses import receptores
    from tests.apoio.corrida import Corrida

    fp = montar_fp(relogio, simulador_pagamentos)
    r2 = abrir_rodada(fp.admin, fp.fornecedor)
    alterar_multiplo(fp.admin, fp.p, "")
    fp.p.refresh_from_db()
    corrida = Corrida()
    corrida.depois_de(monkeypatch, receptores, "_alocar_produto")
    ra, rb = corrida.rodar(
        lambda: incluir_produto_na_rodada(fp.admin, r2, fp.p, D("10")),
        lambda: remover_pendente(fp.c, fp.p, D("4")),
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    reservado, pendente = _estado(fp.c, fp.p)[1:]
    assert reservado + pendente <= D("8.000")
    assert (reservado, pendente) == (D("4.000"), D("0.000"))
    assert total_reservado(fp.p) == D("10.000")


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_reducao_em_paralelo_com_adicao_atende_c_antes_de_e(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-11
    from apps.interesses import servicos
    from tests.apoio.corrida import Corrida

    fp = montar_fp(relogio, simulador_pagamentos)
    abrir_r2(fp, 10)
    e = ContaFactory.create(nome="Comprador E")
    corrida = Corrida()
    corrida.depois_de(monkeypatch, servicos, "_atender_a_fila")
    ra, rb = corrida.rodar(
        lambda: reduzir_interesse(fp.a, fp.p, D("3")),
        lambda: adicionar_interesse(e, fp.p, D("3")),
    )
    assert ra.excecao is None, ra.excecao
    assert corrida.b_esperou
    assert isinstance(rb.excecao, EstoqueInsuficiente), rb.excecao
    assert _estado(fp.c, fp.p) == ("ativa", D("7.000"), D("1.000"))
    assert not ParcelaDeInteresse.objects.filter(comprador=e).exists()
    assert total_reservado(fp.p) == D("10.000")


def test_outro_fornecedor_nao_recebe_as_pendentes_de_f(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    fp = montar_fp(relogio, sim)
    abrir_r2(fp, 4)
    g = FornecedorFactory.create(nome="G")
    rodada_g = RodadaFactory.create(fornecedor=g)
    produto_g = ProdutoFactory.create(fornecedor=g, nome="PG")
    EstoqueDaRodadaFactory.create(rodada=rodada_g, produto=produto_g, limite=D("50"))
    antes = _estado(fp.c, fp.p)
    with transaction.atomic():
        assert alocar_pendentes(g) == D("0.000")
    assert _estado(fp.c, fp.p) == antes


def test_pendentes_de_c_ficam_fora_do_progresso_e_do_fechamento(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-13
    fp = montar_fp(relogio, sim)
    r2 = abrir_rodada(fp.admin, fp.fornecedor)
    alterar_multiplo(fp.admin, fp.p, "")
    incluir_produto_na_rodada(fp.admin, r2, fp.p, D("6"))
    alterar_minimo(fp.admin, fp.fornecedor, D("100.00"))
    assert _estado(fp.a, fp.p) == ("ativa", D("6.000"), D("0.000"))
    assert _estado(fp.c, fp.p) == ("pendente", D("0.000"), D("8.000"))
    progresso = progresso_da_rodada(Rodada.objects.select_related("fornecedor").get(pk=r2.pk))
    assert progresso.valor_elegivel == D("60.00")
    with pytest.raises(TransicaoRecusada) as recusa:
        iniciar_fechamento(fp.admin, r2)
    assert recusa.value.codigo == "minimo_nao_atingido"
