"""Operações do provedor registradas pelos pedidos (E08-03): criar e cancelar cobrança.

`executar` fala com o provedor; `concluir` aplica o resultado, na mesma transação, depois que a
sincronização travou o pagamento (a ordem das travas é pagamento, situação do pedido, tentativa);
`falhou` trata a falha definitiva.
"""

import logging
from typing import Any

from apps.nucleo.tempo import agora
from apps.pagamentos.chamadas import (
    FalhaDefinitiva,
    Operacao,
    agendar_chamada,
    nao_encontrado,
    registrar_operacao,
)
from apps.pagamentos.models import ChamadaAoProvedor
from apps.pagamentos.provedor import (
    NovaCobranca,
    PagamentoConsultado,
    PagamentoNaoEncontrado,
    Provedor,
    RecusaDoProvedor,
    SituacaoNoProvedor,
)
from apps.pagamentos.sincronizacao import sincronizar_pagamento
from apps.pedidos.models import (
    SituacaoDaTentativa,
    SituacaoDePagamento,
    SituacaoDoPedido,
    TentativaDePagamento,
)
from apps.pedidos.pagamento import agendar_cancelamento
from apps.pedidos.prazos import aceita_tentativas, prazo_de_pagamento

logger = logging.getLogger(__name__)


def _motivo_da_recusa(tentativa: TentativaDePagamento) -> str | None:
    """Por que a criação não pode mais acontecer: o prazo, o pedido cancelado ou o pedido pago.
    Leitura sem trava; quem precisa de consistência é o `concluir`."""
    pedido = tentativa.pedido
    if not aceita_tentativas(pedido.abertura, agora()):
        return "prazo_encerrado"  # uma cobrança criada depois do prazo não seria aceita
    situacao = SituacaoDoPedido.objects.get(pedido=pedido).situacao
    if situacao == SituacaoDePagamento.CANCELADO:
        return "pedido_cancelado"
    if situacao == SituacaoDePagamento.PAGO:
        return "pedido_pago"
    return None


def _recusar_criacao(provedor: Provedor, tentativa: TentativaDePagamento, codigo: str) -> None:
    """A recusa nunca cria cobrança, mas procura o que o provedor já tenha: uma execução
    anterior pode ter criado a cobrança e perdido a resposta."""
    try:
        encontrados = tuple(provedor.buscar_por_referencia(tentativa.referencia_externa))
    except RecusaDoProvedor as erro:
        logger.warning(
            "Busca na recusa da criação recusada pelo provedor: tentativa %s, recusa %s",
            tentativa.pk,
            erro.codigo,
        )
        raise FalhaDefinitiva(codigo) from None
    raise FalhaDefinitiva(codigo, encontrados=encontrados)


def _executar_criacao(provedor: Provedor, chamada: ChamadaAoProvedor) -> Any:
    tentativa = TentativaDePagamento.objects.select_related("pedido__abertura").get(
        pk=chamada.parametros["tentativa"]
    )
    pedido = tentativa.pedido
    motivo = _motivo_da_recusa(tentativa)
    if motivo is not None:
        _recusar_criacao(provedor, tentativa, motivo)
    return provedor.criar_cobranca(
        NovaCobranca(
            chave_idempotencia=tentativa.chave_idempotencia,
            referencia_externa=tentativa.referencia_externa,
            valor=pedido.total,
            descricao=f"Orgânicos Méier — pedido {pedido.pk}",
            expira_em=prazo_de_pagamento(pedido.abertura),
            meio="pix",
        )
    )


