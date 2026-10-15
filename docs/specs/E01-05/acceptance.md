# E01-05 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com falha observada (Red). Todos usam `django_db(transaction=True)` e o marcador `concorrencia`, contra Postgres real.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec da fatia | positivo | duas operações que devolvem `"a"` e `"b"` | executo em paralelo | recebo os resultados na ordem das operações, com `valor` igual a `"a"` e `"b"` |
| A-2 | Spec da fatia | positivo | duas operações que gravam o identificador da própria conexão | executo em paralelo | os identificadores são diferentes |
| A-3 | AGENTS.md §6 | concorrência | um contador de teste com valor 0 e duas operações que leem, esperam na barreira interna e gravam `valor + 1` sem trava | executo em paralelo | o valor final é 1 (atualização perdida reproduzida) |
| A-4 | AGENTS.md §6 | concorrência | o mesmo contador com valor 0 e duas operações que incrementam com `select_for_update` dentro de `transaction.atomic` | executo em paralelo, 20 vezes seguidas, reiniciando o contador | o valor final é 2 em todas as repetições |
| A-5 | Spec da fatia | negativo | uma operação que levanta `ValueError` e outra que devolve `"ok"` | executo em paralelo | o resultado da primeira traz a exceção `ValueError`, e o da segunda traz `"ok"` |
| A-6 | Spec da fatia | negativo | uma operação que espera numa barreira que nunca se completa | executo com tempo limite de 2 segundos | `TempoEsgotado` em até cerca de 2 segundos, identificando a operação pendente |
| A-7 | Spec da fatia | positivo | uma execução em paralelo concluída, com erro ou com tempo esgotado | o teste termina | não sobram conexões abertas pelas threads do utilitário (verificado pela contagem de conexões do usuário de teste no Postgres) |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1, A-2, A-5 a A-7 | `tests/tecnicos/test_apoio_concorrencia.py::test_utilitario_*` |
| A-3, A-4 | `tests/tecnicos/test_apoio_concorrencia.py::test_demonstracao_*` |
