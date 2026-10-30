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

## Correção E10-R05 e R09 (2026-10-30)

Valem a seção da correção no `spec.md` e a correção E10-R08 (E10-07, `spec.md`).

**Arranjo R (estorno recusado que conclui tarde):** o arranjo da E10-04 com `estornos_em_processamento(P1)`; autorizar O1 e `processar_chamadas(limite=1)`: a parcela fica `em_processamento` com o `id_estorno` `e`. Depois, `recusar_estorno(e, "estado_invalido")` e `processar_chamadas()`: a parcela passa por `falha_definitiva` e fica `elegivel_excepcional`, com o `id_estorno` `e` guardado. A **conclusão tardia** de `e` é o dublê do parecer: o `EstornoSimulado` volta a `em_processamento` e `concluir_estorno(e)` produz o débito. O dublê exercita o risco residual da infraestrutura 4.7; não afirma que a API real reverte uma recusa (L-7).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-10 | R05 | positivo | `recusar_mas_processar(P1, "meio_nao_permite_estorno")`; autorizar e processar: a parcela `elegivel_excepcional`; depois o estorno escondido fica visível, ainda `em_processamento` | `confirmar_devolucao_excepcional` (recusada, agenda `verificar_estornos`) e `processar_chamadas()` | a parcela em `em_processamento`, com o `id_estorno` do estorno visível; uma chamada `acompanhar_estorno` pendente; o alerta `devolucao_elegivel_excepcional` resolvido com "estorno encontrado no provedor e adotado". **Red esperado:** a parcela continua `elegivel_excepcional`, sem acompanhamento |
| A-11 | R05 | positivo | o A-10 | `concluir_estorno` no simulador e `processar_chamadas()` | a parcela `concluida`; um F15 `devolucao:<id_estorno>`; um aviso "Estorno concluído" para B; nenhum segundo aviso "Estorno em andamento" |
| A-12 | R09, ordem 1 | negativo e positivo | R, com a conclusão tardia de `e` | `confirmar_devolucao_excepcional(parcela, ...)` e depois `processar_chamadas()` | a confirmação levanta `DevolucaoRecusada("há devolução em processamento ou concluída no provedor")`, sem confirmação, F16 nem arquivo, e agenda `verificar_estornos`; depois da tarefa, a parcela `concluida` com o `id_estorno` `e` e um F15 `devolucao:<e>`. **Red esperado:** a confirmação é aceita |
| A-13 | R09, ordem 2 | negativo | R, com a confirmação excepcional feita (`e` ainda recusado) e depois a conclusão tardia de `e` | `conciliar_dia(D)` | `devolucao_concluida_tardiamente` crítico, com a chave `e`, a parcela, `situacao = concluida_fora_da_plataforma` e `devolvida_em_dobro = true`; nenhum lançamento novo no livro; a parcela continua `concluida_fora_da_plataforma`; nenhuma `verificar_estornos` agendada. **Red esperado:** só a divergência comum |
| A-14 | R09 | positivo | R, interrompido em `falha_definitiva` (`processar_chamadas(limite=1)` depois da recusa, com a `verificar_estornos` ainda pendente), e a conclusão tardia de `e` | `processar_chamadas()` | a reconsulta adota `e`: a parcela `concluida`, com um F15 `devolucao:<e>`; nenhuma passagem por `elegivel_excepcional` no histórico. **Red esperado:** `e` é tratado como contabilizado, e a parcela fica `elegivel_excepcional` |
| A-15 | R09 | positivo | o A-14 antes do `processar_chamadas()` | `conciliar_dia(D)` | `devolucao_concluida_tardiamente` crítico com a chave `e` e `devolvida_em_dobro = false`; `verificar_estornos` pendente para a parcela (a já existente). **Red esperado:** nenhum alerta crítico |
| A-16 | R09 | positivo | uma parcela `em_processamento` com o `id_estorno` `e`, e `e` concluído no simulador antes de `acompanhar_estorno` rodar (o A-9) | `confirmar_devolucao_excepcional` de uma **outra** parcela do mesmo pagamento, `elegivel_excepcional` por fábrica, com outro valor | a confirmação é aceita: `e` é assumido pela parcela em processamento. Regressão da definição: esperado verde, sem Red |

As provas `test_adota_processamento_apos_elegibilidade`, `test_estorno_identificado_recusado_que_conclui_tarde` e `test_alerta_tardio_com_id_conhecido` do parecer têm de passar como estão.

| Critério | Arquivo de teste |
|---|---|
| A-10 a A-16 | `tests/tecnicos/test_financeiro_conciliacao_estornos.py` |
