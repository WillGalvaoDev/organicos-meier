# E11-06 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação. Arranjo AP como na E11-01 (`acceptance.md`).

**Arranjo V:**
- AP-viável, com X pago e Y sem pagamento;
- a apuração feita em `T0 + 48h`, com o resultado `valida`;
- o reembolso de caixa de X: 20,00 de produtos, 1,00 de serviço e 2,59 de frete (E11-04, A-1);
- a custódia de A depois disso: produtos 60,00, serviço 3,00 e frete 7,76;
- o relógio em `T0 + 49h`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §7, §8.2 3.6, cenário 14 | positivo | V | `aprovar_resultado(admin, rodada)` | a rodada em `aguardando_fornecedor`; uma `AprovacaoDoResultado`; uma `ApuracaoNoLivro` do ciclo com X como pedido válido; o movimento `apuracao:<ciclo>` levando 60,00 à obrigação com o fornecedor, 3,00 à receita de serviço e 7,76 ao frete; frete efetivo 22,00 e arrecadado 7,76; uma `Despesa` de déficit de frete de 14,24. **Red esperado:** a função não existe |
| A-2 | P-1, cenário 14 | positivo | o A-1 | comparar o pedido X e o pagamento de A | iguais; nenhuma cobrança nova; a custódia de A zerada |
| A-3 | E09-06 | positivo | o A-1 | `frete_do_ciclo(ciclo)` | efetivo 22,00, arrecadado 7,76, devolvido 0,00 e déficit 14,24 |
| A-4 | Infra 4.4 | positivo | V; antes da aprovação, a cobrança de Y aprovada no simulador em `T0 + 47h59` sem aviso entregue | `aprovar_resultado` | a nova consulta registra o pagamento: destino `devolucao` com `pedido_cancelado`, obrigação integral e alerta crítico `aprovado_no_prazo_depois_da_apuracao` (E11-01); Y continua cancelado; o avanço acontece, com X como único pedido válido |
| A-5 | E07-06 | negativo | V; a próxima consulta ao provedor falha | `aprovar_resultado` | `ConsultaAoProvedorFalhou`; a rodada em `pagamento`; sem `AprovacaoDoResultado`, sem `ApuracaoNoLivro`, sem despesa |
| A-6 | Permissão | negativo | V | `aprovar_resultado` com um comprador, com um fornecedor e com `None` | `PermissionDenied`, sem escrita |
| A-7 | Recusas | negativo | (i) AP-viável, sem apuração, depois de `T0 + 48h`; (ii) AP-insuficiente apurada (a rodada voltou para interesse); (iii) o A-1 feito | `aprovar_resultado` | (i) `sem_apuracao`; (ii) `fora_de_pagamento`; (iii) `fora_de_pagamento` (a rodada em `aguardando_fornecedor`). Sem consulta e sem escrita nos três |
| A-8 | Recusa | negativo | uma apuração com o resultado `retorno_para_interesse` e a rodada de volta a `pagamento` por atualização direta no arranjo (estado que nenhum fluxo produz, para isolar a conferência) | `aprovar_resultado` | `resultado_nao_valido` |
| A-9 | Contrato da consulta | negativo | V, num teste com `transaction=True` | `aprovar_resultado` dentro de `transaction.atomic()` do teste | `RuntimeError`; nenhuma consulta registrada; nenhuma escrita |
| A-10 | Concorrência | concorrência | V | duas `aprovar_resultado` em paralelo, a primeira pausada depois de registrar a apuração no livro, antes do commit | uma `AprovacaoDoResultado`; uma `ApuracaoNoLivro`; a outra recebe `fora_de_pagamento` ou `ja_aprovado`, sem escrita |
| A-11 | Sinal | positivo | V, com um receptor de teste conectado a `resultado_aprovado` | `aprovar_resultado` | o receptor chamado uma vez, com a rodada, o ciclo e a apuração, dentro da transação (uma exceção no receptor desfaz o avanço) |
| A-12 | Pedidos válidos | positivo | um arranjo em que o pedido pago de C tem todas as unidades em caixas invalidadas, e o resultado é `valida` pelo pedido de A | `aprovar_resultado` | só o pedido de A é válido (`PedidoApurado`); a custódia de C já estava zerada pelos reembolsos e continua zerada |
| A-13 | Auditoria | positivo | o A-1 | ler a auditoria `rodada.aprovar_resultado` | autor admin; a apuração; o pedido X; frete efetivo 22,00, arrecadado 7,76 e déficit 14,24 |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-9 e A-11 a A-13 | `tests/tecnicos/test_apuracao_aprovacao.py` |
| A-10 | `tests/tecnicos/test_apuracao_aprovacao.py`, com transações PostgreSQL reais |
