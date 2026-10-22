"""Apoio dos testes do livro-razão (E09): o mundo de dois fornecedores e dois compradores, e
atalhos para as contas e para pôr saldo nelas por movimentos permitidos."""

import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from apps.contas.models import Conta
from apps.financeiro.livro import EXTERIOR, Transferencia, conta, lancar
from apps.financeiro.models import (
    Componente,
    ContaFinanceira,
    Despesa,
    Destinacao,
    ObrigacaoComComprador,
    TipoDeMovimento,
)
from apps.fornecedores.models import Fornecedor
from apps.nucleo.auditoria import SISTEMA
from apps.pagamentos.models import PagamentoNoProvedor
from apps.pedidos.models import AberturaDoPagamento, Pedido, SituacaoDoPedido
from apps.rodadas.models import Ciclo, Etapa, Rodada
from tests.apoio.ciclos import dar_prazo_de_teste
from tests.apoio.pedidos import T0, administrador
from tests.fabricas import ContaFactory, FornecedorFactory, RodadaFactory

D = Decimal


@dataclass
class Mundo:
    fa: Fornecedor
    fb: Fornecedor
    ra: Rodada
    rb: Rodada
    ca: Ciclo
    cb: Ciclo
    x: Conta
    y: Conta
    admin: Conta


def montar_mundo() -> Mundo:
    fa = FornecedorFactory.create(nome="Fornecedor A")
    fb = FornecedorFactory.create(nome="Fornecedor B")
    ra = RodadaFactory.create(fornecedor=fa, etapa=Etapa.FECHAMENTO_ENCERRADO)
    rb = RodadaFactory.create(fornecedor=fb, etapa=Etapa.FECHAMENTO_ENCERRADO)
    ca = dar_prazo_de_teste(ra).ciclo
    cb = dar_prazo_de_teste(rb).ciclo
    x = ContaFactory.create(nome="Comprador X")
    y = ContaFactory.create(nome="Comprador Y")
    return Mundo(fa, fb, ra, rb, ca, cb, x, y, administrador())


def chave_nova() -> str:
    return f"teste:{uuid.uuid4().hex}"


def custodia(
    rodada: Rodada, ciclo: Ciclo, comprador: Conta, componente: str = Componente.PRODUTOS
) -> ContaFinanceira:
    return conta(
        Destinacao.CUSTODIA,
        rodada=rodada,
        ciclo=ciclo,
        comprador=comprador,
        componente=componente,
    )


def obrigacao_com(
    rodada: Rodada, ciclo: Ciclo, comprador: Conta, numero: int = 1
) -> ContaFinanceira:
    return conta(
        Destinacao.OBRIGACAO_COMPRADOR,
        obrigacao=numero,
        rodada=rodada,
        ciclo=ciclo,
        comprador=comprador,
    )


def obrigacao_de(fornecedor: Fornecedor, rodada: Rodada) -> ContaFinanceira:
    return conta(Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=fornecedor, rodada=rodada)


def frete_de(rodada: Rodada) -> ContaFinanceira:
    return conta(Destinacao.FRETE, rodada=rodada)


def receita_de(rodada: Rodada) -> ContaFinanceira:
    return conta(Destinacao.RECEITA_SERVICO, rodada=rodada)


def reserva() -> ContaFinanceira:
    return conta(Destinacao.RESERVA)


def despesas() -> ContaFinanceira:
    return conta(Destinacao.DESPESAS_A_COBRIR)


def mover(
    tipo: str,
    de: Any,
    para: Any,
    valor: str | Decimal,
    *,
    autor: Any = SISTEMA,
    chave: str | None = None,
    origem: Any = None,
    justificativa: str = "teste",
) -> Any:
    """Um movimento de uma transferência só (dentro da transação do teste)."""
    return lancar(
        tipo=tipo,
        transferencias=[Transferencia(de, para, D(valor))],
        autor=autor,
        justificativa=justificativa,
        origem=origem if origem is not None else (de if de is not EXTERIOR else para),
        chave=chave or chave_nova(),
    )


def semear(m: Mundo, destino: ContaFinanceira, valor: str) -> None:
    """Põe `valor` na conta por movimentos permitidos, a partir do exterior."""
    d = destino.destinacao
    if d == Destinacao.CUSTODIA:
        mover(TipoDeMovimento.ENTRADA_DE_PAGAMENTO, EXTERIOR, destino, valor)
    elif d == Destinacao.OBRIGACAO_COMPRADOR:
        mover(TipoDeMovimento.ENTRADA_PARA_DEVOLUCAO, EXTERIOR, destino, valor)
    elif d == Destinacao.RESERVA:
        mover(TipoDeMovimento.APORTE, EXTERIOR, destino, valor)
    elif d in (Destinacao.RECEITA_SERVICO, Destinacao.FRETE, Destinacao.OBRIGACAO_FORNECEDOR):
        rodada = destino.rodada
        assert rodada is not None
        ciclo = m.ca if rodada.pk == m.ra.pk else m.cb
        componente = {
            Destinacao.RECEITA_SERVICO: Componente.SERVICO,
            Destinacao.FRETE: Componente.FRETE,
            Destinacao.OBRIGACAO_FORNECEDOR: Componente.PRODUTOS,
        }[Destinacao(d)]
        origem = custodia(rodada, ciclo, m.x, componente)
        mover(TipoDeMovimento.ENTRADA_DE_PAGAMENTO, EXTERIOR, origem, valor)
        mover(TipoDeMovimento.APURACAO, origem, destino, valor)
    else:
        raise AssertionError(f"destinação sem semeadura: {d}")


