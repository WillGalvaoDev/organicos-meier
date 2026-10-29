# E10-05 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:**
- O arranjo da E10-04: X pago por P1 e O1 de 31,25.
- A conciliação de `D` usa o provedor simulado real: saldo e movimentos de `listar_movimentos`, com `id_estorno`.
- O relógio está à 01:00 de `D + 1`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 3.5, Herdado E09 | positivo | O1 devolvida em `D` (parcela `concluida`, F15 `devolucao:<id>`) | `conciliar_dia(D)` | o `devolucao` de −31,25 com par; `sem_par = 0`; diferença 0,00; resultado `ok`. **Red esperado:** o `devolucao` divergente |
| A-2 | Infra 3.5 | negativo | um estorno concluído no simulador, por fábrica, sem parcela no sistema | `conciliar_dia(D)` | `divergencia_na_conciliacao` com a chave do `id_movimento`; nenhum alerta crítico |
| A-3 | Infra 4.7 | positivo | o A-12 da E10-04: a parcela `elegivel_excepcional`; depois, no simulador, um estorno de 31,25 do mesmo pagamento é concluído (o caso de `recusar_mas_processar` com conclusão depois da verificação) | `conciliar_dia(D)` e depois `processar_chamadas()` | na conciliação: divergência do movimento, `devolucao_concluida_tardiamente` crítico com a parcela e o valor, e `verificar_estornos` agendada. Depois da tarefa: a parcela `concluida`, com o `id_estorno` adotado e o F15; os alertas elegível e tardio resolvidos |
| A-4 | Infra 4.7 | positivo | a parcela em `concluida_fora_da_plataforma` (E10-06) e depois o estorno tardio concluído no simulador | `conciliar_dia(D)` | `devolucao_concluida_tardiamente` crítico, com `devolvida_em_dobro = true`; nenhum lançamento novo no livro; a parcela continua `concluida_fora_da_plataforma` |
| A-5 | Caso-limite | positivo | estorno concluído às 23:50 de `D`, com o `concluir` da parcela às 00:10 de `D + 1` e o saldo com `referente_a` às 23:55 | `conciliar_dia(D)` à 01:00 | `sem_par = 0` no dia; diferença 0,00 (o estorno sem par no instante `t` compensa a saída que o livro ainda não tinha) |
| A-6 | Caso-limite | positivo | duas obrigações de 31,25 de X, devolvidas por dois estornos | `conciliar_dia(D)` | os dois `devolucao` pareados, cada um pelo seu `id_estorno`; `ok` |
| A-7 | Infra 3.5 | positivo | uma parcela confirmada de forma excepcional em `D` (E10-06), sem nada no provedor | `conciliar_dia(D)` | nenhuma divergência e nenhum alerta por ela; a diferença não muda com a confirmação (o mesmo resultado sem ela) |
| A-8 | Caso-limite | negativo | um movimento `devolucao` sem `id_estorno` (dublê do protocolo) | `conciliar_dia(D)` | divergência comum; nenhum alerta crítico |
| A-9 | Caso-limite | positivo | a parcela `em_processamento` com o `id_estorno`, e o estorno concluído no simulador antes de `acompanhar_estorno` rodar | `conciliar_dia(D)` | só a divergência comum, sem alerta crítico; depois da tarefa e da conciliação de `D + 1`, a pendência é resolvida (E10-01) |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-9 | `tests/tecnicos/test_financeiro_conciliacao_estornos.py` |
