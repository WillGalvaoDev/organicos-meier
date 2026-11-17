# E15-01 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Relógio:** `relogio.congelar(I)`, com `I = 2026-11-20 12:00 UTC`.
- **Chamada das tarefas:** cada tarefa periódica é chamada diretamente (`tarefa(timestamp=0)`). A função de domínio que ela chama é substituída por um dublê que retorna normalmente ou levanta uma exceção.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regra 1 | positivo | nenhum registro | `with execucao_monitorada("processar_envios_pendentes"): pass` em `I` | um `ExecucaoDaTarefa` com `monitorada_desde = I`, `ultima_conclusao_em = I` e `falhas_seguidas = 0`, sem falha. **Red esperado:** o módulo não existe |
| A-2 | Regra 1 | negativo | o A-1 | em `I + 1min`, o corpo levanta `RuntimeError("dado sensível")` | a mesma `RuntimeError` relançada; `ultima_falha_em = I + 1min`; `ultimo_erro = "RuntimeError"` (sem a mensagem); `falhas_seguidas = 1`; `ultima_conclusao_em = I` |
| A-3 | Regra 1 | positivo | o A-2 com mais uma falha (2 seguidas) | em `I + 3min`, o corpo termina sem exceção | `falhas_seguidas = 0`; `ultima_conclusao_em = I + 3min`; `ultima_falha_em` e `ultimo_erro` mantidos |
| A-4 | Regra 1 | negativo | — | `execucao_monitorada("tarefa_inexistente")` | `ValueError`; o corpo não executa; nenhum registro |
| A-5 | Regra 1 | positivo | — | chamar cada uma das dez tarefas do catálogo, com o dublê sem exceção | dez registros, um por nome do catálogo, com conclusão; o dublê chamado uma vez em cada tarefa |
| A-6 | Regra 1 | negativo | — | chamar `verificar_invariante` com o dublê levantando `ValueError` | a exceção sai da tarefa; o registro com a falha |
| A-7 | Regra 1 | positivo | — | o corpo abre `transaction.atomic()`, grava um objeto e levanta uma exceção | o objeto do corpo desfeito; o registro da falha gravado |
| A-8 | Regra 1 | negativo | a gravação do registro forçada a falhar (dublê em `ExecucaoDaTarefa.objects`) | o corpo termina sem exceção | a tarefa termina sem exceção; um log com o nome da tarefa e a classe do erro |
| A-9 | Regra 2 | concorrência | nenhum registro; transações reais | duas conexões concluem `processar_envios_pendentes` ao mesmo tempo, com a primeira pausada depois do `INSERT` | um registro só; as duas sem exceção; `ultima_conclusao_em` preenchida |
| A-10 | Regra 3 | positivo | registro com conclusão em `I` | gravação de conclusão com o relógio em `I − 1min` | `ultima_conclusao_em = I` |
| A-11 | Regra 4 | positivo | `processar_envios_pendentes`, `verificar_invariante` e `conciliar_dias_pendentes` concluídas em `I` | `situacao_das_tarefas` em `I + 5min`, `I + 5min + 1s`, `I + 30min + 1s` e `I + 3h + 1s` | envios: em dia em `I + 5min` e atrasada em `I + 5min + 1s`, com `atrasada_desde = I + 5min`; invariante: em dia até `I + 30min` e atrasada depois; conciliação: atrasada só em `I + 3h + 1s` |
| A-12 | Regra 4 | positivo | registro de `enviar_pedidos_formais` criado em `I`, só com falhas | `situacao_das_tarefas(I + 6min)` | `atrasada`, com a referência em `monitorada_desde` |
| A-13 | Regra 4 | positivo | nenhum registro | `situacao_das_tarefas(I)` | dez itens na ordem do catálogo, todos `sem_registro`, com as descrições da tabela |
| A-14 | Regra 5 | negativo | o A-2 | ler o registro e os logs capturados | nenhum trecho de "dado sensível" |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-8 e A-10 a A-14 | `tests/tecnicos/test_execucao_das_tarefas.py` |
| A-9 | `tests/tecnicos/test_execucao_das_tarefas.py`, com transações PostgreSQL reais |
