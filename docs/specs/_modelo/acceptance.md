# <ID> — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §16 nº <n> | positivo | | | |
| A-2 | §16 nº <n> | negativo | | | |
| A-3 | T-<n> | concorrência | | | |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 | `tests/aceitacao/test_<id>.py::test_<nome>` |
