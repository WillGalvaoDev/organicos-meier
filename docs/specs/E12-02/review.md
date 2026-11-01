# E12-02 — Registro da implementação (agente 2, 2026-11-01)

Comando: `uv run pytest tests/tecnicos/test_cancelamento_com_pedidos.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-16 | `349f230` | **Red: 9 failed, 9 passed.** Falhas pelo motivo esperado: Y continua `aguardando_pagamento` (A-1, A-16 ii); sem `ChamadaAoProvedor` `cancelar_cobranca` com o alvo `:cancelamento_da_rodada` (A-4, A-5); a criação da tentativa `solicitada` executa (`criada`, A-6); `DID NOT RAISE PagamentoRecusado` (A-7); auditoria sem `pedidos_cancelados` (A-14); o cancelamento não espera o pedido de pagamento (A-15). **Passaram de primeira (regressão, registrados como tais):** A-2, A-3 (a parcela de A em P1 já nasce `pendente`), A-8, A-9 (a conferência de etapa da E11 já recusa), A-10 (as tarefas já filtram a etapa `pagamento`), A-11 (o spec já previa), A-12, A-13, A-16 (i) |
| Motivo `cancelamento_da_rodada` (migração 0013: `max_length` 20 → 30 e a restrição), cancelamento dos pedidos não pagos, agendamento das cobranças (tentativas `criada` e órfãs), `rodada_cancelada` em `pedir_pagamento`, auditoria | `de6bd01` | **18 passed**; suíte completa **2838 passed** |

## Decisões técnicas
- `SituacaoDoPedido.motivo_do_cancelamento` passou a 30 caracteres: o novo motivo tem 22.
- `pedir_pagamento` lê a etapa da rodada numa consulta própria depois da trava da situação (o `select_related` do `select_for_update` travaria também a rodada). A recusa vem logo depois de `nao_e_seu`.
- Os agendamentos não disparam a execução no commit: a tarefa periódica de chamadas as processa (infraestrutura 4.8).
- Acréscimo fora do texto das fatias, para o painel não quebrar com o motivo novo: `CANCELAMENTOS_POR_EXTENSO` ganhou "Cancelado (rodada cancelada)" (o texto da E12-06). O teste da tela é da E12-06.
- Auditoria: `pedidos_cancelados` (pedido e situação anterior), `pedidos_pagos` e `cobrancas` (alvo e `id_externo`).
