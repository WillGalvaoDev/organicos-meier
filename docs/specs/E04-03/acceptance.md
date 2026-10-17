# E04-03 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Os envios são criados por `emitir_evento` ou pela `EnvioFactory`. O relógio é controlado com `time_machine`. O backend de e-mail é o `locmem` (sucesso) ou o `BackendComFalhas` de `tests/apoio`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §12 | positivo | um envio de e-mail pendente, com backend `locmem` | `processar_envios()` | devolve 1; `mail.outbox` com uma mensagem com o destino, o assunto e o corpo do envio; envio `enviado`, `tentativas=1`, `concluido_em` igual ao `agora()`; uma `TentativaDeEnvio` `numero=1`, `sucesso`, `erro` vazio |
| A-2 | Spec §12, Infra 4.14 | negativo | um envio pendente, com `BackendComFalhas(falhas=2)` | processo em t0; avanço para t0+59 s e processo; t0+60 s e processo; t0+60 s+10 min−1 s e processo; t0+60 s+10 min e processo | tentativas nos instantes t0, t0+60 s e t0+60 s+10 min (falha, falha, sucesso); nas chamadas intermediárias, nenhuma tentativa; envio `enviado` com `tentativas=3`; uma mensagem em `mail.outbox` |
| A-3 | Spec §12, Infra 4.14 | negativo | um envio pendente, com `BackendQueFalha` | processo três vezes, avançando o relógio pelos intervalos; depois, avanço um dia e processo de novo | três tentativas `falha` com `erro="ConnectionError"`; envio `falhou`, `tentativas=3`, `concluido_em` preenchido; a quarta chamada não faz tentativa |
| A-4 | Spec da fatia | positivo | três envios elegíveis; `BackendQueFalhaPara` com o destino do primeiro | `processar_envios()` | devolve 3; o primeiro com uma falha e reagendado; os outros dois `enviado` |
| A-5 | Spec da fatia | positivo | cinco envios elegíveis | `processar_envios(limite=2)` | devolve 2; três continuam pendentes com `tentativas=0` |
| A-6 | Spec da fatia | concorrência | os envios `E1` e `E2` elegíveis | uma thread trava `E1` com `select_for_update`; enquanto isso, `processar_envios()` roda noutra thread e termina | `E1` sem tentativa; `E2` enviado; depois que a primeira thread solta a trava, uma nova chamada envia `E1` uma única vez |
| A-7 | Spec §12, Cenário 24 (parte do e-mail) | positivo | uma emissão de `estorno` confirmada e o e-mail falhando três vezes | processo até `falhou` e abro a central como o comprador | a notificação aparece igual à emitida; título, corpo e `lida_em` inalterados |
| A-8 | Infra 5 | negativo | `caplog` em `DEBUG`, envio para `ana@x.com` com assunto "Estorno", e o backend levantando `ConnectionError("falha para ana@x.com")` | processo até `falhou` | há `warning` e `error` com o id do envio e `ConnectionError`; nenhum registro contém `ana@x.com` nem "Estorno"; o `erro` gravado é `ConnectionError`, sem a mensagem |
| A-9 | Infra 5 | negativo | uma `TentativaDeEnvio` | `UPDATE` e `DELETE` pelo ORM e por SQL direto; inserção de um segundo `numero=1` para o mesmo envio | `RegistroImutavel` no ORM; o banco recusa os dois por SQL; `UNIQUE` recusa a duplicata |
| A-10 | Spec da fatia | positivo | — | inspeciono a tarefa `processar_envios_pendentes` no app do Procrastinate | registrada como periódica com `cron "* * * * *"` e `queueing_lock`; ao ser executada diretamente, chama `processar_envios` (verificado com `monkeypatch`) |
| A-11 | Spec da fatia | positivo | — | inspeciono `settings` (teste) | `procrastinate.contrib.django` em `INSTALLED_APPS`; `EMAIL_TIMEOUT == 10`; `makemigrations --check` sem pendências |
| A-12 | Spec da fatia | positivo | um envio pendente agendado para o futuro | `processar_envios()` antes do instante | devolve 0 e não chama o backend |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-5, A-7, A-8, A-12 | `tests/tecnicos/test_notificacoes_processamento.py` |
| A-6 | `tests/tecnicos/test_notificacoes_concorrencia.py` (marcador `concorrencia`) |
| A-9 | `tests/tecnicos/test_notificacoes_modelo.py` |
| A-10, A-11 | `tests/tecnicos/test_notificacoes_tarefas.py` |
