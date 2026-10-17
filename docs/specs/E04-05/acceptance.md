# E04-05 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As telas do administrador usam a passkey simulada da E02-03.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | E02-04, Spec §12 | positivo | o administrador | emite um convite de comprador para `novo@x.com` | um e-mail em `mail.outbox`; um `Envio` com `tipo="acesso:convite"`, `canal="email"`, `conta` nula, `destino="novo@x.com"`, assunto igual ao do e-mail, `corpo` vazio, `chave="acesso:convite:<id>"`, `situacao="enviado"`, `tentativas=1`; uma tentativa `sucesso`; `convite.email_enviado` verdadeiro |
| A-2 | E02-04 | negativo | `BackendQueFalha` | emito o convite pela tela | a tela mostra "Convite criado, mas o e-mail não pôde ser enviado. Emita um novo convite."; `Envio` `falhou` com uma tentativa `ConnectionError`; `email_enviado` falso; um segundo convite gera um segundo `Envio` |
| A-3 | E02-06 | positivo | um comprador ativo | pede o link de acesso | um `Envio` `acesso:link_de_acesso` com `conta` preenchida e `enviado` |
| A-4 | E02-06 | negativo | um e-mail sem conta e `BackendQueFalha` noutro caso | pede o link | sem conta: nenhum `Envio` e nenhum e-mail; com conta e falha: `Envio` `falhou`; nos dois, a resposta HTML é idêntica à do pedido bem-sucedido |
| A-5 | E02-02 | positivo | um comprador | pede a recuperação de senha | um `Envio` `acesso:conta_allauth` com `modelo="account/email/password_reset_key"`, `conta` preenchida, `corpo` vazio e `enviado`; o e-mail recebido contém o link de redefinição |
| A-6 | E02-02 | negativo | um e-mail desconhecido | pede a recuperação | nenhum e-mail e nenhum `Envio` |
| A-7 | Infra 5 | negativo | os fluxos do A-1, A-3 e A-5 | percorro todas as colunas de `Envio` e `TentativaDeEnvio` e os registros de log (`caplog` em `DEBUG`) | nenhum valor contém o token gerado nem o link com token |
| A-8 | Spec da fatia | negativo | — | procuro no código de `apps/` chamadas a `EmailMessage(`, `send_mail(` e `send_mass_mail(` | só aparecem em `apps/notificacoes/canais.py`; a busca ignora a definição de `AdaptadorConta.send_mail` |
| A-9 | Spec da fatia | negativo | um convite emitido dentro de uma transação que depois falha | o teste força o erro depois de `emitir_convite` | nenhum e-mail e nenhum `Envio` |
| A-10 | Spec da fatia | negativo | `enviar_email` aceita a mensagem e a gravação do `Envio` falha (`monkeypatch` no `create`) | pede o link de acesso | a resposta é a de sucesso; um `logger.error` com o tipo e a referência, sem o e-mail |
| A-11 | Regressão E02 | positivo | — | rodo os testes existentes das E02-02 (recuperação de senha), E02-04 (convites) e E02-06 (link de acesso) | todos verdes, sem alteração de asserção; a única mudança permitida é o marcador `django_db(transaction=True)` ou `django_capture_on_commit_callbacks(execute=True)`, conforme a correção E04-R02, listada no `review.md` |
| A-12 | E04-R02 | positivo | `django_db(transaction=True)`; três fluxos: um comprador que pede a recuperação de senha, o administrador que emite um convite e um comprador que pede o link de acesso | dentro de `transaction.atomic()`, executo `POST /recuperar-acesso/` com o e-mail do comprador, `emitir_convite` para `novo@x.com` e `POST /entrar/link/` com o e-mail do comprador; meço `len(mail.outbox)` e `Envio.objects.count()` antes de sair do bloco e depois da confirmação | antes da confirmação, 0 e-mails e 0 `Envio` nos três fluxos; depois, 1 e-mail e 1 `Envio` `enviado`, com uma `TentativaDeEnvio` `sucesso` e o `tipo` do fluxo; na recuperação, `modelo="account/email/password_reset_key"` e `conta` preenchida |
| A-13 | E04-R02 | negativo | os três fluxos do A-12 | faço a mesma chamada dentro de `transaction.atomic()` e levanto `RuntimeError` no fim do bloco | nenhum e-mail, nenhum `Envio` e nenhuma `TentativaDeEnvio` nos três fluxos; antes do rollback, as respostas foram as do fluxo normal (302 na recuperação e 200 no link) |
| A-14 | E04-R02 | negativo | `django_db(transaction=True)`; `BackendQueFalha`; um comprador | `POST /recuperar-acesso/` sem transação externa e, noutro caso, dentro de uma `transaction.atomic()` que é confirmada | nos dois casos, a resposta é igual à do envio bem-sucedido: mesmo status, mesmo destino do redirecionamento e mesmo HTML na página seguinte; um `Envio` `falhou` com uma tentativa `ConnectionError`; nenhuma exceção chega ao cliente; no caso com transação, nada é tentado antes da confirmação |
| A-15 | E04-R02 | negativo | `django_db(transaction=True)`; um comprador; um `monkeypatch` que faz `Envio.objects.create` levantar `DatabaseError` | `POST /recuperar-acesso/` | a resposta é igual à do envio bem-sucedido; um e-mail em `mail.outbox`; nenhum `Envio`; um `logger.error` com o tipo `acesso:conta_allauth` e a referência, sem o e-mail do comprador |
| A-16 | E04-R02, Infra 5 | negativo | o fluxo de recuperação do A-12, com `caplog` em `DEBUG` | extraio o link de redefinição do e-mail recebido; percorro todas as colunas de `Envio` e `TentativaDeEnvio`, os registros de log e os valores da sessão do cliente | nenhum valor contém o link de redefinição nem o token |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-7, A-9, A-10 | `tests/tecnicos/test_notificacoes_acesso.py` |
| A-8 | `tests/tecnicos/test_notificacoes_ponto_unico_de_email.py` |
| A-11 | os arquivos existentes da E02 |
| A-12 a A-16 | `tests/tecnicos/test_notificacoes_acesso.py`, com os três probes de transação do revisor de `0b52010` incluídos literalmente |