def _concluir_criacao(chamada: ChamadaAoProvedor, resultado: Any) -> None:
    """Grava a tentativa `criada`. Se o pedido foi cancelado ou quitado enquanto a chamada ao
    provedor estava em andamento, agenda o cancelamento da cobrança que acabou de nascer: a
    moderação só vê tentativas `criada` e não espera chamada externa (E08-R02)."""
    sincronizar_pagamento(resultado.pagamento, origem="tarefa")
    tentativa_id = chamada.parametros["tentativa"]
    pedido_id = TentativaDePagamento.objects.values_list("pedido_id", flat=True).get(
        pk=tentativa_id
    )
    situacao = SituacaoDoPedido.objects.select_for_update().get(pedido_id=pedido_id)
    tentativa = TentativaDePagamento.objects.select_for_update().get(pk=tentativa_id)
    tentativa.situacao = SituacaoDaTentativa.CRIADA
    tentativa.id_externo = resultado.pagamento.id_externo
    tentativa.dados_para_pagar = resultado.dados_para_pagar
    tentativa.criada_em = resultado.pagamento.criado_em
    tentativa.save(update_fields=["situacao", "id_externo", "dados_para_pagar", "criada_em"])
    if situacao.situacao == SituacaoDePagamento.CANCELADO:
        agendar_cancelamento(tentativa, situacao.motivo_do_cancelamento)
    elif situacao.situacao == SituacaoDePagamento.PAGO:
        agendar_cancelamento(tentativa, "pedido_pago")


def _criacao_falhou(chamada: ChamadaAoProvedor, erro: Exception) -> None:
    """Sincroniza o que a busca achou (dinheiro nunca é ignorado), cancela a cobrança sem
    tentativa (a órfã) e só então marca a tentativa, na ordem das travas."""
    tentativa_id = chamada.parametros["tentativa"]
    encontrados: tuple[PagamentoConsultado, ...] = getattr(erro, "encontrados", ())
    codigo = str(getattr(erro, "codigo", "falha"))[:40]
    for consultado in encontrados:
        sincronizar_pagamento(consultado, origem="busca")
    orfas = sorted(
        (c for c in encontrados if _eh_orfa(c)), key=lambda c: (c.criado_em, c.id_externo)
    )
    for numero, orfa in enumerate(orfas, start=1):
        agendar_chamada(
            "cancelar_cobranca",
            f"t{tentativa_id}:recuperacao:{numero}",
            parametros={"id_externo": orfa.id_externo},
        )
        logger.warning(
            "Cobrança sem tentativa encontrada na recusa da criação: tentativa %s, pagamento %s, "
            "código %s",
            tentativa_id,
            orfa.id_externo,
            codigo,
        )
    tentativa = TentativaDePagamento.objects.select_for_update().get(pk=tentativa_id)
    tentativa.situacao = SituacaoDaTentativa.NAO_CRIADA
    tentativa.codigo_da_falha = codigo
    tentativa.save(update_fields=["situacao", "codigo_da_falha"])


def _eh_orfa(consultado: PagamentoConsultado) -> bool:
    """Pendente e sem tentativa vinculada: a resposta da criação se perdeu."""
    return (
        consultado.situacao == SituacaoNoProvedor.PENDENTE
        and not TentativaDePagamento.objects.filter(id_externo=consultado.id_externo).exists()
    )


def _executar_cancelamento(provedor: Provedor, chamada: ChamadaAoProvedor) -> Any:
    try:
        return provedor.cancelar_cobranca(chamada.parametros["id_externo"])
    except PagamentoNaoEncontrado:
        raise nao_encontrado(chamada) from None


def _concluir_cancelamento(chamada: ChamadaAoProvedor, resultado: Any) -> None:
    # Se o provedor devolver `aprovado` (pagamento no instante do cancelamento), vale o que ele
    # registrou; a decisão sobre o pedido é da quitação (E08-04).
    sincronizar_pagamento(resultado, origem="tarefa")


def registrar_operacoes() -> None:
    registrar_operacao(
        "criar_cobranca", Operacao(_executar_criacao, _concluir_criacao, _criacao_falhou)
    )
    registrar_operacao(
        "cancelar_cobranca", Operacao(_executar_cancelamento, _concluir_cancelamento)
    )
