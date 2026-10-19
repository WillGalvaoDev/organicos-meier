"""Interface do provedor de pagamentos (E07-01).

O sistema fala com o provedor só por aqui. Na fase 1 o único provedor é o simulador; o Mercado
Pago entra na fase 2a como outra implementação do mesmo protocolo. As situações e os campos são
do vocabulário interno: quem implementa traduz o que o provedor responde, inclusive os horários
para UTC (L-4). Nenhum método escreve em tabelas deste app, e nenhuma mensagem de erro leva dado
pessoal nem o corpo de um aviso.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from apps.nucleo.tempo import somar_horas
from apps.nucleo.valores import ValorInvalido, dinheiro

TAMANHO_MAXIMO_DA_CHAVE = 64
TAMANHO_MAXIMO_DA_DESCRICAO = 120


class SituacaoNoProvedor(StrEnum):
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    RECUSADO = "recusado"
    CANCELADO = "cancelado"
    EXPIRADO = "expirado"


@dataclass(frozen=True)
class NovaCobranca:
    chave_idempotencia: str
    referencia_externa: str
    valor: Decimal
    descricao: str
    expira_em: datetime
    meio: str = "pix"

    def __post_init__(self) -> None:
        """A validação local recusa com `ValueError` antes de chamar o provedor."""
        if not 1 <= len(self.chave_idempotencia) <= TAMANHO_MAXIMO_DA_CHAVE:
            raise ValueError("chave de idempotência deve ter de 1 a 64 caracteres")
        if not 1 <= len(self.referencia_externa) <= TAMANHO_MAXIMO_DA_CHAVE:
            raise ValueError("referência externa deve ter de 1 a 64 caracteres")
        if len(self.descricao) > TAMANHO_MAXIMO_DA_DESCRICAO:
            raise ValueError("descrição deve ter até 120 caracteres")
        try:
            valor = dinheiro(self.valor)  # recusa float e mais de duas casas
        except ValorInvalido as erro:
            raise ValueError(f"valor inválido: {erro}") from None
        if valor <= 0:
            raise ValueError("valor deve ser maior que zero")
        object.__setattr__(self, "valor", valor)
        somar_horas(self.expira_em, 0)  # InstanteSemFuso se não tiver fuso
        if self.meio != "pix":
            raise ValueError("na fase 1 o único meio é pix")


@dataclass(frozen=True)
class PagamentoConsultado:
    provedor: str
    id_externo: str
    referencia_externa: str
    valor: Decimal
    situacao: SituacaoNoProvedor
    criado_em: datetime
    aprovado_em: datetime | None
    expira_em: datetime
    consultado_em: datetime


@dataclass(frozen=True)
class CobrancaCriada:
    pagamento: PagamentoConsultado
    dados_para_pagar: dict[str, str]


@dataclass(frozen=True)
class AvisoDoProvedor:
    id_evento: str
    tipo: str
    id_externo: str


class ProvedorIndisponivel(Exception):
    """Rede, tempo esgotado ou erro interno do provedor: pode tentar de novo com a mesma chave."""


class RecusaDoProvedor(Exception):
    """O provedor recusou o pedido (definitiva). `codigo` diz o motivo."""

    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo


class PagamentoNaoEncontrado(Exception):
    """O identificador não existe no provedor; pode ser atraso de consistência (L-6)."""


class AvisoInvalido(Exception):
    """Assinatura ausente ou errada, ou corpo malformado: o aviso é descartado."""


class Provedor(Protocol):
    nome: str

    def criar_cobranca(self, nova: NovaCobranca) -> CobrancaCriada: ...

    def consultar_pagamento(self, id_externo: str) -> PagamentoConsultado: ...

    def buscar_por_referencia(self, referencia_externa: str) -> list[PagamentoConsultado]: ...

    def cancelar_cobranca(self, id_externo: str) -> PagamentoConsultado: ...

    def verificar_aviso(self, corpo: bytes, cabecalhos: Mapping[str, str]) -> AvisoDoProvedor: ...


def obter_provedor() -> Provedor:
    """A implementação configurada; quem usa o provedor nunca importa uma delas."""
    from apps.simulador_pagamentos.provedor import SIMULADO

    return SIMULADO
