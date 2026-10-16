# E03-06 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As parcelas são criadas pela `ParcelaFactory`. Rodadas em etapas posteriores a `interesse` são criadas pela `RodadaFactory`. Os testes de concorrência usam `django_db(transaction=True)`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 105, T-48 | positivo | produto com incremento 0,5, múltiplo 3, parcelas `ativa` com 1,0 e 1,5 reservados e uma `pendente` com 2,0; rodada em `interesse` | altero o incremento para `0,25` | incremento `0.250`; as parcelas não mudam; auditoria `produto.alterar_incremento` |
| A-2 | Cenário 106, T-48 | negativo | o mesmo produto | altero o incremento para `1` | `IncrementoIncompativel` com código `quantidade`; nada gravado; nenhuma auditoria |
| A-3 | Cenário 106, T-48 | negativo | o mesmo produto, sem a parcela de 1,5 | altero o incremento para `2` | `IncrementoIncompativel` com código `multiplo`; nada gravado |
| A-4 | Q-6 | negativo | um produto sem múltiplo, com uma única parcela `pendente` de 0,75 (fila do fornecedor) e incremento 0,25 | altero o incremento para `0,5` | `IncrementoIncompativel` com código `quantidade` |
| A-5 | R-8 | negativo | a rodada em `interesse` | envio `0`, `-1`, `0,0001` e `abc` | `IncrementoInvalido`; erro no formulário; nada gravado |
| A-6 | Cenário 107, T-48 | negativo | a rodada em `fechamento`, `fechamento_encerrado`, `pagamento` e `aguardando_fornecedor`, e sem rodada ativa | altero o incremento pela rota e pelo serviço | 409 / `CondicoesCongeladas`; nada gravado |
| A-7 | Cenário 107, §5.1 | positivo | a rodada em `fechamento` | altero o preço pela edição geral (E03-03) | aceito |
| A-8 | Spec da fatia | positivo | um produto com uma parcela `removida` e nenhuma outra | altero o incremento para qualquer valor válido compatível com o múltiplo | aceito |
| A-9 | Spec da fatia | positivo | o mesmo valor atual | envio | nenhuma gravação nem auditoria |
| A-10 | Spec §4.4 | concorrência | a rodada em `interesse` | uma thread trava fornecedor e rodada, grava `fechamento` e confirma ao ver a outra conexão esperando por trava; `alterar_incremento` corre em outra thread | `CondicoesCongeladas`; incremento inalterado |
| A-11 | Infra 4.12 | concorrência | incremento 0,5, sem parcelas, rodada em `interesse` | uma thread trava fornecedor, rodada, produto e parcelas, insere uma parcela de 1,5 e confirma ao ver `alterar_incremento(1)` esperando | `IncrementoIncompativel`; incremento 0,5 |
| A-12 | Spec da fatia | concorrência | incremento 0,5 | duas alterações em paralelo, para 0,25 e 0,125 | duas auditorias, com o `anterior` da segunda igual ao `novo` da primeira |
| A-13 | Spec §2, §15 | negativo | um comprador e uma conta de fornecedor autenticados; um visitante anônimo | `GET` e `POST` da rota | 403 para os autenticados; anônimo redirecionado para `/entrar/`; nada gravado |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-9 | `tests/tecnicos/test_catalogo_incremento.py` (marcador `tecnico`, com o comentário `T-48`) |
| A-10 a A-12 | `tests/tecnicos/test_catalogo_incremento_concorrencia.py` (marcador `concorrencia`) |
| A-13 | `tests/tecnicos/test_catalogo_permissoes.py` |
| A-1 (cenário 105); A-2, A-3 (106); A-6, A-7 (107) | também marcados `acceptance`, com os números no comentário |
