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
from apps.pagamentos.chamadas import agendar_chamada
from apps.pagamentos.consulta import exigir_fora_de_transacao, pendentes_das_referencias
from apps.pedidos.apuracao import _travar
from apps.pedidos.models import (
    AberturaDoPagamento,
    CancelamentoDaRodada,
    MotivoDoCancelamento,
    Pedido,
    SituacaoDaTentativa,
    SituacaoDePagamento,
    SituacaoDoPedido,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import agendar_cancelamento
from apps.rodadas.ciclos import ciclo_vigente
from apps.rodadas.models import Etapa, Rodada

MAIOR_MENSAGEM = 1000
MOTIVO_NO_ALVO = MotivoDoCancelamento.CANCELAMENTO_DA_RODADA.value
ETAPAS_COM_PEDIDOS = (Etapa.PAGAMENTO, Etapa.AGUARDANDO_FORNECEDOR)
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


def _compradores_envolvidos(rodada: Rodada) -> list[int]:
    """Os donos das parcelas não removidas dos produtos do fornecedor e os compradores dos pedidos
    de todas as aberturas da rodada, por `pk`."""
    donos = ParcelaDeInteresse.objects.filter(produto__fornecedor_id=rodada.fornecedor_id).exclude(
        situacao=SituacaoParcela.REMOVIDA
    )
    compradores = set(donos.values_list("comprador_id", flat=True))
    compradores |= set(
        Pedido.objects.filter(abertura__rodada_id=rodada.pk).values_list("comprador_id", flat=True)
    )
    return sorted(compradores)


def _pedidos_da_abertura_vigente(rodada: Rodada) -> list[Pedido]:
    """Os pedidos da abertura do ciclo vigente, nas etapas que têm pedido congelado. Os das
    aberturas anteriores já foram apurados (retorno ao interesse) e só são lidos."""
    if rodada.etapa not in ETAPAS_COM_PEDIDOS:
        return []
    ciclo = ciclo_vigente(rodada)
    abertura = AberturaDoPagamento.objects.filter(ciclo=ciclo).first() if ciclo else None
    if abertura is None:
        return []
    return list(Pedido.objects.filter(abertura=abertura).order_by("pk"))


def _cancelar_os_pedidos_nao_pagos(
    pedidos: list[Pedido], instante: Any
) -> tuple[list[dict[str, Any]], list[int]]:
    """Regra 3: cada pedido `aguardando_pagamento` passa a `cancelado` pelo cancelamento da
    rodada, com as situações já travadas. Os já cancelados não mudam; os pagos continuam pagos.
    A composição do pedido não é tocada (§7.1). Devolve os cancelados agora e os pagos."""
    cancelados: list[dict[str, Any]] = []
    pagos: list[int] = []
    situacoes = (
        SituacaoDoPedido.objects.select_for_update()
        .filter(pedido__in=pedidos)
        .order_by("pedido_id")
    )
    for situacao in situacoes:
        if situacao.situacao == SituacaoDePagamento.PAGO:
            pagos.append(situacao.pedido_id)
        elif situacao.situacao == SituacaoDePagamento.AGUARDANDO_PAGAMENTO:
            cancelados.append(
                {"pedido": situacao.pedido_id, "situacao_anterior": str(situacao.situacao)}
            )
            situacao.situacao = SituacaoDePagamento.CANCELADO
            situacao.cancelado_em = instante
            situacao.motivo_do_cancelamento = MotivoDoCancelamento.CANCELAMENTO_DA_RODADA
            situacao.save(update_fields=["situacao", "cancelado_em", "motivo_do_cancelamento"])
    return cancelados, pagos


def _agendar_o_cancelamento_das_cobrancas(pedidos: list[Pedido]) -> list[dict[str, str]]:
    """Regra 6: agenda, na transação, o cancelamento no provedor de cada cobrança pendente: a das
    tentativas `criada` (de pedido cancelado ou pago) e as órfãs, sem tentativa vinculada. O alvo
    próprio do motivo evita esperar uma chamada em andamento (E07-R01). A tentativa `solicitada`,
    sem cobrança, não recebe agendamento: a criação já recusa o pedido cancelado."""
    agendadas: list[dict[str, str]] = []
    tentativas = list(
        TentativaDePagamento.objects.filter(pedido__in=pedidos).order_by("pedido_id", "numero")
    )
    com_tentativa = {t.id_externo for t in tentativas if t.id_externo}
    for tentativa in tentativas:
        if tentativa.situacao != SituacaoDaTentativa.CRIADA:
            continue
        chamada = agendar_cancelamento(tentativa, MOTIVO_NO_ALVO)
        if chamada is not None:
            agendadas.append({"alvo": chamada.alvo, "id_externo": str(tentativa.id_externo)})
    for pagamento in pendentes_das_referencias([p.referencia_externa for p in pedidos]):
        if pagamento.id_externo in com_tentativa:
            continue
        chamada = agendar_chamada(
            "cancelar_cobranca",
            f"{pagamento.id_externo}:{MOTIVO_NO_ALVO}",
            parametros={"id_externo": pagamento.id_externo},
        )
        agendadas.append({"alvo": chamada.alvo, "id_externo": pagamento.id_externo})
    return agendadas


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
        travada = _travar(atual.pk, atual.fornecedor_id, _compradores_envolvidos(atual))
        instante = agora()  # lido depois das travas
        _conferir_a_etapa(travada.etapa)  # relida sob a trava
        etapa_anterior = str(travada.etapa)
        pedidos = _pedidos_da_abertura_vigente(travada)
        cancelados, pagos = _cancelar_os_pedidos_nao_pagos(pedidos, instante)
        parcelas = _remover_os_interesses(travada.fornecedor_id)
        cobrancas = _agendar_o_cancelamento_das_cobrancas(pedidos)
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
                "pedidos_cancelados": cancelados,
                "pedidos_pagos": pagos,
                "cobrancas": cobrancas,
                "reembolsos": [],
            },
        )
    return cancelamento
