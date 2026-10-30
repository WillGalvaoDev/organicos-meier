# E11-05 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação. Arranjo AP como na E11-01 (`acceptance.md`). Em AP-insuficiente com X pago e Y sem pagamento, o resultado é `retorno_para_interesse` (E11-03, A-3). Para os critérios de estoque, P1 e P2 têm limite: P1 11 e P2 12.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §8.2 3.7, cenário 15 | positivo | AP-insuficiente; X pago, Y sem pagamento | `iniciar_apuracao` | a rodada em `interesse`; a auditoria `rodada.voltar_para_interesse` com o motivo `pagamentos_insuficientes`. **Red esperado:** a rodada continua `pagamento` |
| A-2 | 17.5, T-22, cenário 56 | positivo | o A-1 | inspecionar as parcelas | as de A, P1 6 e P2 4, `ativa`, com a reserva igual à congelada e a sequência original; as de B `removida` (E11-02); os limites do estoque iguais (11 e 12); `total_reservado`: P1 6 e P2 4 |
| A-3 | Herdado E08 | positivo | AP-insuficiente, com A tendo 2 unidades pendentes em P1 na abertura (`montar_arranjo(pendente_a_p1=2)`: a parcela ficou `pendente`, com a parte congelada só no pedido) | `iniciar_apuracao` | a parcela de A em P1 `ativa`, com reservado 6 e pendente 2; mesma sequência; reservado + pendente ≤ original |
| A-4 | Cenário 103, §5.2 | positivo | o A-1 | inspecionar a parcela de A em P2 (estava na caixa 1, invalidada) | `ativa`, com reservado 4; nenhuma `RestauracaoDeCaixa`; não passou pela fila |
| A-5 | §8.2 3.7, cenário 15 | positivo | o A-1 | inspecionar os reembolsos | um `Reembolso` integral de X com a chave `minimo:<apuracao>:<X>`, motivo `minimo_nao_atingido`, produtos 80,00, serviço 4,00 e frete 10,35; uma obrigação de 94,35 financiada pela custódia; nenhuma `ParcelaDeDevolucao` (aguarda autorização) |
| A-6 | Infra 3.1, herdado E09 | positivo | o A-1 | `frete_do_ciclo(ciclo)` e `ApuracaoNoLivro` | sem `ApuracaoNoLivro`; todos os campos `None` |
| A-7 | §12, E06-06 | positivo | o A-1 | inspecionar as notificações | A recebe um `retorno_para_interesse` com a chave `retorno_para_interesse:apuracao:<apuracao>:<A>`, o corpo com "os pagamentos confirmados não atingiram o mínimo", "continuam reservados" e 94,35, sem o valor do mínimo; B recebe só o `itens_cancelados` da E11-02; nenhum aviso com a chave `retorno_para_interesse:<ciclo>` |
| A-8 | R-5, 17.5 | positivo | o A-1 com um pendente antigo de C de 3 unidades em P1, de sequência anterior a todas | `iniciar_apuracao` | C recebe 3 reservadas de P1 pelo estoque liberado por B (limite 11: A 6 + C 3 = 9); a parcela de C `ativa` |
| A-9 | Cenário 57, T-22 | positivo | o A-8 | `total_reservado` de cada produto | P1 9 ≤ 11, P2 4 ≤ 12; nenhuma parcela com duas reservas |
| A-10 | Conferência do estoque | negativo | o A-1, com o limite de P1 forçado a 5 no banco antes da apuração (abaixo da reserva congelada de A) | `iniciar_apuracao` | `RuntimeError`; nada gravado: sem `ApuracaoFinal`, Y `aguardando_pagamento`, as parcelas de B intactas, a rodada em `pagamento` |
| A-11 | Cenário 16, 56 | positivo | o A-1 | um interesse novo de C em P1; `iniciar_fechamento` pelo administrador com o mínimo atingido | aceitos; um ciclo novo (número 2); a obrigação de X continua pendente de autorização |
| A-12 | Cenário 16, §8.2 | positivo | o A-11, depois a abertura do pagamento do ciclo 2 | inspecionar os pedidos | pedidos novos do ciclo 2; o pedido X do ciclo 1 intacto, com o reembolso integral; nenhuma reserva duplicada |
| A-13 | §8.2, requisito derivado | positivo | o A-12; depois um pagamento aprovado para a referência de X (ciclo 1) | processar o aviso | devolução integral do pagamento (pedido do ciclo 1, já pago: `duplicidade`); nada muda nos pedidos do ciclo 2 |
| A-14 | 17.11 | positivo | o A-1 | alterar o mínimo, o múltiplo de P2 e o limite de P1 pelo administrador | aceitos (a rodada em interesse) |
| A-15 | T-21 | concorrência | AP-insuficiente; X pago | a apuração pausada depois de restaurar as reservas, antes do commit; `adicionar_interesse(C, P1, 5)` em paralelo | a adição espera a apuração; depois, C recebe a reserva até o livre (11 − 6 = 5); o total reservado ≤ 11 |
| A-16 | Herdado E06 | negativo | uma rodada em `pagamento` | `voltar_para_interesse(rodada, motivo="minimo_nao_atingido")` | `TransicaoRecusada("fora_de_fechamento_encerrado")`: os motivos da E06 continuam exigindo o fechamento encerrado |
| A-17 | Regra 2 | positivo | AP-insuficiente; X pago; A suspenso antes da apuração | `iniciar_apuracao` | as parcelas de A não são restauradas; o reembolso integral de X registrado; a auditoria registra as parcelas e o motivo |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-14, A-16 e A-17 | `tests/tecnicos/test_apuracao_retorno.py` |
| A-15 | `tests/tecnicos/test_apuracao_retorno.py`, com transações PostgreSQL reais |
