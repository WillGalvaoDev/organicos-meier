# E04-05 — E-mails de acesso no registro de envios

Fatia 5 de 7 da milestone **E04 — Notificações e comunicados**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Três e-mails saem hoje direto pela API de e-mail do Django, sem registro estruturado do resultado:

- o convite (E02-04);
- o link de acesso (E02-06);
- a recuperação de senha do allauth (E02-02).

A E02-04 deixou para a E04 o "registro estruturado de entregas". Esta fatia passa os três a registrar cada envio e o seu resultado no mesmo modelo `Envio` da E04-02. O comportamento visível desses fluxos não muda.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §12, Eventos | Convite: link, finalidade e expiração de 24h. |
| Especificação §12, Requisitos derivados | Registrar envio e falhas; retentativa sem duplicação indevida. |
| Especificação §3.1 | Tokens imprevisíveis; convite expirado exige novo convite. |
| Infraestrutura 5 | Segredos fora do código e dos logs; nenhum dado pessoal em logs. |
| E02-04 | Token só no e-mail, gravado como hash. Falha de envio: convite gravado e a tela mostra "Convite criado, mas o e-mail não pôde ser enviado. Emita um novo convite.". Registro estruturado de entregas fica na E04. |
| E02-06 | Link de uso único, 15 minutos, token só como hash; a resposta é igual para qualquer e-mail. |
| E02-02 | Recuperação de senha pelo allauth; `ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False`. |
| E04-02, E04-03 | `Envio`, `TentativaDeEnvio` e `enviar_email`. |

## Escopo

**Dentro:**

- O tipo de envio `acesso` e os seus modelos (`convite`, `link_de_acesso` e `conta_allauth`).
- A função `enviar_email_de_acesso`.
- O uso dessa função no convite, no link de acesso e em `AdaptadorConta.send_mail`.

**Fora:**

- Mudança no texto, na validade ou nas regras dos três fluxos.
- Reenvio automático (ver Decisões técnicas).
- Consulta administrativa dos envios (E04-07).

## Decisões técnicas

**Sem retentativa automática nos e-mails de acesso.** Os três e-mails levam um token que só existe na memória da requisição e é gravado apenas como hash (E02-04, E02-06, allauth). Uma retentativa posterior exigiria guardar o token ou o corpo do e-mail, o que contraria "segredos fora do código e dos logs" e o desenho aprovado na E02.

A retentativa sem duplicação indevida, nesses casos, é a ação que já existe:

- um novo convite;
- um novo pedido de link;
- um novo pedido de recuperação.

Cada um gera token novo e envio novo. O registro mostra a falha ao administrador (E04-07). A decisão segue da precedência: a regra de segurança aprovada vence a conveniência de reenviar o mesmo e-mail.

**Envio imediato, não pela fila.** Quem pede o link ou a recuperação espera o e-mail na hora. Por isso esses e-mails continuam saindo em `transaction.on_commit`, sem passar pelo `processar_envios` da E04-03. O registro é gravado no mesmo momento, com uma única tentativa.

## Regras

**Tipos:** o campo `tipo` do `Envio` (E04-02) passa a aceitar `acesso:convite`, `acesso:link_de_acesso` e `acesso:conta_allauth`, além dos valores de `Evento`. A migração substitui o `CHECK` da E04-02:

- `notificacao` nula se e somente se `tipo` é um dos três tipos de acesso;
- `conta` nula só quando `tipo = 'acesso:convite'`;
- os tipos de acesso só existem com `canal = 'email'`.

**Função** (`apps/notificacoes/acesso.py`):

```
enviar_email_de_acesso(tipo, *, destino, assunto, corpo, conta=None, referencia) -> Envio
```

1. É chamada de dentro do `transaction.on_commit` de cada fluxo, depois de a transação do fato ter confirmado. Isso vale para os três fluxos, sem exceção, incluindo `AdaptadorConta.send_mail` (correção E04-R02). Ela envia primeiro e depois grava o registro numa `transaction.atomic()` própria.
2. Envia com `enviar_email(destino, assunto, corpo)` (E04-03).
3. Grava um `Envio` com:
   - `canal=email`, `tipo`, `conta` (nula no convite), `destino` e `assunto`;
   - `corpo` **vazio**, porque o corpo tem o token;
   - `chave=f"{tipo}:{referencia}"`;
   - `tentativas=1` e `situacao` `enviado` ou `falhou`;
   - `concluido_em=agora()`.
