"""Cancelamento da rodada pelo administrador (E12).

O administrador cancela a rodada inteira por decisão própria, sem motivo, indicando se existe
reembolso devido (§7, §7.2, 17.2). Esta fatia (E12-01) entrega o registro, as recusas, as travas e
o efeito nos interesses; as seguintes acrescentam os pedidos, o reembolso e o aviso.

Ordem das travas: a mesma da apuração (E11, com a correção E11-R04, `FOR NO KEY UPDATE`): as contas
dos compradores envolvidos, o fornecedor, a rodada, os produtos do fornecedor, os estoques da
rodada e as parcelas não removidas. O cancelamento concorre com a apuração, as operações de
interesse, a moderação e o encerramento do fechamento, e essa ordem evita impasse com eles.
"""

from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.contas.models import Conta, Papel, Situacao
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora
from apps.pagamentos.consulta import exigir_fora_de_transacao
from apps.pedidos.apuracao import _travar
from apps.pedidos.models import CancelamentoDaRodada
from apps.rodadas.models import Etapa, Rodada

MAIOR_MENSAGEM = 1000
ZERO = Decimal("0.000")

MENSAGENS = {
    "rodada_inexistente": "A rodada não existe.",
    "ja_cancelada": "Esta rodada já foi cancelada.",
    "rodada_encerrada": "A rodada já foi encerrada e não pode ser cancelada.",
    "indicacao_obrigatoria": "Informe se existe reembolso devido.",
    "mensagem_longa": "A mensagem passa de 1000 caracteres.",
}


class CancelamentoRecusado(Exception):
    """O cancelamento foi recusado; `codigo` identifica a recusa e a mensagem é a da tela."""

    def __init__(self, codigo: str) -> None:
        super().__init__(MENSAGENS[codigo])
        self.codigo = codigo


def _conferir_a_etapa(etapa: str) -> None:
    """A etapa precisa ser cancelável: as ativas. A cancelada e a encerrada têm recusa própria."""
    if etapa == Etapa.CANCELADA:
        raise CancelamentoRecusado("ja_cancelada")
    if etapa == Etapa.DISPONIVEL_PARA_RETIRADA:
        raise CancelamentoRecusado("rodada_encerrada")


def _compradores_envolvidos(fornecedor_id: int) -> list[int]:
    """Os donos das parcelas não removidas dos produtos do fornecedor, por `pk`."""
    return sorted(
        set(
            ParcelaDeInteresse.objects.filter(produto__fornecedor_id=fornecedor_id)
            .exclude(situacao=SituacaoParcela.REMOVIDA)
            .values_list("comprador_id", flat=True)
        )
    )


def _remover_os_interesses(fornecedor_id: int) -> list[dict[str, Any]]:
    """Regra 6: cada parcela `ativa` ou `em_pedido` perde a reserva. Com parte pendente, vira
    `pendente` (a fila do fornecedor não pertence a ciclo nenhum, §5.2); sem ela, `removida`. As
    parcelas já `pendente` não mudam; nenhuma é criada e nenhuma sequência muda. Com as parcelas
    já travadas por `_travar`."""
    alteradas: list[dict[str, Any]] = []
    parcelas = (
        ParcelaDeInteresse.objects.filter(
            produto__fornecedor_id=fornecedor_id,
            situacao__in=(SituacaoParcela.ATIVA, SituacaoParcela.EM_PEDIDO),
        )
        .order_by("produto_id", "sequencia")
        .select_related("produto")
    )
    for parcela in parcelas:
        nova = (
            SituacaoParcela.PENDENTE
            if parcela.quantidade_pendente > 0
            else SituacaoParcela.REMOVIDA
        )
        alteradas.append(
            {
                "parcela": parcela.pk,
                "comprador": parcela.comprador_id,
                "situacao_anterior": str(parcela.situacao),
                "situacao_nova": str(nova),
                "reservada_anterior": str(parcela.quantidade_reservada),
                "pendente_mantida": str(parcela.quantidade_pendente),
            }
        )
        parcela.quantidade_reservada = ZERO
        parcela.situacao = nova
        parcela.save(update_fields=["quantidade_reservada", "situacao"])
    return alteradas


def _gravar_o_cancelamento(
    autor: Conta,
    rodada: Rodada,
    instante: Any,
    etapa_anterior: str,
    *,
    com_reembolso: bool,
    mensagem: str,
) -> CancelamentoDaRodada:
    return CancelamentoDaRodada.objects.create(
        rodada=rodada,
        autor=autor,
        cancelada_em=instante,
        com_reembolso=com_reembolso,
        mensagem=mensagem,
        etapa_anterior=etapa_anterior,
    )


def cancelar_rodada(
    autor: Conta | None, rodada: Rodada, *, com_reembolso: bool, mensagem: str = ""
) -> CancelamentoDaRodada:
    """Cancela a rodada inteira (E12-01). Só o administrador ativo, fora de transação, com
    `com_reembolso` exatamente `True` ou `False` e a mensagem opcional de até 1000 caracteres.
    Não recebe lista de compradores, motivo nem informação do fornecedor (T-16)."""
    if (
        autor is None
        or getattr(autor, "papel", None) != Papel.ADMINISTRADOR
        or getattr(autor, "situacao", None) != Situacao.ATIVA
    ):
        raise PermissionDenied
    exigir_fora_de_transacao()
    if com_reembolso is not True and com_reembolso is not False:
        raise CancelamentoRecusado("indicacao_obrigatoria")
    mensagem = mensagem.strip()
    if len(mensagem) > MAIOR_MENSAGEM:
        raise CancelamentoRecusado("mensagem_longa")
    atual = Rodada.objects.filter(pk=rodada.pk).first()
    if atual is None:
        raise CancelamentoRecusado("rodada_inexistente")
    _conferir_a_etapa(atual.etapa)
    with transaction.atomic():
        travada = _travar(
            atual.pk, atual.fornecedor_id, _compradores_envolvidos(atual.fornecedor_id)
        )
        instante = agora()  # lido depois das travas
        _conferir_a_etapa(travada.etapa)  # relida sob a trava
        etapa_anterior = str(travada.etapa)
        parcelas = _remover_os_interesses(travada.fornecedor_id)
        travada.etapa = Etapa.CANCELADA
        travada.save(update_fields=["etapa"])
        cancelamento = _gravar_o_cancelamento(
            autor,
            travada,
            instante,
            etapa_anterior,
            com_reembolso=com_reembolso,
            mensagem=mensagem,
        )
        registrar_auditoria(
            autor,
            "rodada.cancelar",
            travada,
            {
                "rodada": travada.pk,
                "etapa_anterior": etapa_anterior,
                "cancelada_em": instante.isoformat(),
                "com_reembolso": com_reembolso,
                "com_mensagem": bool(mensagem),
                "parcelas": parcelas,
                "pedidos_cancelados": [],
                "cobrancas": [],
                "reembolsos": [],
            },
        )
    return cancelamento
