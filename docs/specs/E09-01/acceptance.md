# E09-01 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:** os fornecedores A e B, com as rodadas `rA` e `rB` e os ciclos `cA` e `cB`, e os compradores X e Y. As contas são criadas por `conta(...)`. Os saldos iniciais são postos com movimentos F1, de exterior para custódia (por exemplo, `custodia(rA, cA, X, produtos)` com R$ 100,00).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 3.1 | positivo | o arranjo, sem saldos | `lancar` F1 com R$ 100,00 de produtos, R$ 5,00 de serviço e R$ 20,00 de frete para X em `rA` | um movimento com três transferências; os saldos das três custódias são 100,00, 5,00 e 20,00; `saldo_total_esperado()` é 125,00; o movimento tem tipo, autor `SISTEMA`, momento, justificativa, origem e chave |
| A-2 | Infra 3.1, E01-04 | negativo | o movimento do A-1 | `save()`, `delete()`, `update()` em lote e `UPDATE`/`DELETE` por SQL em movimento e transferência | `RegistroImutavel` no ORM e erro de integridade da trigger no SQL; nada muda |
| A-3 | §16 nº 32, T-11 | negativo | custódia de produtos de X em `rA` com 100,00 e `despesas_a_cobrir` com −1,00 | `lancar` de `custodia(rA…produtos)` para `despesas_a_cobrir` (uma tarifa paga com dinheiro do fornecedor A) | `MovimentoProibido("fluxo_nao_permitido")`; nenhuma escrita; saldos iguais |
| A-4 | §16 nº 32, T-11 | negativo | `obrigacao_fornecedor(A, rA)` com 100,00 e uma obrigação com comprador da rodada `rB` | `lancar` F9 de `obrigacao_fornecedor(A, rA)` para essa obrigação | `MovimentoProibido`; nenhuma escrita |
| A-5 | §16 nº 32, T-11 | negativo | `obrigacao_fornecedor(A, rA)` com 100,00 | `lancar` para `frete(rB)`, para `reserva`, para `receita_servico(rA)` e para `obrigacao_fornecedor(B, rB)`, um caso parametrizado por destino | cada um recusado com `MovimentoProibido`; nenhuma escrita |
| A-6 | P-2 | negativo | custódia de X em `rA` com 100,00 de produtos | F8 para uma obrigação de Y em `rA`; e F6 com origem na custódia de produtos (componente trocado) | os dois recusados com `MovimentoProibido` |
| A-7 | P-2, ressalva | positivo | `obrigacao_fornecedor(A, rA)` com 100,00 e uma obrigação de X em `rA` | F9 com 25,00 | aceito; os saldos são 75,00 e 25,00 |
| A-8 | Infra 3.2 | positivo | os fluxos F1 a F15, cada um com o seu arranjo mínimo | `lancar` de cada um | todos aceitos, com os saldos esperados; um teste parametrizado por número de fluxo |
| A-9 | AGENTS.md §6 | negativo | `receita_servico(rA)` com 10,00 | `lancar` F13 com 10,01; e um movimento com duas transferências, a primeira válida e a segunda que deixa uma conta negativa | `SaldoInsuficiente` nos dois; no segundo, nenhuma das duas transferências é gravada |
| A-10 | Decisão técnica | positivo | `despesas_a_cobrir` com 0,00 | F4 com 1,50 | aceito; o saldo é −1,50 (o único saldo negativo permitido) |
| A-11 | Infra 5 | negativo | o arranjo | valores `0`, `-1.00`, `1.001` e `1.5` como `float`; transferência com `de == para`; lista vazia; autor administrador com justificativa vazia ou só com espaços | `MovimentoInvalido` com o código de cada caso; nenhuma escrita |
| A-12 | Idempotência | positivo e negativo | o movimento do A-1 com a chave `k` | o mesmo `lancar` de novo com `k`; depois `lancar` com `k` e um valor diferente | o primeiro devolve o mesmo movimento, sem registro novo e com saldos iguais; o segundo levanta `MovimentoConflitante`, sem escrita |
| A-13 | Infra 3.2 | positivo | o arranjo; um administrador | `lancar` F11 de `reserva` para `despesas_a_cobrir`, com o administrador como autor e uma justificativa | o movimento guarda o autor e a justificativa; uma `EntradaAuditoria` com a ação `financeiro.movimento`, o tipo, o valor e as contas, sem dados pessoais |
| A-14 | AGENTS.md §6 | concorrência | `receita_servico(rA)` com 10,00 | duas transações em paralelo, cada uma com F13 de 6,00 | uma aceita e a outra `SaldoInsuficiente`; o saldo final é 4,00; em qualquer ordem |
| A-15 | Idempotência | concorrência | o arranjo | duas transações em paralelo com o mesmo `lancar` (mesma chave e conteúdo) | um único movimento; as duas devolvem o mesmo; os saldos não dobram |
| A-16 | Ordem das travas | concorrência | `receita_servico(rA)` e `reserva` com saldo; `despesas_a_cobrir` negativa | duas transações em paralelo, cada uma com duas transferências F11 (de `receita_servico(rA)` e de `reserva` para `despesas_a_cobrir`), listadas em ordens opostas; cada uma pausa depois da primeira trava | as duas terminam, sem `deadlock detected`; os saldos refletem as duas |
| A-17 | Decisão técnica | negativo | o arranjo | `lancar` fora de transação | `TransactionManagementError`; nenhuma escrita |
| A-18 | E09-07, saldo de relatório | positivo | um F1 de 125,00 às 10:00 e um F3 de 1000,00 às 12:00 | `saldo_total_esperado(ate=11:00)` e `saldo_total_esperado()` | 125,00 e 1125,00 |

