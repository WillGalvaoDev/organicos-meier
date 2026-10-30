# E11-04 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação. Arranjo AP como na E11-01 (`acceptance.md`). Em AP-viável com X pago e Y sem pagamento, as duas caixas de P2 são invalidadas (E11-03, A-1). A tem 4 unidades de P2 na caixa 1.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §8.2 3.4, §9.2, cenário 13 | positivo | AP-viável; X pago, Y sem pagamento | `iniciar_apuracao` | um `Reembolso` de X com a chave `caixa:<apuracao>:<item P2>`, motivo `caixa_invalidada`, tipo `parcial`, autor vazio (sistema), produtos 20,00, serviço 1,00 e frete 2,59; um `ItemReembolsado` de 4 unidades e 20,00; uma `ObrigacaoComComprador` de 23,59, financiada pela custódia de A no ciclo (sem cobertura zero). **Red esperado:** nenhum reembolso |
| A-2 | §9.2 | positivo | o A-1 | inspecionar as devoluções | nenhuma `ParcelaDeDevolucao` (a execução aguarda a autorização); a obrigação aparece em "Pendentes de autorização" da lista de devoluções (E10-07) |
| A-3 | §5.2, Q-1, cenário 74 | positivo | o A-1 | inspecionar a parcela de A em P2 | `pendente`, com pendente 4, reservado 0 e a mesma sequência; uma `RestauracaoDeCaixa` com a `ParcelaNoPedido` da caixa 1 de A e quantidade 4; a parcela de A em P1 continua `em_pedido` com 6. **Red esperado:** a parcela de P2 continua `em_pedido` |
| A-4 | Cenário 74, §5.2 | positivo | o A-3 | `total_reservado(P2)` e `alocar_pendentes(F)` | o total reservado de P2 não inclui as 4 de A; `alocar_pendentes` devolve zero (rodada em `pagamento`); a parcela continua pendente com reserva zero |
| A-5 | Cenário 53, §5.2 | positivo | o A-1 | inspecionar a parcela de A antes de qualquer autorização de devolução | a restauração já feita, sem depender do reembolso |
| A-6 | §7.1 | positivo | o A-1 | comparar o pedido X, os itens e as `ParcelaNoPedido` | iguais e sem linha nova |
| A-7 | §6.3, cenário 13 | positivo | o arranjo do E11-03 A-6 (caixa 1: A 4 e C 2; caixa 2: A 2 e B 4; A e C pagam) | `iniciar_apuracao` | só a parte de A da caixa 2 é estornada e restaurada (2 unidades): um reembolso de 2 unidades do item P2 de A; a parcela de A de 2 (sequência 3) `pendente` com 2; a parcela de A de 4 (caixa 1) continua `em_pedido` com 4; C sem reembolso e sem restauração |
| A-8 | Regra 3 | positivo | um arranjo com P2 de múltiplo 6 e parcelas C 4 e A 4, nessa ordem (caixa 1: C 4 e A 2; caixa 2: A 2 e B 4); A e C pagam, B não | `iniciar_apuracao` | a parcela de A de 4 (cruza as caixas 1 e 2) passa a `pendente`, com pendente 2 e reservado 0; a parte da caixa 1 continua só no pedido; reservado + pendente ≤ original |
| A-9 | T-20, T-32, cenário 55 e 78 | negativo | o A-1 | executar de novo o passo de estorno e restauração da mesma apuração, pela função interna | nenhuma `RestauracaoDeCaixa` nova; a parcela com pendente 4 (não 8); nenhum `Reembolso` nem obrigação nova; a sequência igual. **Red esperado:** a segunda execução restaura de novo |
| A-10 | Regra 4 | positivo | AP-viável; X pago; A suspenso depois de pagar, antes da apuração (o pedido pago é preservado, E08-06) | `iniciar_apuracao` | o reembolso de 23,59 registrado; nenhuma `RestauracaoDeCaixa` para a parcela de A; a auditoria registra a parcela não restaurada e o motivo |
| A-11 | §12, E04 | positivo | o A-1 | inspecionar as notificações de A | um `itens_cancelados` com o título "Itens em caixa incompleta: F", com "4 un de P2", o valor 23,59, a menção à autorização do administrador e à fila de pendentes, o link `/pedidos/<X>/` e a chave `itens_cancelados:caixa:<apuracao>:<A>`. **Red esperado:** nenhuma notificação |
| A-12 | Escopo | negativo | AP-insuficiente; X pago, Y sem pagamento (resultado `retorno_para_interesse`) | `iniciar_apuracao` | nenhum reembolso `caixa_invalidada`, nenhuma `RestauracaoDeCaixa` e nenhum aviso de caixa incompleta |
| A-13 | Caso-limite | positivo | um arranjo em que todas as unidades pagas de A estão em caixas invalidadas e o resultado é `valida` pelos outros pagantes | `iniciar_apuracao` | os reembolsos dos itens de A completam exatamente os produtos, o serviço e o frete de A; nenhum componente passa do registrado |
| A-14 | Concorrência | concorrência | AP-viável; X pago | a apuração pausada depois da restauração, antes do commit; a suspensão de A em paralelo | a suspensão espera a apuração; depois, a parcela de A em P2 `removida` (E05-07); o reembolso continua registrado |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-13 | `tests/tecnicos/test_apuracao_viavel.py` |
| A-14 | `tests/tecnicos/test_apuracao_viavel.py`, com transações PostgreSQL reais |