4. Grava uma `TentativaDeEnvio` `numero=1`, com o resultado e só a classe do erro.
5. **Exceções:**
   - nunca propaga a exceção do envio;
   - devolve o `Envio`, e quem chama lê `situacao` para decidir a mensagem da tela.
   - Se a gravação do registro falhar depois de um envio aceito, registra `logger.error` com o tipo e a referência, sem destino, e não propaga. O e-mail já saiu, e o fluxo do usuário não pode quebrar por causa do registro.
6. A `referencia` é:
   - no convite, o id do convite;
   - no link, o id do `LinkDeAcesso`;
   - no allauth, um `uuid4` gerado na chamada, porque não há identificador natural.

**Convite** (`apps/contas/convites.py`):

- `_enviar_email` passa a chamar `enviar_email_de_acesso("acesso:convite", ...)`.
- O campo existente `convite.email_enviado` continua igual: verdadeiro quando o envio fica `enviado`.
- A mensagem de falha da tela continua a mesma.

**Link de acesso** (`apps/contas/link_de_acesso.py`):

- `_enviar_email` passa a usar a função, com `conta` preenchida.
- A resposta da tela continua igual para qualquer e-mail, com envio ou sem. Isso preserva a proteção contra enumeração da E02-06.

**allauth** (`AdaptadorConta.send_mail(template_prefix, email, context)`):

- Monta assunto e corpo pelos templates do allauth (`render_mail`) durante a requisição e registra no `transaction.on_commit` o envio com `enviar_email_de_acesso("acesso:conta_allauth", ...)` (correção E04-R02).
- A `conta` é a dona do e-mail, quando existir.
- O registro guarda também o `template_prefix` (por exemplo, `account/email/password_reset_key`), num campo `modelo` do `Envio`, opcional, com até 100 caracteres e vazio nos outros tipos.
- Nenhum envio direto pela API de e-mail fica em `apps/contas`. Um teste procura chamadas a `EmailMessage(`, `send_mail(` e `send_mass_mail(` fora de `apps/notificacoes/canais.py` e falha se encontrar alguma.

## Interfaces

- `apps/notificacoes/acesso.py`: `enviar_email_de_acesso` e `TipoDeAcesso`.
- `Envio.modelo` (migração).
- `apps/contas/convites.py`, `apps/contas/link_de_acesso.py` e `apps/contas/adaptadores.py`, ajustados.

## Invariantes

- Nenhum token, link com token ou corpo de e-mail de acesso é gravado no banco nem no log.
- Todo e-mail enviado pela aplicação passa por `enviar_email` e tem um `Envio` registrado.
- O comportamento visível do convite, do link e da recuperação de senha não muda.

## Casos-limite e concorrência

- **Convite com falha de envio:** `Envio` `falhou` com uma tentativa; `email_enviado = False`; a tela mostra a mensagem existente; um novo convite gera um novo `Envio`.
- **Link pedido para e-mail sem conta:** nenhum e-mail e nenhum `Envio`. A resposta é igual à do e-mail com conta.
- **Recuperação de senha para e-mail desconhecido:** com `ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False`, nenhum e-mail e nenhum `Envio`.
- **Convite cuja transação é desfeita:** o `on_commit` não roda; nenhum e-mail e nenhum `Envio`.
- **Os testes existentes da E02** continuam verdes sem alteração de asserção. Os ajustes de fixture, se houver, ficam justificados no `review.md`.

## Correção E04-R02 — revisão da especificação em 2026-10-17

### Diagnóstico

- A regra 1 desta fatia exige que os três fluxos chamem `enviar_email_de_acesso` dentro do `transaction.on_commit`. `AdaptadorConta.send_mail` (`apps/contas/adaptadores.py`) chama a função direto, durante a requisição.
- Quando já existe uma transação aberta, a `transaction.atomic()` de `enviar_email_de_acesso` (`apps/notificacoes/acesso.py`) vira um *savepoint*. Nesse caso:
  - o e-mail sai antes da confirmação;
  - se a transação externa for desfeita, o `Envio` e a `TentativaDeEnvio` somem junto, e o e-mail aceito fica sem registro.