## Mapeamento para testes

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-13, A-17 e A-18 | `tests/tecnicos/test_financeiro_livro.py` |
| A-3 a A-6 | também `tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py`, pelo nível do livro-razão |
| A-14 a A-16 | `tests/tecnicos/test_financeiro_concorrencia.py` |

## Correção E09-R02 — guarda da ordem das travas (2026-10-22)

Valem a "Regra única de travas do financeiro" e a correção E09-R08, no `spec.md` desta fatia. Red esperado no código atual: o A-19 falha porque a trava fora de ordem é aceita, sem exceção.

**Arranjo:** três contas criadas nesta ordem, `c1`, `c2` e `c3`, com `pk` crescente e saldo semeado.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-19 | Correção R02 | negativo | o arranjo | numa transação, travar `c3` e depois `c1`; noutra, travar `c2` e depois `lancar` F11 de `c1` para `c3` | `OrdemDeTravasViolada` nas duas, antes de travar `c1`; nenhum movimento gravado; saldos iguais |
| A-20 | Correção R02 | positivo | o arranjo | numa transação, travar `c1`, `c3` e de novo `c1`; e `lancar` com as transferências entre `c1` e `c3` listadas em qualquer ordem; noutra, travar `c3`, terminar a transação e, numa transação nova, travar `c1` | aceitos: travar de novo uma conta já travada é permitido, e o registro começa vazio em cada transação mais externa, depois de commit e depois de rollback |
| A-21 | Correção R02 | positivo | o arranjo | a suíte inteira, com a guarda ativa | nenhum teste existente falha por `OrdemDeTravasViolada` depois da correção. Um teste que falhar por ela antes da correção é registrado como inversão encontrada, com o caminho, e corrigido pela regra única, sem desligar a guarda |

| Critério | Arquivo de teste |
|---|---|
| A-19 e A-20 | `tests/tecnicos/test_financeiro_livro.py` |
| A-21 | a suíte completa, com o resultado registrado no `review.md` |

## Correção E09-R10: a vida do registro da guarda (2026-10-22)

