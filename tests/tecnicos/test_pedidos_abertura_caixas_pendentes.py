"""T-47 pela abertura do pagamento (E16-07 regra 2-J): a formação de caixas ignora a quantidade
pendente. Produto de múltiplo 10 a R$ 10,00: A reserva 8, B reserva 7 (15 reservadas: uma caixa e
sobram 5) e C tem 5 pendentes sem reserva (as 15 + 5 completariam uma segunda caixa se contassem).
A abertura forma uma caixa só, a sobra de 5 sai da reserva de B e as pendentes de C seguem na
fila. O C104 usa o mesmo preço, sem múltiplo, no segundo teste."""

from decimal import Decimal

import pytest

from apps.catalogo.models import Produto
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.pedidos.models import ItemDoPedido, ParcelaNoPedido, Pedido
from apps.rodadas.models import Etapa, Rodada
from tests.apoio.pedidos import T0, abrir, montar_arranjo
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, ParcelaFactory

pytestmark = pytest.mark.django_db

D = Decimal


def test_a_formacao_de_caixas_pela_abertura_ignora_as_pendentes(
    relogio: RelogioControlado,
) -> None:  # T-47
    relogio.congelar(T0)
    arranjo = montar_arranjo(
        minimo="100.00", parcelas_de_p1=(("a", 8), ("b", 7)), parcelas_de_p2=()
    )
    Produto.objects.filter(pk=arranjo.p1.pk).update(multiplo=D("10.000"))
    c = ContaFactory.create(nome="Comprador C")
    parcela_de_c = ParcelaFactory.create(
        comprador=c,
        produto=arranjo.p1,
        quantidade_original=D("5"),
        quantidade_reservada=D("0"),
        quantidade_pendente=D("5"),
        situacao=SituacaoParcela.PENDENTE,
    )
    parcela_de_b = ParcelaDeInteresse.objects.get(comprador=arranjo.b, produto=arranjo.p1)

    resultado = abrir(arranjo)

    assert resultado.etapa_final == Etapa.PAGAMENTO
    assert Rodada.objects.get(pk=arranjo.rodada.pk).etapa == Etapa.PAGAMENTO
    linhas = list(
        ParcelaNoPedido.objects.order_by("pk").values_list(
            "item__pedido__comprador", "caixa", "quantidade"
        )
    )
    assert linhas == [(arranjo.a.pk, 1, D("8.000")), (arranjo.b.pk, 1, D("2.000"))]
    assert {caixa for _, caixa, _ in linhas} == {1}
    assert sum((quantidade for _, _, quantidade in linhas), D("0")) == D("10.000")
    assert ItemDoPedido.objects.get(pedido__comprador=arranjo.a).multiplo == D("10.000")
    assert (
        ItemDoPedido.objects.get(pedido__comprador=arranjo.b).quantidade,
        ItemDoPedido.objects.get(pedido__comprador=arranjo.a).quantidade,
    ) == (D("2.000"), D("8.000"))
    assert not Pedido.objects.filter(comprador=c).exists()
    assert not ParcelaNoPedido.objects.filter(parcela=parcela_de_c).exists()
    parcela_de_b.refresh_from_db()
    assert (parcela_de_b.situacao, parcela_de_b.quantidade_reservada) == (
        SituacaoParcela.EM_PEDIDO,
        D("2.000"),
    )
    assert parcela_de_b.quantidade_pendente == D("0.000")  # a sobra de 5 sai sem virar pendência
    parcela_de_c.refresh_from_db()
    assert (
        parcela_de_c.situacao,
        parcela_de_c.quantidade_reservada,
        parcela_de_c.quantidade_pendente,
    ) == (SituacaoParcela.PENDENTE, D("0.000"), D("5.000"))


def test_cenario_104_as_pendentes_de_c_nao_entram_em_pedido_nem_em_cobranca(
    relogio: RelogioControlado,
) -> None:  # C104, E16-07 regra 2-J
    """Produto de R$ 10,00 e mínimo de R$ 100,00: A com 8 reservadas e C com 5 pendentes sem
    reserva (elegível 80,00 só com as de A). A rodada chega ao pagamento porque B reserva 6 de
    outro produto (P2, R$ 5,00), sem converter as pendentes de C."""
    relogio.congelar(T0)
    arranjo = montar_arranjo(
        minimo="100.00", parcelas_de_p1=(("a", 8),), parcelas_de_p2=(("b", 6),)
    )
    c = ContaFactory.create(nome="Comprador C")
    parcela_de_c = ParcelaFactory.create(
        comprador=c,
        produto=arranjo.p1,
        quantidade_original=D("5"),
        quantidade_reservada=D("0"),
        quantidade_pendente=D("5"),
        situacao=SituacaoParcela.PENDENTE,
    )
    assert (arranjo.p1.preco, arranjo.fornecedor.minimo) == (D("10.00"), D("100.00"))

    resultado = abrir(arranjo)

    assert resultado.etapa_final == Etapa.PAGAMENTO
    assert not Pedido.objects.filter(comprador=c).exists()
    assert not ParcelaNoPedido.objects.filter(parcela=parcela_de_c).exists()
    assert not ItemDoPedido.objects.filter(pedido__comprador=c).exists()
    do_a = Pedido.objects.get(comprador=arranjo.a)
    do_b = Pedido.objects.get(comprador=arranjo.b)
    assert (do_a.produtos, do_b.produtos) == (D("80.00"), D("30.00"))
    assert resultado.abertura is not None
    assert resultado.abertura.total_produtos == D("110.00")  # sem os 50,00 das pendentes de C
    assert sorted(Pedido.objects.values_list("comprador", flat=True)) == sorted(
        [arranjo.a.pk, arranjo.b.pk]
    )
    parcela_de_c.refresh_from_db()
    assert (
        parcela_de_c.situacao,
        parcela_de_c.quantidade_reservada,
        parcela_de_c.quantidade_pendente,
    ) == (SituacaoParcela.PENDENTE, D("0.000"), D("5.000"))
