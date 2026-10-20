"""Operações do provedor registradas pelos pedidos (E08-03): criar e cancelar cobrança.

`executar` fala com o provedor; `concluir` aplica o resultado, na mesma transação, depois que a
sincronização travou o pagamento (a ordem das travas é pagamento, situação do pedido, tentativa);
`falhou` trata a falha definitiva.
"""

from typing import Any

from apps.nucleo.tempo import agora, prazo_encerrado, somar_horas
from apps.pagamentos.chamadas import (
    FalhaDefinitiva,
    Operacao,
    nao_encontrado,
    registrar_operacao,
)
from apps.pagamentos.models import ChamadaAoProvedor
from apps.pagamentos.provedor import NovaCobranca, PagamentoNaoEncontrado, Provedor
from apps.pagamentos.sincronizacao import sincronizar_pagamento
from apps.pedidos.models import SituacaoDaTentativa, TentativaDePagamento

HORAS_DO_PRAZO_DE_PAGAMENTO = 24


def _executar_criacao(provedor: Provedor, chamada: ChamadaAoProvedor) -> Any:
    tentativa = TentativaDePagamento.objects.select_related("pedido__abertura").get(
        pk=chamada.parametros["tentativa"]
    )
    pedido = tentativa.pedido
    prazo = somar_horas(pedido.abertura.t0, HORAS_DO_PRAZO_DE_PAGAMENTO)
    if prazo_encerrado(agora(), prazo):  # uma cobrança criada depois do prazo não seria aceita
        raise FalhaDefinitiva("prazo_encerrado")
    return provedor.criar_cobranca(
        NovaCobranca(
            chave_idempotencia=tentativa.chave_idempotencia,
            referencia_externa=tentativa.referencia_externa,
            valor=pedido.total,
            descricao=f"Orgânicos Méier — pedido {pedido.pk}",
            expira_em=prazo,
            meio="pix",
        )
    )


def _concluir_criacao(chamada: ChamadaAoProvedor, resultado: Any) -> None:
    sincronizar_pagamento(resultado.pagamento, origem="tarefa")
    tentativa = TentativaDePagamento.objects.select_for_update().get(
        pk=chamada.parametros["tentativa"]
    )
    tentativa.situacao = SituacaoDaTentativa.CRIADA
    tentativa.id_externo = resultado.pagamento.id_externo
    tentativa.dados_para_pagar = resultado.dados_para_pagar
    tentativa.criada_em = resultado.pagamento.criado_em
    tentativa.save(update_fields=["situacao", "id_externo", "dados_para_pagar", "criada_em"])


def _criacao_falhou(chamada: ChamadaAoProvedor, erro: Exception) -> None:
    tentativa = TentativaDePagamento.objects.select_for_update().get(
        pk=chamada.parametros["tentativa"]
    )
    tentativa.situacao = SituacaoDaTentativa.NAO_CRIADA
    tentativa.codigo_da_falha = str(getattr(erro, "codigo", "falha"))[:40]
    tentativa.save(update_fields=["situacao", "codigo_da_falha"])


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
