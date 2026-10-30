# E11-08 — Critérios de aceitação

Agente 1 (especificador). Arranjo FP como no `spec.md`. Depois do passo 7, as pendentes de P são:
- A: 6 unidades, sequência mais antiga;
- C: 8 unidades.

Valem as regras de "Verde de primeira" e "Correção" do `spec.md`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 75, T-30 | positivo | FP, com o limite de P em R2 igual a 10 | a inclusão de P no estoque de R2 | A com 6 reservadas e 0 pendentes, `ativa`; C com 4 reservadas e 4 pendentes, `ativa`; total reservado 10; as sequências originais |
| A-2 | Cenário 76, T-46 | positivo | o A-1 | `adicionar_interesse(D, P, 3)`; depois o limite de P alterado para 14 | a adição recusada ou limitada, sem reserva acima do estoque (§5); depois do aumento, C recebe as 4 restantes antes de qualquer reserva de D; total reservado ≤ 14 |
| A-3 | Cenário 77, T-33, T-47 | positivo | o A-1, com Q também em R2 e A reservando Q até o mínimo | o progresso, o início do fechamento e a abertura do pagamento de R2 | o progresso conta só as reservadas; o pedido de C tem 4 de P (as reservadas), sem as 4 pendentes; a parcela de C continua com 4 pendentes depois da abertura, para a rodada seguinte |
| A-4 | Cenário 78, T-31 | concorrência | FP, com o limite de P em R2 igual a 10 | a inclusão de P (que atende a fila) em paralelo com `adicionar_interesse(E, P, 5)` | em qualquer ordem: A 6 e C 4 reservadas antes de E; E com 0; total 10; nenhuma parcela duplicada |
| A-5 | Cenário 78 | positivo | o A-1 | `alocar_pendentes(F)` duas vezes | nenhuma mudança na segunda; total 10 |
| A-6 | Cenário 96, T-42 | positivo | o A-1 (limite 10, livre zero) | GET `carrinho/` como C; a consulta do histórico de C | "reservado: 4" e "pendente: 4" separados, também com o livre zero; outro comprador não vê as parcelas de C |
| A-7 | Cenário 97, T-43 | positivo | o A-1 | `remover_pendente(C, P, 2)`; depois `remover_pendente(C, P, 2)` | a pendência cai para 2 e depois para 0; as reservas de C (4) e de A (6) iguais; a sequência igual; o reembolso de C da apuração igual (valores e obrigação) |
| A-8 | Cenário 98, T-43 | negativo | o A-1 | `remover_pendente(C, P, 5)`; `remover_pendente(C, P, 0.5)` com incremento 1 | as duas recusadas, sem escrita |
| A-9 | Cenário 99, T-44 | negativo | FP, depois do passo 4 | a rota de remoção de pendentes com o `pk` de um `ItemDoPedido` de A em Q, ou com o produto Q (só `em_pedido`) | recusada; o pedido, a trigger e os registros financeiros iguais |
| A-10 | Cenário 100, T-45 | concorrência | FP, antes da inclusão de P em R2 | `remover_pendente(C, P, 4)` em paralelo com a inclusão de P com limite 10 | em qualquer ordem: reservado + pendente de C ≤ 8; total reservado ≤ 10; a quantidade removida nunca reservada |
| A-11 | Cenário 101, T-46 | concorrência | o A-1 (A 6 e C 4 reservadas, C 4 pendentes, limite 10). A faz o papel de D do cenário | `reduzir_interesse(A, P, 3)` em paralelo com `adicionar_interesse(E, P, 3)` | em qualquer ordem: C recebe as 3 liberadas antes de E (C com 7 reservadas e 1 pendente); E com 0; total reservado 10 |
| A-12 | Cenário 102, T-46 | negativo | FP; uma rodada de G em interesse com estoque livre de um produto de G | `alocar_pendentes(G)` | nenhuma pendente de F reservada |
| A-13 | Cenário 104, R-6 | positivo | uma variante de FP com o limite de P em R2 igual a 6 (A com 6 reservadas da fila, C com 8 pendentes sem estoque) e o mínimo de F alterado para 100,00 em R2 | o progresso de R2 e `iniciar_fechamento` | progresso de 60,00; o fechamento recusado por mínimo não atingido; as pendentes de C fora do progresso |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-3, A-5 a A-9, A-12 e A-13 | `tests/tecnicos/test_fila_ponta_a_ponta.py` |
| A-4, A-10 e A-11 | `tests/tecnicos/test_fila_ponta_a_ponta.py`, com transações PostgreSQL reais |
