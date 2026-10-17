# E04-02 — Emissão de eventos e fila de envios

Fatia 2 de 7 da milestone **E04 — Notificações e comunicados**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

As etapas seguintes (E05 a E14) precisam avisar compradores e o administrador quando um fato acontece: preço alterado, pagamento confirmado, estorno, retirada liberada e outros.

A especificação exige:

- registrar envios e falhas;
- permitir retentativa sem duplicação indevida;
- nunca deixar uma falha de mensagem alterar o estado financeiro;
- manter o site correto mesmo com canal externo em falha.

Esta fatia entrega a função única de emissão, chamada pela etapa dentro da própria transação do fato. Ela grava, de forma atômica e idempotente:

- a notificação no site (E04-01);
- um envio pendente para cada canal externo aplicável.

O envio em si é feito depois, fora da transação do fato (E04-03).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §12, Requisitos derivados | Registrar envio e falhas; retentativa sem duplicação indevida; falha de mensagem não altera o estado financeiro; site correto mesmo com canal externo em falha. |
| Especificação §14 | Notificação e comunicado: destinatários, canais, conteúdo e resultado de entrega. |
| Cenários §16 | 17 (webhook repetido não duplica mensagem). 24 (falha no canal externo não desfaz o fato nem a notificação no site; completado na E04-04). |
| Infraestrutura 4.2 | Idempotência nas integrações; processamento retomável. |
| Infraestrutura 5 | `UNIQUE` em chaves de idempotência. Nenhum dado pessoal em logs. |
| Infraestrutura 2 | E-mail pelo Amazon SES; tarefas e prazos pelo Procrastinate (E04-03). |
| E04-01 | `Evento`, `Canal`, `CANAIS_POR_EVENTO`, `criar_notificacao`. |

## Escopo

**Dentro:**

- Modelo `Envio`, a fila de saída (padrão *outbox*).
- Funções `emitir_evento` e `emitir_evento_para_varios`.
- Criação dos envios de e-mail. Os envios de WhatsApp entram na E04-04, sobre esta mesma função.
- Fábrica `EnvioFactory`.

**Fora:**

- Execução dos envios, tentativas e retentativas (E04-03).
- Canal externo simulado e consentimento de WhatsApp (E04-04).
- E-mails de acesso, como convite, link e recuperação de senha (E04-05).
- O texto de cada evento, que é da etapa que emite.

## Regras

**Emissão de um evento para uma conta:**

```
emitir_evento(evento, conta, *, titulo, corpo, link=None, chave) -> Notificacao
```

1. Exige uma transação aberta (`connection.in_atomic_block`). Fora dela, levanta `TransactionManagementError`, com o mesmo padrão de `travar_condicoes` (E03-02). Assim a notificação nasce e morre junto com o fato que a causou: se a transação da etapa for desfeita, nada fica gravado.
2. **Idempotência:**
   - se já existe uma `Notificacao` com a mesma `chave`, devolve a existente e não cria nada (nem notificação, nem envio);
   - a verificação usa a restrição `UNIQUE` de `chave`, com `INSERT ... ON CONFLICT DO NOTHING` ou equivalente dentro de um *savepoint*, e não só uma leitura prévia. Duas emissões simultâneas com a mesma chave geram uma notificação.
   - Se a chave existir com conteúdo diferente (evento, conta, título, corpo ou link), levanta `ChaveDeEventoReutilizada`, sem gravar nada. É erro de programação de quem emite.
3. Cria a notificação com `criar_notificacao` (E04-01). As validações e a regra de destinatário valem ali.
4. Para cada canal externo de `CANAIS_POR_EVENTO[evento]`:
   - **`email`:** cria um `Envio` pendente para `conta.email_normalizado`;
   - **`whatsapp`:** nesta fatia, não cria nada. A E04-04 acrescenta a regra.
5. Não envia nada, não chama serviço externo e não agenda tarefa. A E04-03 processa a fila.

**Emissão para várias contas com o mesmo conteúdo:**

```
emitir_evento_para_varios(evento, contas, *, titulo, corpo, link=None, chave_base) -> int
```

- **Chave de cada conta:** `f"{chave_base}:{conta.pk}"`, com as mesmas regras de `emitir_evento`.
- **Gravação em lote:** um número fixo de consultas, que não cresce com o número de contas (critério A-10). Cada conta passa antes por `validar_notificacao` (E04-01). Se qualquer uma falhar, nada é gravado. Em seguida:
  1. as notificações são inseridas em lote, ignorando conflitos de chave;
  2. as existentes são relidas numa consulta, para a comparação de conteúdo de `ChaveDeEventoReutilizada`;
  3. os envios das notificações novas são inseridos em lote.
- **Retorno:** o número de notificações novas.
- **Contas repetidas:** a mesma conta repetida em `contas` gera uma única notificação.

**Quem escolhe os destinatários:** a etapa que emite. Esta fatia não filtra contas por situação.

- Uma conta suspensa recebe normalmente, porque ainda tem pedidos, estornos e retiradas.
- Uma conta removida também, se a etapa a incluir, porque o histórico dela é preservado.
- A regra de quem recebe cada evento pertence à etapa, que conhece o fato. O comunicado, por exemplo, filtra as contas na E04-06.

**Modelo `Envio`** (`apps/notificacoes/models.py`):

