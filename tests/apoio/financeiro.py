"""Apoio dos testes do livro-razão (E09): o mundo de dois fornecedores e dois compradores, e
atalhos para as contas e para pôr saldo nelas por movimentos permitidos."""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from apps.contas.models import Conta
from apps.financeiro.livro import EXTERIOR, Transferencia, conta, lancar
from apps.financeiro.models import (
    Componente,
    ContaFinanceira,
    Destinacao,
    TipoDeMovimento,
)
from apps.fornecedores.models import Fornecedor
from apps.nucleo.auditoria import SISTEMA
from apps.rodadas.models import Ciclo, Etapa, Rodada
from tests.apoio.ciclos import dar_prazo_de_teste
from tests.apoio.pedidos import administrador
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
