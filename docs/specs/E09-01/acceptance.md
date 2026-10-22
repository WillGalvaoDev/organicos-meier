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