def pedido_composto(
    comprador: Conta, produtos: str = "100.00", servico: str = "5.00", frete: str = "20.00"
) -> Pedido:
    """Um pedido de `comprador` com os componentes dados, numa abertura nova (fornecedor e rodada
    próprios, etapa `pagamento`, `T0` como início), gravado direto."""
    fornecedor = FornecedorFactory.create()
    rodada = RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.PAGAMENTO)
    ciclo = dar_prazo_de_teste(rodada).ciclo
    valores = (D(produtos), D(servico), D(frete))
    abertura = AberturaDoPagamento.objects.create(
        ciclo=ciclo,
        rodada=rodada,
        t0=T0,
        frete=valores[2],
        total_produtos=valores[0],
        autor=administrador(),
    )
    pedido = Pedido.objects.create(
        abertura=abertura,
        comprador=comprador,
        produtos=valores[0],
        servico=valores[1],
        frete=valores[2],
        total=sum(valores, D("0.00")),
    )
    SituacaoDoPedido.objects.create(pedido=pedido, situacao="aguardando_pagamento")
    return pedido


_SEQUENCIA = iter(range(1, 1_000_000))


def obrigacao_de_teste(valor: str = "50.00") -> ObrigacaoComComprador:
    """Uma obrigação integral sem pedido e sem nenhum movimento de financiamento."""
    return ObrigacaoComComprador.objects.create(
        origem_tipo="teste",
        origem_id=str(next(_SEQUENCIA)),
        motivo="referencia_desconhecida",
        integral=D(valor),
    )


def despesa_de_tarifa(valor: str = "2.00", rodada: Rodada | None = None) -> Despesa:
    """Uma despesa de tarifa pendente, com o pagamento de apoio que ela exige."""
    numero = next(_SEQUENCIA)
    instante = T0
    pagamento = PagamentoNoProvedor.objects.create(
        provedor="simulador",
        ambiente="testes",
        id_externo=f"apoio-tarifa-{numero}",
        referencia_externa=f"apoio-{numero}",
        valor=D("100.00"),
        situacao="aprovado",
        criado_no_provedor_em=instante,
        expira_em=instante + timedelta(hours=24),
        aprovado_no_provedor_em=instante,
    )
    return Despesa.objects.create(tipo="tarifa", valor=D(valor), pagamento=pagamento, rodada=rodada)


@dataclass
class Apuracao:
    """O arranjo Ap da E09-06: a rodada `r` do fornecedor A, o ciclo `c` e a abertura com frete
    30,00, com o pedido X do comprador B (125,00) e o pedido Y do comprador D (62,50)."""

    fornecedor: Fornecedor
    rodada: Rodada
    ciclo: Ciclo
    abertura: AberturaDoPagamento
    x: Pedido
    y: Pedido
    b: Conta
    d: Conta
    admin: Conta


def montar_ap() -> Apuracao:
    fornecedor = FornecedorFactory.create(nome="Fornecedor A")
    rodada = RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.PAGAMENTO)
    ciclo = dar_prazo_de_teste(rodada).ciclo
    admin = administrador()
    abertura = AberturaDoPagamento.objects.create(
        ciclo=ciclo,
        rodada=rodada,
        t0=T0,
        frete=D("30.00"),
        total_produtos=D("150.00"),
        autor=admin,
    )
    b = ContaFactory.create(nome="Comprador B")
    d = ContaFactory.create(nome="Comprador D")
    pedidos = []
    for comprador, (produtos, servico, frete) in (
        (b, ("100.00", "5.00", "20.00")),
        (d, ("50.00", "2.50", "10.00")),
    ):
        valores = (D(produtos), D(servico), D(frete))
        pedido = Pedido.objects.create(
            abertura=abertura,
            comprador=comprador,
            produtos=valores[0],
            servico=valores[1],
            frete=valores[2],
            total=sum(valores, D("0.00")),
        )
        SituacaoDoPedido.objects.create(pedido=pedido, situacao="aguardando_pagamento")
        pedidos.append(pedido)
    return Apuracao(fornecedor, rodada, ciclo, abertura, pedidos[0], pedidos[1], b, d, admin)