| Campo | Regra |
|---|---|
| `canal` | `email` ou `whatsapp` (`Canal`, sem `site`) |
| `tipo` | `CharField` de até 40 caracteres. Nesta fatia, só os valores de `Evento`; a E04-05 acrescenta os três tipos de acesso |
| `notificacao` | FK opcional para `Notificacao`, `PROTECT`; nula só nos e-mails de acesso (E04-05) |
| `conta` | FK opcional para `Conta`, `PROTECT`; nula só no convite, cujo destinatário ainda não tem conta |
| `destino` | e-mail normalizado, no e-mail. No WhatsApp, vazio: o número é lido no envio (E04-04) |
| `assunto` | até 150 caracteres |
| `corpo` | texto; vazio nos e-mails de acesso, que levam segredo (E04-05) |
| `chave` | `UNIQUE`, até 220 caracteres: `f"{notificacao.chave}:{canal}"` |
| `situacao` | `pendente`, `enviado`, `falhou` ou `cancelado`; nasce `pendente` |
| `tentativas` | inteiro, nasce 0 |
| `proxima_tentativa_em` | instante; nasce igual a `criado_em` |
| `criado_em` | `agora()` |
| `concluido_em` | nulo até `enviado`, `falhou` ou `cancelado` |
| `motivo_cancelamento` | vazio, ou um código curto (E04-04) |

- `CHECK`:
  - `situacao` dentro dos valores;
  - `tentativas BETWEEN 0 AND 3`;
  - `concluido_em` nulo se e somente se `situacao = 'pendente'`;
  - nesta fatia, `notificacao` e `conta` são obrigatórias (`NOT NULL` lógico por `CHECK`). A E04-05 relaxa esse `CHECK` só para os tipos de acesso: `notificacao` nula nos três, e `conta` nula só no convite.
- Índice parcial em `proxima_tentativa_em` para `situacao = 'pendente'`.
- **Trigger:**
  - recusa `DELETE`;
  - recusa `UPDATE` de `canal`, `tipo`, `notificacao`, `conta`, `destino`, `assunto`, `corpo`, `chave` e `criado_em`;
  - recusa qualquer `UPDATE` de um envio já concluído (`enviado`, `falhou` ou `cancelado`).

  Só a E04-03 e a E04-04 alteram os campos de estado, e só enquanto o envio está pendente.

**Conteúdo do e-mail** (montado na emissão e congelado no `Envio`):

- `assunto`: `"Orgânicos Méier: " + titulo`, cortado em 150 caracteres.
- `corpo`, em texto simples, nesta ordem:
  1. o `corpo` da notificação;
  2. se houver link, uma linha em branco e `"Acesse: " + ORIGEM_PUBLICA + link`;
  3. uma linha em branco e o rodapé fixo `"Você recebeu este aviso porque tem conta no Orgânicos Méier. As notificações também ficam no seu perfil do site."`.
- Sem HTML: a especificação não exige formatação, e o texto simples evita injeção pelo conteúdo.
- `ORIGEM_PUBLICA` já existe (E02-04).

**Logs:** a emissão não registra e-mail, nome, título nem corpo em log. Em caso de erro, registra só o evento e os ids.

## Interfaces

- `apps/notificacoes/emissao.py`: `emitir_evento`, `emitir_evento_para_varios` e `ChaveDeEventoReutilizada`.
- `apps/notificacoes/models.py`: `Envio`, `SituacaoEnvio`.
- Migração com `CHECK`s, índice e trigger.
- `tests/fabricas.py`: `EnvioFactory`.

## Invariantes

- Toda notificação de evento com e-mail na matriz tem exatamente um `Envio` de e-mail.
- Uma chave nunca gera duas notificações nem dois envios do mesmo canal.
- A emissão nunca fala com serviço externo. Uma falha de envio, portanto, nunca desfaz o fato, porque o envio acontece depois, em outra transação.
- O conteúdo de um envio nunca muda depois de gravado.

## Casos-limite e concorrência

- **Transação da etapa desfeita:** nada fica gravado, nem notificação nem envio.
- **Emissão repetida** (cenário 17: o mesmo webhook processado de novo gera a mesma chave): nenhuma notificação nova e nenhum envio novo.
- **Duas emissões simultâneas com a mesma chave,** em transações diferentes: uma notificação e um envio. A segunda espera a primeira confirmar (conflito na chave única) e então devolve a existente.
- **Evento só de site** (`preco_alterado`): notificação sem nenhum envio.
- **`emitir_evento_para_varios` com lista vazia:** devolve 0 e não grava nada.
- **Conta com papel errado para o evento:** `NotificacaoInvalida` (E04-01). Em lote, nada é gravado.

## Correção E04-R01 — revisão da especificação em 2026-10-17

- **Diagnóstico e regra:** estão na correção E04-R01 da E04-01. O link de qualquer emissão passa pela regra de link interno de `validar_notificacao`. `emitir_evento` e `emitir_evento_para_varios` não ganham validação própria.
- **Lote:** em `emitir_evento_para_varios`, a validação do link continua acontecendo antes de qualquer gravação. Um link recusado não grava nada para nenhuma conta, como as outras violações.
- **Testes obrigatórios:** critério A-15, com Red observado antes do código. Os casos `emitir` e `lote` do probe `test_link_externo_disfarcado_de_relativo_deve_ser_recusado` ficam no arquivo indicado na E04-01.

## Dependências e decisões em aberto

- Depende de E04-01.
- Sem decisões em aberto.
