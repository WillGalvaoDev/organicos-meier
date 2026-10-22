"""O invariante do saldo do provedor (E09-07).

O saldo do provedor tem de cobrir o dinheiro de terceiros: a custódia, as obrigações com
fornecedores, o frete arrecadado e as obrigações com compradores. Com a diferença negativa, abre
o alerta crítico `invariante_violado` (que bloqueia as utilizações da reserva e as retiradas de
receita); quando o invariante volta a valer, o alerta é resolvido.

O saldo vem de `consultar_saldo()`, fora de transação. Como ele pode não ser em tempo real (no
Mercado Pago vem de relatórios), o livro-razão é lido só até o `referente_a` desse saldo.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Case, DecimalField, Sum, Value, When

from apps.financeiro.alertas import abrir_alerta, resolver_alerta
from apps.financeiro.livro import OrdemDeTravasViolada, conta, travar_contas
from apps.financeiro.models import Destinacao, TipoDeAlerta, TransferenciaFinanceira
from apps.financeiro.reserva import avaliar_reserva
from apps.pagamentos.provedor import ProvedorIndisponivel, RecusaDoProvedor, obter_provedor

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")
DESTINACOES_DE_TERCEIROS = (
    Destinacao.CUSTODIA,
    Destinacao.OBRIGACAO_FORNECEDOR,
    Destinacao.FRETE,
    Destinacao.OBRIGACAO_COMPRADOR,
)


@dataclass(frozen=True)
class ResultadoDoInvariante:
    saldo_do_provedor: Decimal
    obrigacoes_de_terceiros: Decimal
    diferenca: Decimal


def obrigacoes_de_terceiros(ate: object) -> Decimal:
    """A soma dos saldos das contas de terceiros, só com os movimentos até o instante `ate`,
    lida numa única consulta."""
    campo: DecimalField[Decimal, Decimal] = DecimalField(max_digits=14, decimal_places=2)
    zero = Value(Decimal("0.00"), output_field=campo)
    total = TransferenciaFinanceira.objects.filter(movimento__momento__lte=ate).aggregate(
        entrou=Sum(
            Case(When(para__destinacao__in=DESTINACOES_DE_TERCEIROS, then="valor"), default=zero)
        ),
        saiu=Sum(
            Case(When(de__destinacao__in=DESTINACOES_DE_TERCEIROS, then="valor"), default=zero)
        ),
    )
    return (total["entrou"] or ZERO) - (total["saiu"] or ZERO)


def _avaliar_a_reserva() -> None:
    """Abre ou resolve o alerta `reserva_insuficiente` numa transação própria (E09-R05): algumas
    despesas nascem sem nenhuma operação da reserva depois delas. Trava a `reserva` (regra única de
    travas). Uma falha aqui não desfaz o passo do invariante, e vice-versa."""
    try:
        with transaction.atomic():
            travar_contas(conta(Destinacao.RESERVA))
            avaliar_reserva()
    except OrdemDeTravasViolada:
        raise  # erro de programação: nunca engolido
    except Exception:
        logger.exception("Reserva não avaliada na tarefa do invariante")


def verificar_invariante_agora() -> ResultadoDoInvariante | None:
    """Compara o saldo do provedor com o dinheiro de terceiros; abre ou resolve o alerta. Com o
    provedor indisponível, devolve `None`, registra um aviso e deixa os alertas como estavam."""
    try:
        saldo_do_provedor = obter_provedor().consultar_saldo()
    except (ProvedorIndisponivel, RecusaDoProvedor) as erro:
        logger.warning("Invariante não verificado: provedor sem saldo (%s)", type(erro).__name__)
        _avaliar_a_reserva()  # usa só o livro-razão: vale também com o provedor fora do ar
        return None
    total = saldo_do_provedor.liberado + saldo_do_provedor.a_liberar
    terceiros = obrigacoes_de_terceiros(saldo_do_provedor.referente_a)
    diferenca = total - terceiros
    with transaction.atomic():
        if diferenca < 0:
            abrir_alerta(
                TipoDeAlerta.INVARIANTE_VIOLADO,
                "geral",
                {
                    "diferenca": diferenca,
                    "saldo_do_provedor": total,
                    "obrigacoes_de_terceiros": terceiros,
                },
            )
        else:
            resolver_alerta(
                TipoDeAlerta.INVARIANTE_VIOLADO, "geral", motivo="invariante restabelecido"
            )
    _avaliar_a_reserva()
    return ResultadoDoInvariante(total, terceiros, diferenca)
