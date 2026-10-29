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

LIMITE_ID_EVENTO = 64
LIMITE_TIPO = 40
LIMITE_ID_EXTERNO = 64
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
    # `None` é "o provedor não informou", nunca zero: sem `liberado_em` o valor está a liberar.
    tarifa: Decimal | None = None
    liberado_em: datetime | None = None

    def __post_init__(self) -> None:
        """Todos os instantes em UTC, com fuso, qualquer que seja o caminho da resposta (R04).
        O instante é o mesmo; muda só a representação. Sem fuso: `InstanteSemFuso`."""
        for campo in ("criado_em", "aprovado_em", "expira_em", "consultado_em", "liberado_em"):
            instante = getattr(self, campo)
            if instante is not None:
                object.__setattr__(self, campo, somar_horas(instante, 0))


@dataclass(frozen=True)
class CobrancaCriada:
    pagamento: PagamentoConsultado
    dados_para_pagar: dict[str, str]


@dataclass(frozen=True)
class AvisoDoProvedor:
    id_evento: str
    tipo: str
    id_externo: str

    def __post_init__(self) -> None:
        """O esquema do aviso, para qualquer implementação do provedor (R05): textos não vazios,
        sem o caractere nulo e dentro dos limites das colunas de `AvisoRecebido`."""
        limites = (
            ("id_evento", LIMITE_ID_EVENTO),
            ("tipo", LIMITE_TIPO),
            ("id_externo", LIMITE_ID_EXTERNO),
        )
        for campo, limite in limites:
            valor = getattr(self, campo)
            if not isinstance(valor, str) or not 1 <= len(valor) <= limite or "\x00" in valor:
                raise AvisoInvalido("corpo malformado")


class TipoDeMovimentoNoProvedor(StrEnum):
    PAGAMENTO = "pagamento"
    TARIFA = "tarifa"
    DEPOSITO = "deposito"
    SAIDA = "saida"
    DEVOLUCAO = "devolucao"
    AJUSTE = "ajuste"
    OUTRO = "outro"


@dataclass(frozen=True)
class SaldoNoProvedor:
    """O saldo da conta no provedor. `referente_a` é o instante a que ele se refere: pode ser
    anterior a `consultado_em`, porque o provedor real o monta de relatórios assíncronos (L-9)."""

    liberado: Decimal
    a_liberar: Decimal
    referente_a: datetime
    consultado_em: datetime

    def __post_init__(self) -> None:
        for campo in ("referente_a", "consultado_em"):
            object.__setattr__(self, campo, somar_horas(getattr(self, campo), 0))


@dataclass(frozen=True)
class MovimentoNoProvedor:
    id_movimento: str
    tipo: TipoDeMovimentoNoProvedor
    descricao_no_provedor: str  # o rótulo original do provedor, até 50 caracteres
    valor: Decimal  # com sinal, nunca zero
    id_externo: str | None  # o pagamento, só em `pagamento`, `tarifa` e `devolucao`
    ocorrido_em: datetime
    liberado_em: datetime | None

    def __post_init__(self) -> None:
        for campo in ("ocorrido_em", "liberado_em"):
            instante = getattr(self, campo)
            if instante is not None:
                object.__setattr__(self, campo, somar_horas(instante, 0))


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

    def verificar_aviso(
        self, corpo: bytes, cabecalhos: Mapping[str, str], parametros: Mapping[str, str]
    ) -> AvisoDoProvedor:
        """`parametros` é a query string da URL: a assinatura do Mercado Pago a inclui (L-11)."""
        ...

    def consultar_saldo(self) -> SaldoNoProvedor: ...

    def listar_movimentos(self, desde: datetime, ate: datetime) -> list[MovimentoNoProvedor]: ...


def obter_provedor() -> Provedor:
    """A implementação configurada; quem usa o provedor nunca importa uma delas.

    Segunda barreira, além do carregamento das configurações: cobre configurações alteradas
    depois (`override_settings`), recusando o simulador em produção (E07-02).
    """
    from django.conf import settings
    from django.core.exceptions import ImproperlyConfigured

    from apps.simulador_pagamentos.provedor import SIMULADO

    if settings.AMBIENTE == "producao":
        raise ImproperlyConfigured("O simulador de pagamentos não pode ser usado em produção.")

    return SIMULADO
