"""O repasse ao fornecedor e o pagamento do frete (E13-06).

A transferência ao fornecedor é manual: o administrador paga fora do sistema e registra aqui. O
repasse só baixa a obrigação com aquele fornecedor naquela rodada e fica limitado à parte
liberada dela no provedor (infraestrutura 3.4, T-11). A consulta ao provedor vem antes do
repasse, fora de transação e sem trava (infraestrutura 4.2); o que ela sincronizar já vale para o
limite. O pagamento do frete não consulta e fica limitado ao liberado do frete.
"""

from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.contas.models import Conta, Papel, Situacao
from apps.financeiro.liquidez import liquidez, registrar_saida
from apps.financeiro.livro import conta, travar_contas
from apps.financeiro.models import (
    ApuracaoNoLivro,
    ContaFinanceira,
    Destinacao,
    MovimentoFinanceiro,
    PedidoApurado,
)
from apps.nucleo.auditoria import registrar_auditoria
from apps.pagamentos.consulta import consultar_antes_de_decidir, exigir_fora_de_transacao
from apps.pedidos.models import Pedido
from apps.rodadas.models import Rodada

__all__ = [
    "RepasseRecusado",
    "consultar_antes_de_decidir",
    "registrar_pagamento_do_frete",
    "registrar_repasse",
    "registrar_saida",
]

SEM_REPASSE = "A rodada não tem valores devidos ao fornecedor."
SEM_FRETE = "A rodada não tem frete apurado."


class RepasseRecusado(Exception):
    """A saída não pode ser registrada. `codigo` diz o motivo; a mensagem é a da tela."""

    def __init__(self, codigo: str, mensagem: str) -> None:
        self.codigo = codigo
        super().__init__(mensagem)


def _exigir_administrador(autor: Conta | None) -> Conta:
    if autor is None or autor.papel != Papel.ADMINISTRADOR or autor.situacao != Situacao.ATIVA:
        raise PermissionDenied
    return autor


def _exigir_apuracao(rodada: Rodada, mensagem: str) -> None:
    if not ApuracaoNoLivro.objects.filter(ciclo__rodada=rodada).exists():
        raise RepasseRecusado("sem_obrigacao", mensagem)


def _pedidos_validos(rodada: Rodada) -> list[Pedido]:
    validos = PedidoApurado.objects.filter(apuracao__ciclo__rodada=rodada).values("pedido_id")
    return list(Pedido.objects.filter(pk__in=validos).select_related("abertura").order_by("pk"))


def _registrar(
    autor: Conta,
    rodada: Rodada,
    *,
    tipo: str,
    origem: ContaFinanceira,
    acao: str,
    valor: Decimal,
    identificacao: str,
    justificativa: str,
) -> MovimentoFinanceiro:
    with transaction.atomic():
        travar_contas(origem)
        parte = liquidez(origem)  # lido sob a trava, como o limite do registro
        movimento = registrar_saida(
            autor,
            tipo=tipo,
            conta=origem,
            valor=valor,
            identificacao=identificacao,
            justificativa=justificativa,
        )
        registrar_auditoria(
            autor,
            acao,
            rodada,
            {
                "rodada": rodada.pk,
                "fornecedor": rodada.fornecedor_id,
                "valor": str(valor),
                "identificacao": identificacao,
                "liberado": str(parte.liberado),
                "a_liberar": str(parte.a_liberar),
            },
        )
        return movimento


def registrar_repasse(
    autor: Conta | None,
    rodada: Rodada,
    *,
    valor: Decimal,
    identificacao: str,
    justificativa: str,
) -> MovimentoFinanceiro:
    """Registra o repasse manual ao fornecedor da rodada. Só o administrador ativo
    (`PermissionDenied`) e fora de transação (`RuntimeError`): a consulta ao provedor vem antes e,
    se falhar, bloqueia o registro (`ConsultaAoProvedorFalhou`)."""
    administrador = _exigir_administrador(autor)
    exigir_fora_de_transacao()
    _exigir_apuracao(rodada, SEM_REPASSE)
    for pedido in _pedidos_validos(rodada):
        consultar_antes_de_decidir(pedido.referencia_externa)
    obrigacao = conta(
        Destinacao.OBRIGACAO_FORNECEDOR, fornecedor=rodada.fornecedor_id, rodada=rodada.pk
    )
    return _registrar(
        administrador,
        rodada,
        tipo="repasse",
        origem=obrigacao,
        acao="rodada.repasse",
        valor=valor,
        identificacao=identificacao,
        justificativa=justificativa,
    )


def registrar_pagamento_do_frete(
    autor: Conta | None,
    rodada: Rodada,
    *,
    valor: Decimal,
    identificacao: str,
    justificativa: str,
) -> MovimentoFinanceiro:
    """Registra o pagamento do frete da rodada, limitado ao liberado do frete. Não consulta o
    provedor: não está entre as decisões da infraestrutura 4.2."""
    administrador = _exigir_administrador(autor)
    _exigir_apuracao(rodada, SEM_FRETE)
    return _registrar(
        administrador,
        rodada,
        tipo="pagamento_do_frete",
        origem=conta(Destinacao.FRETE, rodada=rodada.pk),
        acao="rodada.pagamento_do_frete",
        valor=valor,
        identificacao=identificacao,
        justificativa=justificativa,
    )
