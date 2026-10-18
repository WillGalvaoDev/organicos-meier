# E05-07 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). A suspensão usa `suspender(admin, conta)` (E02-08). As rodadas estão em `interesse`, salvo indicação.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 19, Spec §2 | positivo | A com 4 de `P` (fornecedor X, limite 10) e 2 de `Q` (fornecedor Y); uma parcela `pendente` de 3 em `R` (X) | `suspender(admin, A)` | as três parcelas de A ficam `removida`, com reservado e pendente zero; sequências e originais inalterados; total reservado de `P` 0 e de `Q` 0; uma auditoria `interesse.remover_por_suspensao` com autor `SISTEMA` |
| A-2 | Cenário 19 | negativo | o estado do A-1 | `reativar(admin, A)` | nenhuma parcela de A volta a `ativa` ou `pendente`; uma nova adição de A cria uma parcela com sequência nova |
| A-3 | Spec §5.2 | positivo | `P` com limite 4, cheio pelas 4 de A; C com uma parcela `pendente` de 3 | `suspender(admin, A)` | C fica `ativa` com 3 reservados, na mesma transação; total reservado 3 |
| A-4 | Spec da fatia | positivo | A com 2 de `P`; a rodada de X em `fechamento_encerrado`; C com 2 pendentes | `suspender(admin, A)` | a parcela de A fica `removida`; C continua com 2 pendentes |
| A-5 | Spec da fatia | negativo | A com uma parcela `em_pedido` de `P` | `suspender(admin, A)` | a parcela `em_pedido` não muda; nenhuma auditoria `interesse.remover_por_suspensao` |
| A-6 | E02-08 | negativo | A com 4 de `P`; um `monkeypatch` faz `remover_interesses_do_comprador` levantar `RuntimeError` | `suspender(admin, A)` | a exceção chega a quem chamou; A continua `ativa`; a parcela continua `ativa` com 4; nenhuma auditoria da suspensão |
| A-7 | Spec da fatia | negativo | — | chamo `remover_interesses_do_comprador(conta, motivo="suspensao")` fora de transação; noutro caso, dentro de uma transação com `motivo="outro"` | `TransactionManagementError`; `ValueError` |
| A-8 | Spec da fatia | concorrência | A ativa | em threads: (a) A adiciona 2 e segura as travas enquanto `suspender` espera; (b) `suspender` segura a trava da conta enquanto A adiciona 2 | em (a), a parcela nova é removida pela suspensão; em (b), a adição é recusada com `PermissionDenied`; nos dois, A sem parcela `ativa` ao final |
| A-9 | Spec da fatia | concorrência | `P` com limite 4; A com uma parcela `pendente` de 4 | em threads: (a) `alocar_pendentes(X)` segura as travas enquanto `suspender(admin, A)` espera; (b) a ordem inversa | nos dois, A sem parcela `ativa` nem `pendente` ao final e total reservado 0; nenhum deadlock |
| A-10 | D-1, Spec §2 | positivo | A `ativa` com 4 de `P` (fornecedor X, limite 4, cheio pelas 4 de A), 2 de `Q` (fornecedor Y) e uma parcela `pendente` de 3 em `R` (X); C com uma parcela `pendente` de 2 em `P` | `remover(admin, A)` | as três parcelas de A ficam `removida`, com sequências e originais inalterados; C fica `ativa` com 2 reservados, na mesma transação; uma auditoria `interesse.remover_por_remocao_da_conta` com autor `SISTEMA`; A `removida` e o e-mail banido |
| A-11 | D-1, cenário 20 | negativo | A `ativa` com uma parcela `em_pedido` de `P` e uma `ativa` de `Q` | `remover(admin, A)` | a `em_pedido` não muda; a de `Q` fica `removida`; nenhuma parcela é apagada |
| A-12 | D-1 | negativo | A `suspensa`, cujos interesses já saíram na suspensão; uma conta de fornecedor `ativa` | `remover(admin, A)`; `remover(admin, fornecedor)` | as duas remoções são aceitas; nenhuma auditoria `interesse.remover_por_remocao_da_conta`; nenhuma parcela alterada |
| A-13 | D-1, E02-08 | negativo | A `ativa` com 4 de `P`; um `monkeypatch` faz `remover_interesses_do_comprador` levantar `RuntimeError` | `remover(admin, A)` | a exceção chega a quem chamou; A continua `ativa`; o e-mail não fica banido; a parcela continua `ativa` com 4 |
| A-14 | D-1 | concorrência | A `ativa` | em threads: (a) A adiciona 2 e segura as travas enquanto `remover(admin, A)` espera; (b) `remover` segura a trava da conta enquanto A adiciona 2 | em (a), a parcela nova é removida pela remoção da conta; em (b), a adição é recusada com `PermissionDenied`; nos dois, A sem parcela `ativa` ao final |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-7, A-10 a A-13 | `tests/tecnicos/test_interesses_suspensao.py` |
| A-1 e A-2 | também marcados `acceptance`, com o comentário `cenário 19` |
| A-11 | também marcado `acceptance`, com o comentário `cenário 20` |
| A-8, A-9, A-14 | `tests/tecnicos/test_interesses_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
