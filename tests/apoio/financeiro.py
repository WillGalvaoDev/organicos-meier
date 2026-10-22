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
