"""Apoio dos testes de pedidos (E08): o arranjo comum da abertura do pagamento.

Fornecedor F (mínimo R$ 100,00), rodada com o fechamento encerrado, `P1` a R$ 10,00 sem múltiplo
e `P2` a R$ 5,00 com múltiplo 6. O comprador A tem 6 de `P1` e 4 de `P2`; o comprador B tem 5 de
`P1` e 8 de `P2`, sendo 2 delas numa segunda parcela. A ordem das parcelas de `P2` é A com 4, B
com 6 e B com 2 (duas caixas). `pendente_a_p1` acrescenta pendentes à parcela de A em `P1`. O
relógio deve estar congelado antes de montar o arranjo.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.catalogo.models import Produto, Unidade
from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import PagamentoNoProvedor
from apps.pagamentos.provedor import obter_provedor
from apps.pagamentos.sincronizacao import sincronizar_pagamento
from apps.pedidos.abertura import ResultadoDaAbertura, abrir_pagamento
from apps.pedidos.models import AberturaDoPagamento, Pedido, SituacaoDoPedido, TentativaDePagamento
from apps.pedidos.pagamento import pedir_pagamento
from apps.rodadas.models import Ciclo, Etapa, Rodada
from tests.apoio.ciclos import dar_prazo_de_teste
from tests.conftest import RelogioControlado
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ParcelaFactory,
    ProdutoFactory,
    RodadaFactory,
)

D = Decimal
T0 = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)


@dataclass
class Arranjo:
    fornecedor: Fornecedor
    rodada: Rodada
    ciclo: Ciclo
    p1: Produto
    p2: Produto
    a: Conta
    b: Conta
    admin: Conta


def administrador() -> Conta:
    return Conta.objects.get(papel=Papel.ADMINISTRADOR)


def montar_arranjo(*, minimo: str = "100.00", pendente_a_p1: int = 0) -> Arranjo:
    fornecedor = FornecedorFactory.create(nome="F", minimo=D(minimo))
    rodada = RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.FECHAMENTO_ENCERRADO)
    ciclo = dar_prazo_de_teste(rodada).ciclo
    p1 = ProdutoFactory.create(
        fornecedor=fornecedor, nome="P1", unidade=Unidade.UNIDADE, preco=D("10.00")
    )
    p2 = ProdutoFactory.create(
        fornecedor=fornecedor,
        nome="P2",
        unidade=Unidade.UNIDADE,
        preco=D("5.00"),
        multiplo=D("6.000"),
    )
    for produto in (p1, p2):
        EstoqueDaRodadaFactory.create(rodada=rodada, produto=produto, limite=None)
    a = ContaFactory.create(nome="Comprador A")
    b = ContaFactory.create(nome="Comprador B")
    for comprador, produto, quantidade in (
        (a, p1, 6),
        (b, p1, 5),
        (a, p2, 4),
        (b, p2, 6),
        (b, p2, 2),
    ):
        pendente = pendente_a_p1 if (comprador, produto) == (a, p1) else 0
        ParcelaFactory.create(
            comprador=comprador,
            produto=produto,
            quantidade_original=D(quantidade + pendente),
            quantidade_reservada=D(quantidade),
            quantidade_pendente=D(pendente),
        )
    return Arranjo(fornecedor, rodada, ciclo, p1, p2, a, b, administrador())


def abrir(arranjo: Arranjo, frete: str = "22.00") -> ResultadoDaAbertura:
    return abrir_pagamento(arranjo.admin, arranjo.rodada, D(frete))


def pedido_de(comprador: Conta) -> Pedido:
    pedidos: list[Pedido] = list(Pedido.objects.filter(comprador=comprador))
    assert len(pedidos) == 1, f"pedidos do comprador: {len(pedidos)}"
    return pedidos[0]


def abertura_unica() -> AberturaDoPagamento:
    aberturas: list[AberturaDoPagamento] = list(AberturaDoPagamento.objects.all())
    assert len(aberturas) == 1, f"aberturas: {len(aberturas)}"
    return aberturas[0]


def pedido_aberto(relogio: RelogioControlado, frete: str = "22.00") -> tuple[Arranjo, Pedido]:
    """O arranjo com o pagamento aberto em `T0`; o relógio fica em `T0 + 1h` (14:00 UTC).
    Devolve o arranjo e o pedido `X` do comprador A (total R$ 94,35)."""
    relogio.congelar(T0)
    arranjo = montar_arranjo()
    abrir(arranjo, frete)
    relogio.congelar(T0 + timedelta(hours=1))
    return arranjo, pedido_de(arranjo.a)


def marcar_pago(pedido: Pedido, quando: datetime | None = None) -> PagamentoNoProvedor:
    """Põe o pedido em `pago` direto no banco, com um pagamento aprovado de apoio."""
    instante = quando or T0 + timedelta(hours=2)
    pagamento = PagamentoNoProvedor.objects.create(
        provedor="simulador",
        ambiente="testes",
        id_externo=f"apoio-{pedido.pk}",
        referencia_externa=pedido.referencia_externa,
        valor=pedido.total,
        situacao="aprovado",
        criado_no_provedor_em=instante,
        expira_em=instante + timedelta(hours=24),
        aprovado_no_provedor_em=instante,
    )
    SituacaoDoPedido.objects.filter(pedido=pedido).update(
        situacao="pago", quitado_por=pagamento, quitado_em=instante
    )
    return pagamento


def cancelar_direto(
    pedido: Pedido, motivo: str = "suspensao", quando: datetime | None = None
) -> None:
    """Põe o pedido em `cancelado` direto no banco."""
    SituacaoDoPedido.objects.filter(pedido=pedido).update(
        situacao="cancelado",
        cancelado_em=quando or T0 + timedelta(hours=2),
        motivo_do_cancelamento=motivo,
    )


def pedido_avulso(comprador: Conta, nome: str = "G", total: str = "50.00") -> Pedido:
    """Um pedido de `comprador` numa abertura de outro fornecedor, gravado direto."""
    fornecedor = FornecedorFactory.create(nome=nome)
    rodada = RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.PAGAMENTO)
    ciclo = dar_prazo_de_teste(rodada).ciclo
    valor = D(total)
    abertura = AberturaDoPagamento.objects.create(
        ciclo=ciclo,
        rodada=rodada,
        t0=T0,
        frete=D("0.00"),
        total_produtos=valor,
        autor=administrador(),
    )
    pedido = Pedido.objects.create(
        abertura=abertura,
        comprador=comprador,
        produtos=valor,
        servico=D("0.00"),
        frete=D("0.00"),
        total=valor,
    )
    SituacaoDoPedido.objects.create(pedido=pedido, situacao="aguardando_pagamento")
    return pedido


def tentativa_criada(pedido: Pedido) -> TentativaDePagamento:
    """O comprador pede para pagar e a tarefa cria a cobrança (no relógio corrente)."""
    pedir_pagamento(pedido.comprador, pedido)
    processar_chamadas()
    tentativa = TentativaDePagamento.objects.filter(pedido=pedido).order_by("-numero").first()
    assert tentativa is not None
    assert tentativa.situacao == "criada", tentativa.situacao
    return tentativa


def sincronizar(id_externo: str, origem: str = "tarefa") -> None:
    """Consulta o pagamento no provedor e o sincroniza, numa transação."""
    with transaction.atomic():
        sincronizar_pagamento(obter_provedor().consultar_pagamento(id_externo), origem=origem)


def pedido_na_abertura(
    abertura: AberturaDoPagamento, comprador: Conta, total: str = "50.00"
) -> Pedido:
    """Mais um pedido de `comprador` na mesma abertura, gravado direto."""
    valor = D(total)
    pedido = Pedido.objects.create(
        abertura=abertura,
        comprador=comprador,
        produtos=valor,
        servico=D("0.00"),
        frete=D("0.00"),
        total=valor,
    )
    SituacaoDoPedido.objects.create(pedido=pedido, situacao="aguardando_pagamento")
    return pedido


def recuperacao_de_dois_pagamentos(
    relogio: RelogioControlado, sim: Any
) -> tuple[Arranjo, Pedido, TentativaDePagamento, TentativaDePagamento, TentativaDePagamento]:
    """O arranjo R da correção E08-R08: duas tentativas expiradas e sincronizadas, uma terceira só
    `solicitada`, as duas cobranças aprovadas no simulador sem sincronizar, e o relógio em
    `T0 + 25h`, dentro da margem. Devolve (arranjo, pedido, primeira, segunda, terceira)."""
    arranjo, pedido = pedido_aberto(relogio)
    primeira = tentativa_criada(pedido)
    assert primeira.id_externo is not None
    sim.expirar(primeira.id_externo)
    sincronizar(primeira.id_externo)
    relogio.congelar(T0 + timedelta(hours=2))
    segunda = tentativa_criada(pedido)
    assert segunda.id_externo is not None
    sim.expirar(segunda.id_externo)
    sincronizar(segunda.id_externo)
    terceira = pedir_pagamento(arranjo.a, pedido)
    relogio.congelar(T0 + timedelta(hours=3))
    sim.aprovar(primeira.id_externo)
    sim.aprovar(segunda.id_externo)
    relogio.congelar(T0 + timedelta(hours=25))
    return arranjo, pedido, primeira, segunda, terceira
