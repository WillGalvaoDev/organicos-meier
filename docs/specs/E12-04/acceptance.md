# E12-04 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação. Arranjo AP como na E12-02. O cancelamento é feito pelo serviço, fora de transação, no instante indicado.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 51, T-19 | positivo | AP; Y com a cobrança criada em `T0 + 1h`; o cancelamento sem reembolso em `T0 + 3h`; a cobrança aprovada no simulador em `T0 + 4h` (antes de o cancelamento ser processado) | o aviso de aprovação processado | Y continua `cancelado` por `cancelamento_da_rodada`, sem `quitado_em`; destino `devolucao` com `pedido_cancelado`; uma obrigação integral de 106,15 financiada pelo próprio pagamento; alerta crítico `pagamento_depois_do_cancelamento` com pagamento, pedido, comprador, valor, `aprovado_em` e `cancelada_em`; `Pedido` e itens inalterados. **Red esperado:** nenhum alerta |
| A-2 | Regra 1, herdado E08 | positivo | AP; Y com a cobrança aprovada no simulador em `T0 + 2h`, sem aviso entregue; cancelamento sem reembolso em `T0 + 3h` (sem consulta prévia); depois o aviso entregue | processar o aviso | Y não quita: destino `devolucao` com `pedido_cancelado`; a obrigação integral; o alerta aberto. **Red esperado:** Y quita (a aprovação é anterior a `cancelado_em`) |
| A-3 | Regra 1 | positivo | AP; X pago; o cancelamento com reembolso; depois uma segunda cobrança de X aprovada | processar o aviso | destino `devolucao` com `duplicidade`; alerta `duplicidade` e alerta `pagamento_depois_do_cancelamento`; o reembolso do cancelamento de X intacto |
| A-4 | Regra 3 | positivo | AP-viável apurada (Y `cancelado` por `inadimplencia`); a rodada cancelada; depois a cobrança de Y, criada antes de `T0 + 24h`, aprovada em `T0 + 47h` e informada agora | processar o aviso | destino `devolucao` com `pedido_cancelado`; alerta `aprovado_no_prazo_depois_da_apuracao` e alerta `pagamento_depois_do_cancelamento` |
| A-5 | Idempotência | negativo | o A-1 | entregar o aviso de novo; executar `registrar_entrada` do destino de novo | um destino, uma obrigação, um alerta `pagamento_depois_do_cancelamento` |
| A-6 | Regra 4 | negativo | o A-5 com o alerta resolvido pelo administrador | entregar o aviso de novo | o alerta continua resolvido; nenhum novo |
| A-7 | Escopo | negativo | o A-1 | `autorizar_devolucoes_do_cancelamento_agora()` | a obrigação do destino não é autorizada pela tarefa (segue a autorização da E10) |
| A-8 | Escopo | negativo | um pagamento aprovado de pedido de rodada não cancelada, aguardando pagamento, dentro do prazo | processar o aviso | quita como hoje; nenhum alerta `pagamento_depois_do_cancelamento` (regressão) |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-8 | `tests/tecnicos/test_pagamento_depois_do_cancelamento.py` |