Valem a seção "Correções da revalidação da E09 sobre 2930ffd" do `spec.md` e a correção E09-R08. Os testes usam transações PostgreSQL reais (`transaction=True`), sem dublê de banco, exceto o A-27 (iii).

**Arranjo:** duas contas, `menor` e `maior` (por exemplo, `reserva` e `despesas_a_cobrir`), com `menor.pk < maior.pk`, conferido no próprio teste.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-22 | Correção R10 | positivo | o arranjo; um único objeto `escopo = transaction.atomic()` | `with escopo:` trava `maior` e termina com commit; um segundo `with escopo:` trava só `menor` | aceito, sem exceção. Repetir com a primeira execução terminando em rollback (exceção capturada fora do `with`): também aceito. **Red esperado:** `OrdemDeTravasViolada` |
| A-23 | Correção R10 | negativo | o arranjo; um único objeto `escopo` | `with escopo:` trava `menor` e `maior` e commita; um segundo `with escopo:` trava `maior` e depois pede `menor` | `OrdemDeTravasViolada` no pedido de `menor`, antes de travar. **Red esperado:** nenhuma exceção |
| A-24 | Correção R10 | positivo e negativo | o arranjo; uma função decorada com `@transaction.atomic` que trava as contas recebidas, na ordem em que as recebe | (i) chamar com `(maior,)` e depois com `(menor,)`; (ii) chamar com `(menor, maior)` e depois com `(maior, menor)` | (i) as duas chamadas aceitas; (ii) a primeira aceita, e a segunda levanta `OrdemDeTravasViolada` ao pedir `menor`. **Red esperado:** em (i), `OrdemDeTravasViolada` na segunda chamada; em (ii), nenhuma exceção |
| A-25 | Correção R10 | negativo | o arranjo | numa transação, um `atomic` interno trava `menor` e é desfeito por uma exceção capturada; depois a transação trava `maior` e pede `menor` | `OrdemDeTravasViolada` no pedido de `menor`. Controle no mesmo teste: depois do rollback do savepoint e antes de travar `maior`, outra conexão com `lock_timeout = '500ms'` consegue travar `menor`, o que mostra que a trava não está retida. **Red esperado:** nenhuma exceção |
| A-26 | Correção R10 | positivo | o arranjo | numa transação, um `atomic` interno trava `maior` e é desfeito por uma exceção capturada; depois a transação pede `menor` e, em seguida, `maior` | aceitos, sem exceção, porque a trava de `maior` foi liberada pelo savepoint. Variação aninhada, com o mesmo resultado: dois `atomic` internos, o de dentro trava `maior` e o de fora é desfeito. **Red esperado:** `OrdemDeTravasViolada` no pedido de `menor` |
| A-27 | Correção R10 | negativo e positivo | o arranjo | (i) numa transação, um `atomic` interno trava `maior` e termina sem erro; depois a transação pede `menor`. (ii) numa transação que trava `maior`, um `atomic` interno trava de novo `maior` e é desfeito; depois a transação pede `menor`. (iii) num `TestCase` do Django, o mesmo objeto `escopo` usado duas vezes, como no A-22 e no A-23 | (i) `OrdemDeTravasViolada`, porque a trava passou para o bloco de fora. (ii) `OrdemDeTravasViolada`, porque `maior` já estava travada antes do savepoint e continua retida. (iii) os resultados do A-22 e do A-23. **Red esperado:** em (iii), os do A-22 e do A-23. Os casos (i) e (ii) já passam no código atual e são declarados como regressão, sem Red inventado |

Depois dos A-22 a A-27, o A-21 é refeito: a suíte inteira roda com a guarda nova, e o resultado fica no `review.md`.

| Critério | Arquivo de teste |
|---|---|
| A-22 a A-26, A-27 (i) e (ii) | `tests/tecnicos/test_financeiro_livro.py` |
| A-27 (iii) | `tests/tecnicos/test_financeiro_livro.py`, numa classe `TestCase` |
