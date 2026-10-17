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

1. É chamada de dentro do `transaction.on_commit` de cada fluxo, depois de a transação do fato ter confirmado. Ela envia primeiro e depois grava o registro numa `transaction.atomic()` própria.
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

- Monta assunto e corpo pelos templates do allauth (`render_mail`) e envia com `enviar_email_de_acesso("acesso:conta_allauth", ...)`.
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

## Dependências e decisões em aberto

- Depende de E02-02, E02-04, E02-06, E04-02 e E04-03.
- Sem decisões em aberto.