- **Reprodução do revisor:** `POST /recuperar-acesso/` dentro de `transaction.atomic()`, seguido de rollback. Resultado: um e-mail em `mail.outbox` e nenhum `Envio`.
- `ATOMIC_REQUESTS` é `False` (`config/settings/base.py`), então a requisição comum não tem transação externa. O defeito aparece sempre que o allauth, ou o código que o chama, envia dentro de uma transação. O convite e o link de acesso já usam `on_commit`.
- A docstring de `enviar_email_de_acesso` registra essa exceção ("ou direto, no allauth"), que a especificação não autorizou.

### Regra

**`AdaptadorConta.send_mail` adia o envio para depois da confirmação.**

1. **Durante a requisição**, nesta ordem:
   - monta a mensagem com `self.render_mail(template_prefix, email, context)`;
   - lê o destino em `mensagem.to[0]`;
   - busca a conta pelo `email_normalizado`;
   - gera a `referencia` com `uuid4`.

   Esses valores ficam só na memória da requisição. O corpo renderizado leva o token e não é gravado em lugar nenhum.
2. **Registro do envio:** `send_mail` chama `transaction.on_commit(...)` com uma função que executa `enviar_email_de_acesso(CONTA_ALLAUTH, destino=..., assunto=mensagem.subject, corpo=mensagem.body, conta=..., referencia=..., modelo=template_prefix)`.
   - **Sem transação aberta:** o Django executa a função na hora, no mesmo momento de hoje.
   - **Com transação aberta:** a função só roda depois da confirmação. Se houver rollback, ela não roda, e não sai nem e-mail nem registro.
3. **Alcance:** a regra vale para todo e-mail que o allauth manda por `send_mail`, e não só para a recuperação de senha.
4. **Resposta:** `send_mail` não devolve nem propaga o resultado do envio. Para o allauth, a resposta é igual em todos os casos: sucesso, falha do canal, falha do registro ou e-mail desconhecido. Isso mantém a proteção contra enumeração.
5. **Docstring:** a de `enviar_email_de_acesso` passa a dizer que a função é sempre chamada de dentro do `on_commit` dos três fluxos, sem exceção.

**O que não muda:**

- o conteúdo renderizado, o assunto e o `modelo`;
- a associação à conta;
- o `corpo` vazio no `Envio`;
- a tentativa única;
- o tratamento de falha do canal: `falhou`, com a classe do erro;
- o tratamento de falha da gravação: `logger.error` com o tipo e a referência, sem destino;
- o envio imediato, fora da fila;
- `ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False`.

**Testes existentes da E02:**

- `tests/tecnicos/test_contas_recuperacao.py` usa `pytest.mark.django_db` sem `transaction=True`. Nesse modo, cada teste roda numa transação que nunca é confirmada, e a função registrada no `on_commit` não executa.
- Nesse arquivo, e em qualquer outro cujo e-mail venha do allauth, o ajuste permitido é trocar o marcador para `django_db(transaction=True)`, como já fazem os testes do convite e do link de acesso. Também vale envolver a chamada em `django_capture_on_commit_callbacks(execute=True)`.
- Nenhuma asserção muda. Cada arquivo ajustado fica listado no `review.md` com essa justificativa (A-11).

### Testes obrigatórios

- Três probes do revisor entram literais em `tests/tecnicos/test_notificacoes_acesso.py`:
  - `test_recuperacao_rollback_nao_envia_email`;
  - `test_recuperacao_so_envia_apos_commit`;
  - `test_link_rollback_nao_envia_email`.

  Eles estão em `docs/specs/E04-07/review.md`, na seção "Script reproduzível" da revisão de `0b52010`.
- Os critérios A-12 a A-16 exigem Red observado antes do código.
  - Na recuperação de senha, o A-12 e o A-13 cobrem o próprio defeito.
  - No convite e no link de acesso, o A-12 e o A-13 são guarda de regressão. Se passarem já no Red, registre isso no `review.md` com a justificativa (o comportamento já existia). Isso não é violação do TDD.

### O que não fazer

- Não guardar o `context` do allauth para renderizar a mensagem dentro do `on_commit`. A renderização acontece na requisição, como hoje.
- Não gravar o corpo nem o contexto em banco, cache ou sessão para enviar depois.
- Não mandar o e-mail do allauth para a fila do `processar_envios`.
- Não usar `transaction.atomic(durable=True)` nem uma conexão separada para gravar o registro antes da confirmação. A ordem exigida é: confirmar o fato, enviar e depois registrar.
- Não ligar `ATOMIC_REQUESTS`.

## Dependências e decisões em aberto

- Depende de E02-02, E02-04, E02-06, E04-02 e E04-03.
- Sem decisões em aberto.
