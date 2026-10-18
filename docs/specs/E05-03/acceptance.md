# E05-03 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As parcelas são criadas pela `ParcelaFactory`. O produto `P` é do fornecedor `X`, em unidade, com incremento 1.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 97, T-43 | positivo | A com uma parcela `ativa` de original 10, 6 reservados e 4 pendentes; B com 5 reservados | `remover_pendente(A, P, "2")`; depois `remover_pendente(A, P, "2")` | depois da primeira, A tem 6 reservados e 2 pendentes; depois da segunda, 6 e 0, e a parcela continua `ativa`; B, sequências e originais inalterados; duas auditorias `interesse.remover_pendente` |
| A-2 | Spec §5.2 | positivo | A com parcelas pendentes de 2 (sequência menor) e 3 | `remover_pendente(A, P, "4")` | a de 3 fica `removida`; a de 2 fica `pendente` com 1 |
| A-3 | Spec da fatia | positivo | A com uma parcela `pendente` de 4 | `remover_pendente(A, P, "4")` | a parcela passa a `removida`, com reservado e pendente zero |
| A-4 | Cenário 98, T-43 | negativo | A com 4 pendentes | remover `"5"`, `"1.5"`, `"0"`, `"-1"`, `"abc"` e `1.0` (`float`) | `RemocaoAcimaDoPendente` com "A remoção passa da quantidade pendente (4)." no primeiro e `QuantidadeInvalida` nos demais; nada gravado e nenhuma auditoria |
| A-5 | Spec §5.2 | positivo | A com 4 pendentes | com a rodada de X em `pagamento`, em `fechamento_encerrado` e sem rodada ativa, removo 1 | aceito nos três casos |
| A-6 | Cenário 99, T-44 | negativo | A com uma parcela `em_pedido` de 4 reservados e 2 pendentes, e nenhuma outra parcela | `remover_pendente(A, P, "2")` | `RemocaoAcimaDoPendente` (pendente 0 nas parcelas consideradas); a parcela `em_pedido` não muda |
| A-7 | Spec §2 | negativo | um comprador suspenso com uma parcela pendente criada por fábrica; uma conta de fornecedor | `remover_pendente` | `PermissionDenied`; nada gravado |
| A-8 | Spec da fatia | negativo | A com 4 pendentes; limite 10 com 2 reservados; nenhuma outra pendente | `remover_pendente(A, P, "4")` | total reservado continua 2; nenhuma auditoria `interesse.alocar_pendentes` |
| A-9 | Cenário 100, T-45 | concorrência | limite 10 sem reservas; A com uma parcela `pendente` de 6 | em threads: (a) `remover_pendente(A, P, "6")` segura as travas enquanto `alocar_pendentes(X)` espera; (b) `alocar_pendentes(X)` segura as travas enquanto `remover_pendente(A, P, "6")` espera | em (a): A `removida` e total reservado 0; em (b): A com 6 reservados, e a remoção é recusada com `RemocaoAcimaDoPendente` (pendente 0); nos dois: reservado + pendente ≤ original e total reservado ≤ limite |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-8 | `tests/tecnicos/test_interesses_remover_pendente.py` |
| A-1, A-4 e A-6 | também marcados `acceptance`, com os comentários `cenário 97`, `cenário 98` e `cenário 99` |
| A-9 | `tests/tecnicos/test_interesses_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`, comentário `cenário 100`) |
