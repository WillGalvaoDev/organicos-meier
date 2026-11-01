# E12-02 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo AP**, como na E11 (`tests/apoio/apuracao.py`, `arranjo_ap`):
- pedido X de A: 94,35;
- pedido Y de B: 106,15;
- pagamento aberto em `T0`.

"Pago pelo simulador" como na E11-01. O teste roda fora de transação. Salvo indicação, o relógio está em `T0 + 2h` e o cancelamento é `com_reembolso=False`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §7.2, cenário 41 | positivo | AP; X pago; Y sem pagamento | `cancelar_rodada(admin, rodada, com_reembolso=False)` | a rodada `cancelada`; X `pago` e intacto; Y `cancelado` com `motivo_do_cancelamento = cancelamento_da_rodada` e `cancelado_em = T0 + 2h`; todas as parcelas de A e B `removida`; `total_reservado` zero em P1 e P2. **Red esperado:** Y continua `aguardando_pagamento` |
| A-2 | §7.1 | positivo | o A-1 | comparar `Pedido`, `ItemDoPedido` e `ParcelaNoPedido` antes e depois | iguais, campo a campo; nenhuma linha nova |
| A-3 | Regra 5, herdado E08 | positivo | AP com `pendente_a_p1=2`; X pago | `cancelar_rodada` | a parcela de A em P1 `pendente`, com pendente 2, reservado 0 e a mesma sequência |
| A-4 | Herdado E08, regra 6 | positivo | AP; Y com uma tentativa `criada` e a cobrança pendente no simulador | `cancelar_rodada`; depois `processar_chamadas()` | uma `ChamadaAoProvedor` `cancelar_cobranca` com o alvo `t<tentativa>:cancelamento_da_rodada`, agendada no commit; depois de processada, a cobrança `cancelado` no simulador e o pagamento sincronizado |
| A-5 | Regra 6, E08-R03 | positivo | AP; uma cobrança pendente com a referência de Y no simulador, registrada pela reconsulta, sem tentativa vinculada | `cancelar_rodada`; `processar_chamadas()` | a chamada com o alvo `<id_externo>:cancelamento_da_rodada`; a cobrança cancelada |
| A-6 | Regra 6 | positivo | AP; Y com a tentativa `solicitada` (criação ainda não executada) | `cancelar_rodada`; `processar_chamadas()` | nenhum agendamento de cancelamento para ela; a criação recusada com `pedido_cancelado`; nenhuma cobrança no simulador |
| A-7 | Herdado E08, regra 7 | negativo | o A-1 | `pedir_pagamento(B, Y)` e `pedir_pagamento(A, X)` | `PagamentoRecusado("rodada_cancelada")` nos dois, com a mensagem da regra 7; nenhuma tentativa nova; nenhuma chamada nova. **Red esperado:** `pedido_cancelado` e `pedido_pago` |
| A-8 | Regra 8 | negativo | o A-1 com o relógio em `T0 + 48h` | `iniciar_apuracao(admin, rodada)` | `ApuracaoRecusada("fora_de_pagamento")`; nenhuma consulta; nenhuma `ApuracaoFinal` |
| A-9 | Regra 8 | negativo | AP-viável apurada (E11-01) e não aprovada; depois `cancelar_rodada` | `aprovar_resultado(admin, rodada)` | `ApuracaoRecusada("fora_de_pagamento")`; nenhum `ApuracaoNoLivro`; nenhuma `AprovacaoDoResultado` |
| A-10 | Regra 9 | positivo | o A-1 com uma tentativa de X ainda `criada` (segunda cobrança) e o relógio em `T0 + 25h` | `bloquear_tentativas_vencidas_agora()` e `reconsultar_pagamentos_da_margem_agora()` | nenhuma das duas trata a abertura da rodada cancelada: nenhuma chamada com alvo `:prazo` nem consulta nova |
| A-11 | Cenário 44, T-15 | positivo | AP; Y pago em duplicidade (dois pagamentos aprovados de Y; um quita e o outro gera destino `devolucao` `duplicidade` com a obrigação integral, E08-04/E09-04) | `cancelar_rodada(..., com_reembolso=False)` | nenhuma obrigação nova; a obrigação de duplicidade continua com o mesmo devido, sem parcela e sem liquidação; a contagem de `MovimentoFinanceiro` igual. **Red esperado:** nenhum (regressão: registrar como tal se passar de primeira) |
| A-12 | Infra 3.2, regra 10 | positivo | AP-viável apurada e aprovada (E11-06; etapa `aguardando_fornecedor`) | `cancelar_rodada(..., com_reembolso=False)` | a rodada `cancelada`; os saldos de custódia, obrigação com o fornecedor, frete e receita da rodada iguais aos de antes; nenhum movimento novo; a `ApuracaoNoLivro` intacta |
| A-13 | Regra 3 | positivo | AP-viável apurada (Y `cancelado` por `inadimplencia`) | `cancelar_rodada` | Y continua `cancelado` com o motivo `inadimplencia` e o `cancelado_em` da apuração |
| A-14 | Auditoria | positivo | o A-4 | ler a auditoria `rodada.cancelar` | Y nos cancelados agora (situação anterior `aguardando_pagamento`); X nos pagos; a cobrança com o alvo e o `id_externo` |
| A-15 | Concorrência | concorrência | AP; Y sem tentativa | (i) `pedir_pagamento(B, Y)` pausado depois de travar a situação, antes do commit, e o cancelamento em paralelo; (ii) a ordem inversa | (i) o cancelamento espera; Y `cancelado`; a tentativa `solicitada` não gera cobrança (a criação recusa). (ii) `pedir_pagamento` espera e recebe `rodada_cancelada`. Nos dois, nenhuma cobrança pendente no simulador |
| A-16 | Concorrência | concorrência | AP-viável, X pago, Y sem pagamento, relógio em `T0 + 48h` | (i) `iniciar_apuracao` pausada antes do commit e o cancelamento em paralelo; (ii) o cancelamento pausado e a apuração em paralelo | sem impasse; (i) o cancelamento espera; Y `cancelado` por `inadimplencia`; a rodada `cancelada`. (ii) a apuração recebe `fora_de_pagamento`; Y `cancelado` por `cancelamento_da_rodada` |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-14 | `tests/tecnicos/test_cancelamento_com_pedidos.py` |
| A-15 e A-16 | `tests/tecnicos/test_cancelamento_com_pedidos.py`, com transações PostgreSQL reais |
