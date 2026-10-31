"""Apuração final do ciclo (E11).

A apuração tem dois atos do administrador: iniciá-la, a partir de `T0 + 48h` (esta fatia e as
seguintes), e aprovar o resultado. Iniciar reconsulta o provedor antes da transação, sem travas
(infraestrutura 4.2), e depois decide numa só transação: cancela os não pagos e grava a
`ApuracaoFinal`. A rodada continua em `pagamento`: a apuração feita é o registro, não uma etapa.

Ordem das travas da decisão: o fornecedor, a rodada, todos os produtos do fornecedor por `pk`
(e, em cada um, o estoque da rodada e as parcelas) e as `SituacaoDoPedido` de todos os pedidos da
abertura. A apuração não trava pagamento nenhum, então segue a ordem da E08-03.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.catalogo.models import Produto
from apps.contas.models import Conta, Papel
from apps.fornecedores.models import Fornecedor
from apps.interesses.models import ParcelaDeInteresse, SituacaoParcela
from apps.notificacoes.emissao import emitir_evento
from apps.notificacoes.eventos import Evento
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora, no_fuso_da_operacao
from apps.pagamentos.consulta import consultar_antes_de_decidir, exigir_fora_de_transacao
from apps.pedidos.models import (
    AberturaDoPagamento,
    ApuracaoFinal,
    MotivoDoCancelamento,
    Pedido,
    SituacaoDaTentativa,
    SituacaoDePagamento,
    SituacaoDoPedido,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import agendar_cancelamento
from apps.pedidos.prazos import fim_da_margem, pode_iniciar_apuracao
from apps.rodadas.ciclos import ciclo_vigente
from apps.rodadas.models import EstoqueDaRodada, Etapa, Rodada

logger = logging.getLogger(__name__)

MOTIVO_DA_TENTATIVA = "apuracao"
MAIOR_TITULO = 150
ZERO = Decimal("0.000")

MENSAGENS = {
    "fora_de_pagamento": "Só uma rodada na etapa de pagamento pode ser apurada.",
    "antes_do_prazo": (
        "A apuração só pode começar a partir de {liberada:%d/%m/%Y} às {liberada:%H:%M} "
        "(horário de Brasília)."
    ),
    "ja_apurada": "A apuração deste ciclo já foi feita.",
}


class ApuracaoRecusada(Exception):
    """A apuração não pode ser feita agora. `codigo` diz o motivo; a mensagem é a da tela."""

    def __init__(self, codigo: str, liberada_em: datetime | None = None) -> None:
        self.codigo = codigo
        liberada = no_fuso_da_operacao(liberada_em) if liberada_em is not None else None
        self.mensagem = MENSAGENS[codigo].format(liberada=liberada)
        super().__init__(self.mensagem)


def _exigir_administrador(autor: Conta | None) -> Conta:
    if autor is None or autor.papel != Papel.ADMINISTRADOR:
        raise PermissionDenied
    return autor


def _conferir(rodada: Rodada, instante: datetime) -> AberturaDoPagamento:
    """As três conferências da apuração, sobre a rodada relida: em `pagamento`, ciclo ainda não
    apurado e `T0 + 48h` chegado. A primeira que falha vale."""
    if rodada.etapa != Etapa.PAGAMENTO:
        raise ApuracaoRecusada("fora_de_pagamento")
    ciclo = ciclo_vigente(rodada)
    abertura: AberturaDoPagamento | None = (
        AberturaDoPagamento.objects.filter(ciclo=ciclo).first() if ciclo else None
    )
    if abertura is None:
        raise ApuracaoRecusada("fora_de_pagamento")
    if ApuracaoFinal.objects.filter(ciclo_id=abertura.ciclo_id).exists():
        raise ApuracaoRecusada("ja_apurada")
    if not pode_iniciar_apuracao(abertura, instante):
        raise ApuracaoRecusada("antes_do_prazo", fim_da_margem(abertura))
    return abertura


def _travar(rodada_pk: int, fornecedor_id: int) -> Rodada:
    """As travas da decisão, na ordem documentada no módulo. Devolve a rodada travada.

    Fornecedor, rodada, produtos, estoques e parcelas são travados com `FOR NO KEY UPDATE`: ele
    exclui as operações de interesse (que usam `FOR UPDATE`) e as outras apurações, mas deixa um
    pagamento que quita ou devolve inserir registros que apontam para a rodada e para o
    fornecedor. Com `FOR UPDATE`, o commit desse pagamento esperaria a conferência da chave
    estrangeira contra a apuração, que espera a trava da situação dele: impasse.
    """
    Fornecedor.objects.select_for_update(no_key=True).get(pk=fornecedor_id)
    travada = Rodada.objects.select_for_update(no_key=True).get(pk=rodada_pk)
    produtos = list(
        Produto.objects.select_for_update(no_key=True)
        .filter(fornecedor_id=fornecedor_id)
        .order_by("pk")
    )
    no_estoque = set(
        EstoqueDaRodada.objects.filter(rodada_id=travada.pk).values_list("produto_id", flat=True)
    )
    for produto in produtos:
        if produto.pk in no_estoque:
            EstoqueDaRodada.objects.select_for_update(no_key=True).get(
                rodada_id=travada.pk, produto_id=produto.pk
            )
        list(
            ParcelaDeInteresse.objects.select_for_update(no_key=True)
            .filter(produto_id=produto.pk)
            .exclude(situacao=SituacaoParcela.REMOVIDA)
            .order_by("sequencia")
        )
    return travada


def _cancelar_os_nao_pagos(situacoes: list[SituacaoDoPedido], instante: datetime) -> list[int]:
    """Cada `aguardando_pagamento` passa a `cancelado` por inadimplência, sem mexer na
    composição do pedido (§7.1). Devolve os pedidos cancelados agora."""
    cancelados: list[int] = []
    for situacao in situacoes:
        if situacao.situacao != SituacaoDePagamento.AGUARDANDO_PAGAMENTO:
            continue
        situacao.situacao = SituacaoDePagamento.CANCELADO
        situacao.cancelado_em = instante
        situacao.motivo_do_cancelamento = MotivoDoCancelamento.INADIMPLENCIA
        situacao.save(update_fields=["situacao", "cancelado_em", "motivo_do_cancelamento"])
        cancelados.append(situacao.pedido_id)
    return cancelados


def _remover_as_parcelas_dos_inadimplentes(
    fornecedor_id: int, compradores: list[int]
) -> list[dict[str, Any]]:
    """Os inadimplentes perdem todas as parcelas `ativa`, `em_pedido` e `pendente` em produtos do
    fornecedor, inclusive de fora do estoque da rodada (§8.2, passo 3.2). A sequência e a
    quantidade original ficam; as parcelas de outros fornecedores não mudam. Nenhuma reserva é
    atendida agora: fora de interesse a fila não é atendida. Devolve o que saiu, por comprador."""
    parcelas = ParcelaDeInteresse.objects.filter(
        comprador_id__in=compradores,
        produto__fornecedor_id=fornecedor_id,
        situacao__in=(
            SituacaoParcela.ATIVA,
            SituacaoParcela.EM_PEDIDO,
            SituacaoParcela.PENDENTE,
        ),
    ).order_by("comprador_id", "produto_id", "sequencia")
    por_comprador: dict[int, list[list[object]]] = {}
    for parcela in parcelas:
        por_comprador.setdefault(parcela.comprador_id, []).append(
            [parcela.pk, str(parcela.quantidade_reservada), str(parcela.quantidade_pendente)]
        )
        parcela.quantidade_reservada = ZERO
        parcela.quantidade_pendente = ZERO
        parcela.situacao = SituacaoParcela.REMOVIDA
        parcela.save(update_fields=["quantidade_reservada", "quantidade_pendente", "situacao"])
    return [{"comprador": pk, "parcelas": removidas} for pk, removidas in por_comprador.items()]


def _avisar_o_cancelamento(pedidos: list[Pedido], fornecedor: Fornecedor) -> None:
    """O aviso de cancelamento ao comprador cujo pedido foi cancelado por esta apuração. Quem já
    tinha o pedido cancelado por suspensão ou remoção não recebe: a moderação já tratou a conta."""
    for pedido in pedidos:
        emitir_evento(
            Evento.ITENS_CANCELADOS,
            pedido.comprador,
            titulo=f"Pedido cancelado: {fornecedor.nome}"[:MAIOR_TITULO],
            corpo=(
                f"Seu pedido {pedido.pk} da rodada de {fornecedor.nome} foi cancelado porque o "
                "pagamento não foi identificado até o fim do prazo. Os itens desse fornecedor "
                "saíram do seu carrinho, inclusive reservas e quantidades pendentes. Nada foi "
                "cobrado neste pedido."
            ),
            link=f"/pedidos/{pedido.pk}/",
            chave=f"itens_cancelados:inadimplencia:{pedido.pk}:{pedido.comprador_id}",
        )


def _cancelar_as_cobrancas_pendentes(pedido_ids: list[int]) -> None:
    """Para cada pedido da abertura, pago ou não, agenda o cancelamento das tentativas `criada`
    cujo pagamento não é terminal (E08-03). O alvo próprio do motivo evita esperar uma chamada
    em andamento (E07-R01)."""
    tentativas = TentativaDePagamento.objects.filter(
        pedido_id__in=pedido_ids, situacao=SituacaoDaTentativa.CRIADA
    ).order_by("pedido_id", "numero")
    for tentativa in tentativas:
        agendar_cancelamento(tentativa, MOTIVO_DA_TENTATIVA)


def _gravar_a_apuracao(
    autor: Conta,
    rodada: Rodada,
    abertura: AberturaDoPagamento,
    instante: datetime,
    situacoes: list[SituacaoDoPedido],
    cancelados: list[int],
    anteriores: dict[int, str],
    inadimplentes: list[dict[str, Any]],
) -> ApuracaoFinal:
    pagos = [s.pedido_id for s in situacoes if s.situacao == SituacaoDePagamento.PAGO]
    nao_pagos = [s.pedido_id for s in situacoes if s.situacao != SituacaoDePagamento.PAGO]
    apuracao = ApuracaoFinal.objects.create(
        ciclo_id=abertura.ciclo_id,
        abertura=abertura,
        autor=autor,
        iniciada_em=instante,
        pedidos_pagos=len(pagos),
        pedidos_nao_pagos=len(nao_pagos),
    )
    dados: dict[str, Any] = {
        "rodada": rodada.pk,
        "ciclo": abertura.ciclo_id,
        "iniciada_em": instante.isoformat(),
        "pagos": pagos,
        "nao_pagos": [[pk, anteriores[pk]] for pk in nao_pagos],
        "cancelados_agora": cancelados,
        "inadimplentes": inadimplentes,
    }
    registrar_auditoria(autor, "rodada.apuracao_final", rodada, dados)
    return apuracao


def iniciar_apuracao(autor: Conta | None, rodada: Rodada) -> ApuracaoFinal:
    """Inicia a apuração final do ciclo vigente da rodada em `pagamento`, a partir de `T0 + 48h`.

    Só o administrador (`PermissionDenied`). Só fora de transação (`RuntimeError`): a reconsulta
    ao provedor vem antes da decisão. Uma `ConsultaAoProvedorFalhou` bloqueia a apuração.
    """
    administrador = _exigir_administrador(autor)
    exigir_fora_de_transacao()
    atual = Rodada.objects.get(pk=rodada.pk)
    abertura = _conferir(atual, agora())
    pedidos = list(Pedido.objects.filter(abertura=abertura).order_by("pk"))
    for pedido in pedidos:
        consultar_antes_de_decidir(pedido.referencia_externa)
    pedido_ids = [p.pk for p in pedidos]
    with transaction.atomic():
        travada = _travar(atual.pk, atual.fornecedor_id)
        instante = agora()  # lido depois das travas
        _conferir(travada, instante)
        situacoes = list(
            SituacaoDoPedido.objects.select_for_update()
            .filter(pedido_id__in=pedido_ids)
            .order_by("pedido_id")
        )
        anteriores = {s.pedido_id: s.situacao for s in situacoes}
        nao_pagos = {s.pedido_id for s in situacoes if s.situacao != SituacaoDePagamento.PAGO}
        cancelados = _cancelar_os_nao_pagos(situacoes, instante)
        compradores = [p.comprador_id for p in pedidos if p.pk in nao_pagos]
        inadimplentes = _remover_as_parcelas_dos_inadimplentes(travada.fornecedor_id, compradores)
        _cancelar_as_cobrancas_pendentes(pedido_ids)
        _avisar_o_cancelamento([p for p in pedidos if p.pk in cancelados], travada.fornecedor)
        return _gravar_a_apuracao(
            administrador,
            travada,
            abertura,
            instante,
            situacoes,
            cancelados,
            anteriores,
            inadimplentes,
        )
