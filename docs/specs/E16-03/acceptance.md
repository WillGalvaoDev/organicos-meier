# E16-03 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Transporte em memória (TM):** o Sentry inicializado no teste com um DSN fictício e um transporte que guarda os envelopes numa lista, sem rede, com as mesmas opções e filtros que `prod.py` usa. A função de opções é reaproveitável pelo teste.
- **Ambiente fictício (AF):** o da E16-01, mais `SENTRY_DSN`.
- **Execução das tarefas:** `tarefa(timestamp=0)`, como nas E15.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regra 1 | negativo | AF sem `SENTRY_DSN` | carregar `config.settings.prod` em subprocesso | falha de configuração. **Red esperado:** carrega |
| A-2 | Regra 2 | positivo | AF | carregar e ler as opções do cliente do Sentry | `environment = "homologacao"`, `send_default_pii` falso, `include_local_variables` falso, `max_request_body_size = "never"`, `traces_sample_rate = 0`, `before_send` e `before_breadcrumb` ligados aos filtros |
| A-3 | Regra 1 | positivo | `config.settings.test` sem `SENTRY_DSN` | rodar `verificar_operacao(0)` e provocar um `logger.error` | nenhum cliente ativo; nenhum envio; a tarefa conclui |
| A-4 | Regra 3 | negativo | TM; uma view de teste que levanta `RuntimeError("falha para ana@exemplo.com, tel (21) 99999-0000")`, chamada por C autenticado com `?email=ana@exemplo.com`, cookie de sessão e corpo `POST` com `senha=x` | a requisição | um evento enviado: método e caminho presentes; sem query string, corpo, cookies e IP; o usuário só com `id`; a mensagem com `[removido]` no lugar do e-mail e do telefone; nenhum dos textos `ana@exemplo.com`, `99999-0000`, `senha=x` nem o valor do cookie em qualquer parte do envelope |
| A-5 | Regra 3 | negativo | TM; `logger.error("x", extra={"token": "abc", "email": "b@c.d", "pedido": 7})` | registrar | o evento com `token` e `email` iguais a `[removido]` e `pedido = 7` |
| A-6 | Regra 3 | negativo | TM com o filtro forçado a levantar exceção | provocar um erro | nenhum envelope enviado |
| A-7 | Regra 4 | negativo | TM; uma consulta SQL com parâmetro `ana@exemplo.com` e depois um erro | provocar o erro | o evento sem breadcrumb de SQL; o texto `ana@exemplo.com` ausente do envelope |
| A-8 | Regras 6 e 7 | positivo | TM | `verificar_operacao(0)` | dois check-ins com o slug `verificar-operacao`: `in_progress` e depois `ok`, com o mesmo `check_in_id`; o `monitor_config` com `schedule` `*/5 * * * *` (crontab), `checkin_margin = 10`, `max_runtime = 5` e `timezone = "UTC"`. **Red esperado:** nenhum check-in |
| A-9 | Regra 7 | positivo | TM; o corpo de `verificar_operacao` forçado a levantar `RuntimeError` | executar | a exceção repassada; check-ins `in_progress` e `error`; o `ExecucaoDaTarefa` com a falha `RuntimeError` (E15-01) |
| A-10 | Regra 8 | negativo | TM com o envio de check-in forçado a levantar `ConnectionError` | `verificar_operacao(0)` | a tarefa conclui normalmente; o `ExecucaoDaTarefa` com a conclusão; um log com `ConnectionError` |
| A-11 | Regra 9 | negativo | TM | `processar_envios_pendentes(0)` e `verificar_invariante(0)` | nenhum check-in |
| A-12 | Regra 6 | positivo | — | ler `MONITORES_EXTERNOS` | a linha de `verificar_operacao` da tabela da regra 6, com o slug `verificar-operacao`. A linha de `backup_diario` entra com a tarefa e é testada na E16-04 (A-14) |
| A-13 | Regra 5 | negativo | a suíte inteira | ler as configurações de teste | `SENTRY_DSN` vazio em `config.settings.test` e no CI |

| Critério | Arquivo de teste |
|---|---|
| A-1, A-2 e A-13 | `tests/ambiente/test_homologacao.py` |
| A-3 a A-12 | `tests/tecnicos/test_observabilidade.py` |
