# E14-03 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Endereço do apoio:** `Rua das Hortas, 100 — Méier, Rio de Janeiro/RJ`.
- **Contas:** admin, o comprador A (ativo), um comprador suspenso, a conta de fornecedor de F.
- **Carrinho:** A com interesse em P1 de F numa rodada em `interesse`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §11 | positivo | nenhum endereço | `definir_endereco_de_retirada(admin, "  Rua das Hortas, 100 — Méier, Rio de Janeiro/RJ  ")` | um registro com o texto sem os espaços externos, autor e instante; `endereco_vigente()` devolve esse registro; auditoria `retirada.definir_endereco` com o anterior vazio e o novo. **Red esperado:** a função não existe |
| A-2 | Regra 3 | positivo | o A-1 | definir `Rua Nova, 5` | dois registros; o vigente é o novo; o anterior intacto |
| A-3 | Regra 2 | negativo | o A-1 | o mesmo texto; `""`; `"   "`; 501 caracteres | `sem_alteracao`, `texto_invalido`, `texto_invalido` e `texto_invalido`, sem escrita; 500 caracteres é aceito |
| A-4 | Regra 1 | negativo | nenhum endereço | definir com o comprador A, com o fornecedor e com `None` | `PermissionDenied`, sem escrita |
| A-5 | Regra 7, herdado E05 | positivo | o A-1 | GET `carrinho/` como A | o grupo de F mostra "Retirada: Rua das Hortas, 100 — Méier, Rio de Janeiro/RJ". **Red esperado:** o carrinho não mostra endereço |
| A-6 | Regra 7 | positivo | nenhum endereço | GET `carrinho/` como A | "Retirada: endereço ainda não informado." |
| A-7 | Regras 8 e 9 | positivo | o A-1 | GET `regras/` como A, como o suspenso e como admin | 200, com o endereço, o link para `comunicados/`, a frase do prazo de sete dias e a de ocorrências sem substituição |
| A-8 | Regra 8, §2 | negativo | o A-1 | GET `regras/` como o fornecedor; como anônimo | 403 sem o endereço; o anônimo é levado ao login, e nenhuma resposta contém o endereço |
| A-9 | Regra 10 | positivo | — | GET `inicio/` como A e como admin; como o fornecedor | "Regras e retirada" para A e admin; ausente para o fornecedor |
| A-10 | Regras 5 e 6 | positivo | o A-2 | GET e POST de `administracao/retirada/endereco/` como admin | o GET mostra o vigente e o histórico com os dois registros (o mais recente primeiro); o POST de um texto novo dá 302 com "Endereço de retirada atualizado."; o POST de texto vazio dá 400 com a mensagem |
| A-11 | Regra 5 | negativo | — | a página e o POST como A, como o fornecedor e como anônimo | 403, 403 e login; nada gravado |
| A-12 | Casos-limite | positivo | endereço `Rua A, 1\r\nFundos <b>` | GET `regras/` e `carrinho/` | as duas linhas aparecem separadas; `<b>` aparece escapado |
| A-13 | Só inserção | negativo | o A-1 | `update` e `delete` do endereço pela aplicação e por SQL direto | recusados |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-4 e A-13 | `tests/tecnicos/test_endereco_de_retirada.py` |
| A-5 a A-12 | `tests/tecnicos/test_endereco_de_retirada_telas.py` |
