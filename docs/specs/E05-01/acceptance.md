# E05-01 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Salvo indicação, a rodada é do fornecedor `F`, está em `interesse` e tem o produto `P` (unidade, incremento 1, R$ 10,00) incluído. Os compradores são `ativa`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §5 | positivo | estoque de `P` com limite 10 | `adicionar_interesse(A, P, "4")` | uma parcela `ativa` com original, reservada e pendente iguais a 4, 4 e 0; `ResumoDoInteresse(reservado=4, pendente=0)`; uma auditoria `interesse.adicionar` com parcela, produto, rodada e quantidade, sem nome nem e-mail |
| A-2 | Cenário 8 | positivo | sem limite | A adiciona 8; B adiciona 10; A adiciona 2; depois `reduzir_interesse(A, P, "2")` | as sequências seguem A(8) < B(10) < A(2); a redução zera a parcela A(2), que passa a `removida`; A(8) fica intacta; reservado de A é 8 |
| A-3 | Spec §5 | positivo | A com parcelas de 2, 3 e 4, nessa ordem | `reduzir_interesse(A, P, "5")` | a de 4 fica `removida`; a de 3 fica com 2 reservados; a de 2 fica intacta; `quantidade_original` e `sequencia` das três não mudam; uma auditoria `interesse.reduzir` com os ids das parcelas tocadas |
| A-4 | Spec §5 | negativo | limite 10 e B com 7 reservados | A adiciona 4; noutro caso, com limite 0, A adiciona 1 | `EstoqueInsuficiente` com "Há apenas 3 unidade disponível." e, no segundo, "Este produto está esgotado nesta rodada."; nenhuma parcela e nenhuma auditoria novas |
| A-5 | Cenários 63, 85 e 109, T-26, T-50 | negativo e positivo | produtos: kg a R$ 12,00 com incremento 0,5; L com 0,5; unidade com 1; kg com 0,25; unidade com 2; caixa com 1 | `adicionar_interesse` com 1,5 e 1,2 (kg 0,5); 1,5 e 1,2 (L); 2 e 2,5 (unidade 1); 0,75 (kg 0,25); 12 e 12,5 (unidade 1); 4 e 3 (unidade 2); 1,25 (kg 0,25); 3 e 1,5 (caixa); depois `1.5` como `float`, `"abc"`, `"-1"`, `"0"` e `"1000000000.000"` | aceitos: 1,5, 1,5, 2, 0,75, 12, 4, 1,25 e 3; recusados com `QuantidadeInvalida` e sem gravar: 1,2, 1,2, 2,5, 12,5, 3, 1,5, o `float`, o texto, o negativo e o zero; o último com a mensagem de capacidade; na parcela de 1,5 kg, o subtotal calculado por `calcular_subtotal` é R$ 18,00 |
| A-6 | Spec §5 | negativo | A com 4 reservados | `reduzir_interesse(A, P, "5")`; `reduzir_interesse(A, P, "0.5")` | `ReducaoAcimaDoReservado` com "A redução passa da quantidade reservada (4)."; `QuantidadeInvalida`; nada alterado |
| A-7 | Spec da fatia | positivo | A com 4 reservados | `definir_interesse(A, P, "6")`; depois `"6"` de novo; depois `"1"`; depois `"0"` | a primeira cria uma parcela de 2; a segunda não grava nada, nem auditoria; a terceira reduz 5, a partir da parcela mais recente; a quarta deixa todas `removida`; o resumo final é reservado 0 |
| A-8 | Spec §2, E02-10 | negativo | um comprador suspenso, uma conta de fornecedor e o administrador | `adicionar_interesse`, `reduzir_interesse` e `definir_interesse` | `PermissionDenied` em todos; nada gravado |
| A-9 | Spec §7 | negativo e positivo | rodadas em cada etapa ativa e um fornecedor sem rodada ativa | `adicionar_interesse(A, P, "1")` | aceito em `interesse` e `fechamento`; `InteressesBloqueados` com `etapa_bloqueada` em `fechamento_encerrado`, `pagamento` e `aguardando_fornecedor`, e com `sem_rodada_ativa` sem rodada; sempre a mesma mensagem |
| A-10 | Spec da fatia | negativo | um produto `R` de `F` fora do estoque da rodada; um produto `S` de outro fornecedor `G`, cuja rodada em `interesse` não inclui `S` | `adicionar_interesse` com `R` e com `S` | `ProdutoForaDaRodada` nos dois; nada gravado em `F` nem em `G` |
| A-11 | E03-03 D-1 | positivo | `P` com `disponivel=False` | A adiciona 2 e reduz 1 | as duas operações são aceitas |
| A-12 | Spec da fatia | negativo | — | chamo `travar_rodada_para_interesses` fora de transação | `TransactionManagementError` |
| A-13 | Cenário 3, Infra 5 | concorrência | limite 1 | duas adições de 1, de compradores diferentes, em threads; a primeira segura as travas até a segunda aparecer esperando trava em `pg_stat_activity` | uma aceita e uma `EstoqueInsuficiente`; total reservado 1; uma única parcela |
| A-14 | Cenário 108, T-49 | concorrência | incremento 1 e A sem parcelas | (a) `alterar_incremento(admin, P, "2")` segura as travas e, enquanto isso, A adiciona 3; (b) A adiciona 3 e segura as travas, enquanto isso `alterar_incremento(admin, P, "2")` | em (a), a adição é recusada com `QuantidadeInvalida`, porque foi validada contra o incremento 2; em (b), a alteração é recusada com `IncrementoIncompativel("quantidade")`; nos dois casos, toda parcela fica múltipla do incremento vigente |
| A-15 | Spec da fatia | concorrência | A ativa | `suspender(admin, A)` segura a trava da conta e, enquanto isso, A adiciona 1; depois, a suspensão confirma | a adição espera e é recusada com `PermissionDenied`; nenhuma parcela de A |
| A-16 | Spec da fatia | concorrência | limite 10 | 10 threads, cada uma com `adicionar_interesse` de 2, de compradores diferentes | exatamente 5 aceitas; total reservado 10; nenhum deadlock; sequências distintas |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-12 | `tests/tecnicos/test_interesses_servicos.py` |
| A-2 | também marcado `acceptance`, com o comentário `cenário 8` |
| A-5 | também marcado `acceptance`, com os comentários `cenários 63, 85, 109` |
| A-13 a A-16 | `tests/tecnicos/test_interesses_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`); o A-13 com o comentário `cenário 3` e o A-14 com `cenário 108` |
