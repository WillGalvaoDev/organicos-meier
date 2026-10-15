# E01-04 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com falha observada (Red). Testes com banco usam Postgres real.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 5 | positivo | um modelo de teste que herda de `RegistroSoInsercao` | crio e salvo um objeto novo | o registro existe no banco |
| A-2 | Infra 5 | negativo | um objeto já gravado desse modelo | altero um campo e salvo | `RegistroImutavel`, e o banco continua com o valor original |
| A-3 | Infra 5 | negativo | um objeto já gravado | chamo `delete()` | `RegistroImutavel`, e o registro continua existindo |
| A-4 | Infra 5 | negativo | registros gravados | chamo `QuerySet.update()`, `QuerySet.delete()` ou `bulk_update()` | `RegistroImutavel` em cada caso, sem mudança no banco |
| A-5 | Infra 4.9 e 5 | negativo | a tabela do modelo de teste com a proteção instalada | executo `UPDATE` e depois `DELETE` por SQL direto | o banco recusa as duas operações, e os registros continuam iguais |
| A-6 | Spec §14 | positivo | um usuário e um objeto de referência | chamo `registrar_auditoria` com ação, alterações e motivo | a entrada tem autor, ação, momento (relógio da E01-03), motivo, alterações e referência ao objeto |
| A-7 | Spec §14, §7.2 | positivo | uma ação sem motivo exigido, executada pelo sistema | chamo `registrar_auditoria` sem motivo e com autor sistema | a entrada é gravada com motivo vazio e autor identificado como sistema |
| A-8 | Infra 5 | negativo | uma entrada de auditoria gravada | tento alterar ou apagar pela aplicação e por SQL direto | `RegistroImutavel` na aplicação e recusa do banco no SQL |
| A-9 | Spec §15 | negativo | alterações com uma chave que contém `senha`, `password`, `token`, `secret` ou `chave_api`, inclusive em outra caixa (`Token_Pagamento`), como parte do nome (`senha_hash`) ou num dicionário aninhado | chamo `registrar_auditoria` | a função recusa e nada é gravado |
| A-10 | Spec §15 | positivo | uma entrada de auditoria de um usuário (modelo de `get_user_model()`) | removo esse usuário | a remoção conclui sem erro, a entrada continua existindo e mantém o tipo `usuario` e o identificador original |
| A-11 | Spec da fatia | positivo | uma transação que chama `registrar_auditoria` e depois falha | a transação é desfeita | a entrada não existe |
| A-12 | Spec da fatia | positivo | três entradas | gravo com `bulk_create` | as três existem |
| A-13 | Spec da fatia | negativo | inserções por SQL direto com tipo `usuario` sem identificador, tipo `sistema` com identificador e tipo desconhecido | executo cada uma | o banco recusa as três |
| A-14 | Spec da fatia | negativo | autor ausente, ou ação vazia | chamo `registrar_auditoria` | a função recusa e nada é gravado |

O modelo de teste de A-1 a A-5 fica no app `tests/apoio`, com a proteção instalada pela mesma operação de migração usada pela aplicação.

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-4, A-12 | `tests/tecnicos/test_nucleo_so_insercao.py::test_aplicacao_*` |
| A-5 | `tests/tecnicos/test_nucleo_so_insercao.py::test_trigger_*` |
| A-6 a A-11, A-13, A-14 | `tests/tecnicos/test_nucleo_auditoria.py` |