def pagar_pedido(ap: Apuracao, pedido: Pedido, sim: Any, relogio: Any, quando: timedelta) -> str:
    """O pedido é pago: cobrança criada, aprovada em `T0 + quando` e sincronizada. Devolve o
    `id_externo`. A tarifa vem do plano que o teste definiu no simulador."""
    from tests.apoio.pedidos import sincronizar, tentativa_criada

    relogio.congelar(T0 + timedelta(hours=1))
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    relogio.congelar(T0 + quando)
    sim.aprovar(id_externo)
    sincronizar(id_externo)
    return id_externo


@dataclass
class Rodada1:
    """Uma rodada quitada e apurada: o fornecedor, a rodada, o ciclo, os pedidos e o comprador do
    primeiro."""

    fornecedor: Fornecedor
    rodada: Rodada
    ciclo: Ciclo
    pedido: Pedido
    comprador: Conta
    pedidos: list[Pedido]


@dataclass(frozen=True)
class ItemPago:
    produtos: str
    servico: str
    aprovado_em: Any
    liberacao_horas: int = 24


def pedidos_pagos_e_apurados(
    sim: Any, relogio: Any, *, nome: str, t0: Any, itens: list[ItemPago]
) -> Rodada1:
    """Uma rodada nova, aberta em `t0` (frete 0,00), com um pedido por item: cada um é pago
    (cobrança criada meia hora depois de `t0`, aprovada em `aprovado_em`, com a liberação do
    item) e todos são apurados juntos no livro. O relógio fica no último `aprovado_em`."""
    from django.db import transaction

    from apps.financeiro.apuracao import registrar_apuracao_no_livro
    from tests.apoio.pedidos import sincronizar, tentativa_criada

    fornecedor = FornecedorFactory.create(nome=nome)
    rodada = RodadaFactory.create(fornecedor=fornecedor, etapa=Etapa.PAGAMENTO)
    ciclo = dar_prazo_de_teste(rodada).ciclo
    abertura = AberturaDoPagamento.objects.create(
        ciclo=ciclo,
        rodada=rodada,
        t0=t0,
        frete=D("0.00"),
        total_produtos=sum((D(i.produtos) for i in itens), D("0.00")),
        autor=administrador(),
    )
    pedidos: list[Pedido] = []
    for numero, item in enumerate(itens, start=1):
        comprador = ContaFactory.create(nome=f"Comprador {nome}{numero}")
        valores = (D(item.produtos), D(item.servico), D("0.00"))
        pedido = Pedido.objects.create(
            abertura=abertura,
            comprador=comprador,
            produtos=valores[0],
            servico=valores[1],
            frete=valores[2],
            total=sum(valores, D("0.00")),
        )
        SituacaoDoPedido.objects.create(pedido=pedido, situacao="aguardando_pagamento")
        sim.definir_liberacao("pix", horas=item.liberacao_horas)
        relogio.congelar(t0 + timedelta(minutes=30))
        id_externo = tentativa_criada(pedido).id_externo
        assert id_externo is not None
        relogio.congelar(item.aprovado_em)
        sim.aprovar(id_externo)
        sincronizar(id_externo)
        pedidos.append(pedido)
    with transaction.atomic():
        registrar_apuracao_no_livro(ciclo, pedidos, autor=SISTEMA)
    return Rodada1(fornecedor, rodada, ciclo, pedidos[0], pedidos[0].comprador, pedidos)


def pedido_pago_e_apurado(
    sim: Any,
    relogio: Any,
    *,
    nome: str,
    t0: Any,
    produtos: str,
    servico: str,
    aprovado_em: Any,
    liberacao_horas: int = 24,
) -> Rodada1:
    """Uma rodada com um pedido só: ver `pedidos_pagos_e_apurados`."""
    item = ItemPago(produtos, servico, aprovado_em, liberacao_horas)
    return pedidos_pagos_e_apurados(sim, relogio, nome=nome, t0=t0, itens=[item])


def montar_l(sim: Any, relogio: Any) -> tuple[Rodada1, Rodada1]:
    """O arranjo L da E09-07: XA (100,00 + 5,00) em `rA`, aprovado às `T0 + 1h`, e XB (80,00 +
    4,00) em `rB`, aprovado às `T0 - 30h`, os dois quitados e apurados, com liberação em 24h e
    tarifa zero. O relógio fica em `T0 + 2h`: XB liberado, XA a liberar. Devolve (A, B)."""
    h = timedelta(hours=1)
    b = pedido_pago_e_apurado(
        sim,
        relogio,
        nome="B",
        t0=T0 - 48 * h,
        produtos="80.00",
        servico="4.00",
        aprovado_em=T0 - 30 * h,
    )
    a = pedido_pago_e_apurado(
        sim, relogio, nome="A", t0=T0, produtos="100.00", servico="5.00", aprovado_em=T0 + h
    )
    relogio.congelar(T0 + 2 * h)
    return a, b
