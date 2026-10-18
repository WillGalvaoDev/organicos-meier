# E05-02 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As parcelas pendentes são criadas pela `ParcelaFactory`, com situação `pendente`, reservada 0 e pendente igual à original, salvo indicação. A rodada é do fornecedor `X`, está em `interesse` e tem o produto `P` (unidade, incremento 1).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 75, T-30 | positivo | estoque de `P` com limite 10; A com 6 pendentes (sequência menor) e C com 8 | `alocar_pendentes(X)` dentro de `transaction.atomic()` | devolve 10; A fica `ativa` com 6 reservados e 0 pendente; C fica `ativa` com 4 reservados e 4 pendentes; sequências e originais inalterados; nenhuma parcela nova; uma auditoria `interesse.alocar_pendentes` com autor `SISTEMA` e `[[A, 6], [C, 4]]` |
| A-2 | Cenário 76 | positivo e negativo | o estado final do A-1 | D adiciona 3; o administrador altera o limite para 13; D adiciona 1 | a primeira adição de D é recusada com "esgotado"; a alteração do limite dá 3 a C, que fica com 7 reservados e 1 pendente; a segunda adição de D também é recusada; total reservado 13 |
| A-3 | Cenário 101 | positivo | limite 10; D com 3 reservados; outros com 7; C com 4 pendentes | `reduzir_interesse(D, P, "3")` | C recebe 3 na mesma transação; D fica `removida`; total reservado continua 10; C fica com 1 pendente |
| A-4 | Spec §5.2, R-5 | positivo e negativo | limite 10 com 4 reservados; C com 4 pendentes (estado criado por fábrica) | `adicionar_interesse(E, P, "4")`; depois `adicionar_interesse(E, P, "2")` | a primeira é recusada com `EstoqueInsuficiente` e "Há apenas 2 unidade disponível.", e nada é gravado (C continua com 4 pendentes); a segunda dá 4 a C antes e 2 a E, na mesma transação; total reservado 10 |
| A-5 | Spec da fatia | positivo | sem limite; A com 5 pendentes | E adiciona 2 | A recebe as 5 antes; E recebe 2 |
| A-6 | Cenário 102, T-46 | negativo | fornecedor `Y` com rodada em `interesse`, produto `Q` sem limite e pendentes em `Q`; X sem pendentes | `alocar_pendentes(X)`; incluo um produto novo na rodada de X | as pendentes de `Q` não mudam; nenhuma reserva aparece na rodada de X a partir de parcelas de Y |
| A-7 | Spec da fatia | positivo | rodada de X sem `P` no estoque; A com 4 pendentes em `P` | `alocar_pendentes(X)`; depois incluo `P` com limite 3 | a primeira chamada não altera nada; a inclusão aciona o receptor de `estoque_alterado`; A fica com 3 reservados e 1 pendente |
| A-8 | Spec da fatia | negativo | A com 4 pendentes; limite 10 sem reservas | coloco a rodada em `fechamento_encerrado`, em `pagamento` e depois sem rodada ativa, e chamo `alocar_pendentes(X)` em cada caso | devolve 0; nada é gravado nem auditado; nenhuma exceção |
| A-9 | Spec da fatia | positivo | rodada em `fechamento`; limite 10 sem reservas; A com 4 pendentes | `alocar_pendentes(X)` | A recebe 4 |
| A-10 | Spec da fatia | positivo | incremento 4; limite 10; A com 12 pendentes | `alocar_pendentes(X)` | A recebe 8 e fica com 4 pendentes |
| A-11 | Spec da fatia | negativo | uma parcela `em_pedido` com 2 reservados e 2 pendentes; limite 10 | `alocar_pendentes(X)` | a parcela `em_pedido` não muda |
| A-12 | Cenário 78 | positivo | o estado final do A-1 | `alocar_pendentes(X)` de novo | devolve 0; nada é gravado; nenhuma auditoria nova |
| A-13 | Spec da fatia | negativo | limite 10 com 2 reservados; A com 4 pendentes | `alterar_estoque(admin, estoque, "8")` (redução) | o receptor não aloca; A continua com 4 pendentes; total reservado 2 |
| A-14 | Spec da fatia | negativo | — | chamo `alocar_pendentes` fora de transação | `TransactionManagementError` |
| A-15 | T-31, cenário 78 | concorrência | limite 6; A com 4 pendentes | em threads: (a) `alocar_pendentes(X)` segura as travas enquanto E adiciona 4; (b) E adiciona 4 e segura as travas enquanto `alocar_pendentes(X)` espera | nos dois casos: A com 4 reservados; E recusado com "Há apenas 2 unidade disponível."; total reservado 4; nenhuma parcela duplicada; nenhum deadlock |
| A-16 | Cenário 101, T-46 | concorrência | limite 10, cheio; D com 3 reservados; C com 4 pendentes | em threads, D reduz 3 enquanto E adiciona 3 | C recebe as 3 liberadas; E é recusado; total reservado 10, em qualquer ordem |
| A-17 | E05-R01, E03-05 | negativo e positivo | estoque de `P` sem limite; (i) sem reservas; (ii) A com 3 reservados; noutros casos, os pares de controle (`"6"` → `"10"`, `"6"` → sem limite, `"6"` → `"3"`), sem reservas e com C com 2 pendentes | (i) e (ii): `alterar_estoque(admin, estoque, "10")`; (iii) com o estado de (ii), `alterar_estoque(admin, estoque, "2")`; os pares de controle; um espião em `apps.interesses.receptores._alocar_produto` | (i) e (ii): limite 10, nenhuma exceção, uma auditoria `estoque.alterar` com `anterior` nulo, e o espião não é chamado; (iii) `EstoqueAbaixoDoReservado`, com o limite ainda sem limite e nada gravado; nos pares: o espião é chamado em `"6"` → `"10"` e em `"6"` → sem limite, e C recebe 2 nesses dois; não é chamado em `"6"` → `"3"`; antes da correção, (i) e (ii) falham com `TypeError` (Red) |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-14 | `tests/tecnicos/test_interesses_fila.py` |
| A-1, A-2, A-3, A-6 e A-12 | também marcados `acceptance`, com os comentários `cenário 75`, `cenário 76`, `cenário 101`, `cenário 102` e `cenário 78` |
| A-15, A-16 | `tests/tecnicos/test_interesses_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`); tratamento da correção E05-R04 da E05-01 |
| A-17 | `tests/tecnicos/test_interesses_fila.py`, com as provas `test_sem_limite_para_finito` e `test_controle_transicoes_estoque` do revisor incluídas literalmente, além do espião e dos casos (iii) e de C |
