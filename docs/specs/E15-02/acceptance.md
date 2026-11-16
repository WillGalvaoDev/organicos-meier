# E15-02 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjo AO:**
  - o administrador ADM1, um comprador (C) e um fornecedor (F). Não há segundo administrador nem administrador suspenso: o banco admite um único administrador, sempre ativo (especificação §1, "Há um único administrador"; `conta_administrador_unico` e `conta_administrador_ativo`). "Cada administrador ativo" (regra 3) é, nos testes, ADM1;
  - relógio em `I = 2026-11-20 12:00 UTC` (09:00 em Brasília);
  - `ExecucaoDaTarefa` de todas as tarefas do catálogo concluídas em `I`.
- **Execução:** `verificar_operacao_agora()` chamada diretamente, salvo indicação.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regra 9 | positivo | AO; `processar_envios_pendentes` concluída pela última vez em `I` | verificar em `I + 6min` | um alerta `tarefa_atrasada` com chave `processar_envios_pendentes`, gravidade aviso e os dados da regra 9; uma notificação `alerta_operacional` no site para ADM1, com o título "Tarefa atrasada", o corpo "A tarefa Envio de notificações não conclui desde 20/11/2026 09:00. Ela deveria rodar a cada 1 minuto(s)." e o link `/administracao/`; um `Envio` de e-mail para ADM1; nada para C e F; o retorno `(1, 0)`. **Red esperado:** o tipo não existe |
| A-2 | Regra 6 | positivo | o A-1 | verificar de novo em `I + 7min` | nenhum alerta novo e nenhuma notificação nova; `(0, 0)` |
| A-3 | Regra 6 | positivo | o A-1; a tarefa conclui em `I + 8min` | verificar em `I + 9min` | o alerta resolvido com `resolvido_em = I + 9min` e o motivo "condição encerrada"; `(0, 1)` |
| A-4 | Regra 6 | positivo | o A-3; a tarefa para de novo | verificar em `I + 15min` | um alerta novo (outro pk) e notificações novas; o resolvido intacto |
| A-5 | Regra 8 | positivo | AO sem o registro de `enviar_pedidos_formais` | verificar em `I`; depois em `I + 5min + 1s` | na primeira, o registro criado com `monitorada_desde = I` e nenhum alerta; na segunda, `tarefa_atrasada` com o corpo "não tem execução concluída desde 20/11/2026 09:00" |
| A-6 | Regra 6 | negativo | AO com o alerta do A-1 aberto; uma verificação de teste registrada antes de `tarefa_atrasada` que levanta `RuntimeError`; `processar_envios_pendentes` em dia de novo | verificar | a exceção não sai; um log com o tipo da verificação de teste e "RuntimeError"; o alerta de tarefa atrasada resolvido normalmente (a verificação seguinte rodou) |
| A-7 | Regra 6 | negativo | AO com o alerta do A-1 aberto; a verificação de `tarefa_atrasada` substituída por uma que levanta | verificar | o alerta continua aberto; nada resolvido |
| A-8 | Regra 3 | positivo | AO | dentro de uma transação, `abrir_alerta("invariante_violado", "geral", {...})` | a notificação com o evento `alerta_financeiro` e o link `/administracao/financeiro/`, como antes desta fatia |
| A-9 | Regra 3 | negativo | AO sem a conta do administrador (o arranjo não cria ADM1) | verificar com uma tarefa atrasada | o alerta aberto; nenhuma notificação; um log de falta de destinatário |
| A-10 | Regra 4 | positivo | o A-1 | ler os logs capturados | um `WARNING` com `tarefa_atrasada` e `processar_envios_pendentes`, sem os dados |
| A-11 | Regra 7 | positivo | — | ler as tarefas periódicas do Procrastinate | `verificar_operacao` com `*/5 * * * *` e `queueing_lock`; o catálogo da E15-01 com "Verificação operacional", 5 e 15 minutos; chamar a tarefa grava o `ExecucaoDaTarefa` dela |
| A-12 | Regra 1 | concorrência | AO com uma tarefa atrasada; transações reais | duas execuções de `verificar_operacao_agora()` ao mesmo tempo, com a primeira pausada depois de abrir o alerta | um alerta aberto; uma notificação e um `Envio` para ADM1; nenhuma exceção |
| A-13 | Regra 1 | positivo | o A-1 com um alerta crítico financeiro aberto depois | `alertas_abertos()` | o crítico primeiro, depois `tarefa_atrasada` |
| A-14 | Interface | positivo | o A-1 e o A-8 | `link_do_alerta` e `natureza_do_alerta` | `/administracao/` e `condicao`; `/administracao/financeiro/` e `None` |
| A-15 | Invariante | negativo | AO | C e F na central de notificações depois do A-1 | nenhuma notificação `alerta_operacional` |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-11 e A-13 a A-15 | `tests/tecnicos/test_alertas_operacionais.py` |
| A-12 | `tests/tecnicos/test_alertas_operacionais.py`, com transações PostgreSQL reais |
