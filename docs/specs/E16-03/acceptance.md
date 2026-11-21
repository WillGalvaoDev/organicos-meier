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
| A-14 | Regra 3-A (E16-R02) | negativo | TM; `capture_event` com `request.url = "https://exemplo.invalid/entrar/link/TOKEN-SINTETICO-1/?x=1"` | capturar | `TOKEN-SINTETICO-1` ausente do envelope inteiro; `request.url` igual a `https://exemplo.invalid/entrar/link/[removido]/`. **Red esperado:** o token presente em `request.url` (reprodução do revisor) |
| A-15 | Regra 3-A (E16-R02) | negativo | TM; `GET` em `/convite/TOKEN-SINTETICO-2/`, `/convite/TOKEN-SINTETICO-3/google/` e `/entrar/link/TOKEN-SINTETICO-4/`, com a view forçada a levantar `RuntimeError` com o caminho no texto (trocando uma função que ela chama) e um `logger.warning` com o caminho antes do erro | cada requisição | um evento por requisição; nenhum dos três tokens em nenhuma parte do envelope (requisição, transação, exceção, `logentry`, breadcrumbs); a transação com o padrão da rota; o caminho `/convite/[removido]/google/` no terceiro |
| A-16 | Regra 3-A (E16-R02) | positivo e negativo | o resolvedor de URLs do projeto; depois um URLconf de teste com a rota extra `teste/<str:token_de_teste>/` | conferir a cobertura de `ROTAS_COM_SEGREDO` | as três rotas do projeto cobertas; a rota extra acusada como não coberta |
| A-17 | Regra 3-B (E16-R02) | negativo | TM; `capture_event({"message": "erro", "extra": {"nome": "Pessoa Sintetica Revisora"}})`; depois `logger.error("x", extra={"first_name": "Fulana Sintetica", "nome_completo": "Fulana Sintetica Completa", "username": "fulana.sintetica", "telefone_do_comprador": "21 3333 4444", "cpf": "000.000.000-00", "pedido": 7, "id_externo": "SIM-1"})`; tags `{"usuario": "fulana-tag"}`; contexto `{"comprador": {"name": "Fulana Contexto"}}` | capturar | todos os valores pessoais como `[removido]` e ausentes do envelope; `pedido = 7` e `id_externo = "SIM-1"` preservados; `contexts.runtime.name` preservado. **Red esperado:** `Pessoa Sintetica Revisora` em `extra.nome` (reprodução do revisor) |
| A-18 | Regras 3-A, 3-B e 4 (E16-R02) | negativo | TM; um breadcrumb com `message` contendo `/entrar/link/TOKEN-SINTETICO-5/` e `data = {"nome": "Pessoa Sintetica", "url": "https://exemplo.invalid/convite/TOKEN-SINTETICO-6/?a=b"}`; depois um erro | capturar o erro | o breadcrumb presente, com a mensagem `/entrar/link/[removido]/`, `data.nome` igual a `[removido]` e `data.url` igual a `https://exemplo.invalid/convite/[removido]/`; nenhum dos valores sintéticos no envelope |
| A-19 | Regras 3 e 3-B (E16-R02) | negativo | TM; um evento com `request.headers` contendo `User-Agent`, `Cookie`, `Authorization`, `X-Forwarded-For` e `Referer: https://exemplo.invalid/convite/TOKEN-SINTETICO-7/` | capturar | só `User-Agent` nos cabeçalhos; `TOKEN-SINTETICO-7` e os valores dos demais cabeçalhos ausentes do envelope |
| A-20 | Regra 2 (E16-R02) | positivo | AF | carregar e ler a integração com o Django do cliente | `transaction_style = "url"` |

| Critério | Arquivo de teste |
|---|---|
| A-1, A-2 e A-13 | `tests/ambiente/test_homologacao.py` |
| A-3 a A-12 | `tests/tecnicos/test_observabilidade.py` |
| A-14 a A-20 | `tests/tecnicos/test_observabilidade.py` |
