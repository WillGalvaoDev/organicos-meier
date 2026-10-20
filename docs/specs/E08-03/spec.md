# E08-03 — Tentativas de pagamento e cobrança Pix

Fatia 3 de 7 da milestone **E08 — Cobrança: abertura, congelamento e prazos**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Com o pedido congelado, o comprador paga pelo provedor integrado, só por Pix na fase 1. Cada vez que ele pede para pagar, o sistema cria uma tentativa. A tentativa grava a chave de idempotência e agenda a criação da cobrança no provedor (E07-04). Quando a cobrança é criada, o comprador vê o código Pix.

O servidor recusa novas tentativas a partir de `T0 + 24h`, mesmo que a tarefa de bloqueio esteja atrasada.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §8.1 | Uma obrigação de pagamento por comprador e por rodada de fornecedor. Pagamento só pela plataforma integrada. Considerar confirmações assíncronas e expiração. |
| Especificação §8.3 | De `T0` a `T0 + 24h`, o comprador pode pagar. A partir de `T0 + 24h`, nenhuma tentativa nova. |
| Especificação §2, §13 | O comprador ativo paga os pedidos dele. O comprador suspenso consulta os pedidos pagos. |
| Infraestrutura 4.2 | Chave de idempotência gravada antes da chamada, uma por pedido, ciclo e tentativa. `external_reference` com o pedido e o ciclo. Toda chamada é registrada numa tabela, na mesma transação, e executada por uma tarefa. |
| Infraestrutura 4.3 | `T0 ≤ t < T0 + 24h`: o comprador pode criar tentativas. `t ≥ T0 + 24h`: novas tentativas são recusadas no servidor. Comparação com precisão de milissegundos em UTC, e `T0 + 24h` exato já é bloqueado. |
| Infraestrutura 4.5 | Pix com `date_of_expiration = T0 + 24h` [Validar L-1]. |
| Cenários §16 | 12 (parte das tentativas). |
| Testes técnicos | T-1. |
| Herdado da E07 | Cobranças pela interface `Provedor`; chave por pedido, ciclo e tentativa, informada em `agendar_chamada`; criar e cancelar cobrança como operações de `ChamadaAoProvedor`, agendadas na mesma transação; o impasse da correção E07-R01 é evitado com um alvo próprio por tentativa. |

## Escopo

**Dentro:**

- O modelo `TentativaDePagamento`.
- O serviço `pedir_pagamento`.
- As operações `criar_cobranca` e `cancelar_cobranca` de `ChamadaAoProvedor`.
- O disparo imediato da tarefa de chamadas.
- As telas do comprador: a lista de pedidos, o detalhe e o pagamento.
- O erro `FalhaDefinitiva` em `apps/pagamentos/chamadas.py`.

**Fora:**

- O que acontece quando o pagamento é aprovado (E08-04).
- O cancelamento das cobranças em `T0 + 24h` (E08-05). Esta fatia só entrega a operação.
- O cartão (fase 2b).

## Decisões técnicas

- **Uma tentativa aberta por vez.** Uma tentativa está aberta quando:
  - está `solicitada` (cobrança ainda não criada); ou
  - está `criada` e o pagamento dela no provedor continua `pendente`.

  Enquanto há uma tentativa aberta, "Pagar" mostra a cobrança existente, e não cria outra. Uma tentativa nova só nasce quando a anterior terminou sem aprovação: recusada, cancelada, expirada ou não criada. Isso evita cobranças duplicadas por cliques repetidos. A duplicidade que ainda puder acontecer no provedor é tratada na E08-04.
- **Identificadores:**
  - `referencia_externa = "om-c<ciclo>-p<pedido>"`: identifica pedido e ciclo, e é igual em todas as tentativas do pedido;
  - `chave_idempotencia = "om-p<pedido>-t<numero>"`: única por tentativa.
- **Alvos próprios.**
  - A criação usa o alvo `t<tentativa>`.
  - O cancelamento usa `t<tentativa>:<motivo>`, com o motivo `prazo`, `suspensao` ou `remocao_da_conta`.

  Assim, nenhuma transação que trava o pedido espera uma chamada em andamento do mesmo par. É a regra contra impasse da correção E07-R01.
- **A criação respeita o prazo na execução.** O `executar` de `criar_cobranca` relê o prazo antes de chamar o provedor.
  - A partir de `T0 + 24h`, levanta `FalhaDefinitiva("prazo_encerrado")`, e a tentativa fica `nao_criada`. Uma cobrança criada depois do prazo não seria aceita (infraestrutura 4.3) e só geraria devolução.
  - Por isso, quem pede para pagar no último segundo pode receber "não foi possível gerar a cobrança a tempo". O prazo do comprador não é estendido.
- **`FalhaDefinitiva(codigo)`**, nova em `apps/pagamentos/chamadas.py`. É uma falha local tratada como `RecusaDoProvedor`: a chamada fica `falhou`, com o código, e o `falhou` da operação é chamado. Serve para uma operação recusar antes de chamar o provedor.
- **Disparo imediato.** Depois do commit da tentativa (`transaction.on_commit`), o serviço enfileira a tarefa `processar_chamadas_ao_provedor` (E07-04), para o comprador não esperar até um minuto pela execução periódica.
  - Se a tarefa já está na fila, o `queueing_lock` recusa a nova entrada, e a recusa é ignorada.
  - A execução periódica continua garantindo o processamento se o disparo falhar.
- **Sem dados pessoais na cobrança.** A descrição é "Orgânicos Méier — pedido <id>". Os dados para pagar (o código Pix) ficam na tentativa, aparecem só para o dono do pedido e nunca vão para o log.

## Regras

### Modelo `TentativaDePagamento` (`apps/pedidos/models.py`)

| Campo | Regra |
|---|---|
| `pedido`, `numero` | `UNIQUE (pedido, numero)`; `numero` começa em 1 |
| `chave_idempotencia` | única |
| `referencia_externa` | do pedido |
| `situacao` | `solicitada`, `criada` ou `nao_criada` |
| `id_externo` | nulo até a criação; único quando preenchido |
| `dados_para_pagar` | JSON, vazio até a criação |
| `codigo_da_falha` | código curto quando `nao_criada` |
| `solicitada_em`, `criada_em` | instantes; `criada_em` nulo até a criação |

Restrições:

- `UNIQUE (pedido) WHERE situacao = 'solicitada'`;
- `CHECK` de que `criada` exige `id_externo`, e `nao_criada` exige `codigo_da_falha`.

`referencia_externa` também é uma propriedade de `Pedido`.

### Serviço (`apps/pedidos/pagamento.py`)

```
pedir_pagamento(comprador: Conta, pedido: Pedido) -> TentativaDePagamento
```

Numa transação:

1. Trava a `SituacaoDoPedido` e depois as tentativas do pedido.
2. Lê `agora()` depois das travas.
3. **Recusas** (`PagamentoRecusado(codigo)`, com a mensagem de cada código):

   | Código | Quando | Mensagem |
   |---|---|---|
   | `nao_e_seu` | o pedido não é do comprador | — (a rota responde 404) |
   | `prazo_encerrado` | `prazo_encerrado(agora, T0 + 24h)` | "O prazo para pagar este pedido terminou em <dd/mm/aaaa> às <HH:MM> (horário de Brasília)." |
   | `pedido_pago` | situação `pago` | "Este pedido já está pago." |
   | `pedido_cancelado` | situação `cancelado` | "Este pedido foi cancelado e não pode mais ser pago." |
   | `conta_inativa` | comprador que não está ativo | "Sua conta não pode fazer pagamentos no momento." |

4. **Tentativa aberta:** se há uma, devolve essa, sem criar outra nem agendar nada.
5. **Tentativa nova:**
   - cria a `TentativaDePagamento` `solicitada`, com `numero` igual ao maior anterior + 1;
   - agenda `agendar_chamada("criar_cobranca", f"t{tentativa.pk}", parametros={"tentativa": tentativa.pk}, chave_idempotencia=tentativa.chave_idempotencia)`;
   - registra o disparo imediato com `on_commit`;
   - grava a auditoria `pedido.pedir_pagamento` (comprador), com o pedido e o número da tentativa.

Para saber se a tentativa `criada` ainda está aberta, o serviço olha a situação do `PagamentoNoProvedor` de mesmo `id_externo`. Sem esse registro, a tentativa conta como aberta.

### Operação `criar_cobranca`

- **`executar`:**
  - lê a tentativa, o pedido e a abertura, sem trava;
  - se `prazo_encerrado(agora(), T0 + 24h)`, levanta `FalhaDefinitiva("prazo_encerrado")`;
  - senão, chama `provedor.criar_cobranca(NovaCobranca(chave_idempotencia, referencia_externa, pedido.total, "Orgânicos Méier — pedido <id>", expira_em=T0 + 24h, meio="pix"))`.
- **`concluir`:**
  - `sincronizar_pagamento(resultado.pagamento, origem="tarefa")`;
  - depois trava a tentativa e grava `criada`, `id_externo`, `dados_para_pagar` e `criada_em = resultado.pagamento.criado_em`.
- **`falhou`:** trava a tentativa e grava `nao_criada`, com o código (o da `FalhaDefinitiva` ou o da `RecusaDoProvedor`).

### Operação `cancelar_cobranca`

- **Alvo:** `t<tentativa>:<motivo>`. **Parâmetros:** `{"id_externo": ...}`.
- **`executar`:** `provedor.cancelar_cobranca(id_externo)`. `PagamentoNaoEncontrado` segue a regra das 24 horas de `consultar_pagamento` (E07-04).
- **`concluir`:** `sincronizar_pagamento(resultado, origem="tarefa")`. Se o provedor devolver `aprovado` (pagamento concluído no instante do cancelamento), vale o que ele registrou, e a E08-04 decide.

**Função** `agendar_cancelamento(tentativa, motivo)`:

- só agenda se a tentativa está `criada` e o pagamento dela não é terminal;
- é idempotente por par (E07-04);
- exige transação.

### Ordem das travas

`PagamentoNoProvedor` → `SituacaoDoPedido` → `TentativaDePagamento`.

- O `concluir` das operações já chega com o pagamento travado pela sincronização, e então trava a tentativa.
- `pedir_pagamento` trava a situação e as tentativas, e nunca trava o pagamento.
- Ninguém trava um pagamento depois de travar uma situação de pedido. A E11 segue a mesma ordem.

### Telas do comprador

**`GET /pedidos/`** (`pedidos_lista`, `exige_comprador`):

- lista os pedidos do comprador, do mais recente ao mais antigo;
- cada linha mostra fornecedor, total, situação ("Aguardando pagamento até <data e hora>", "Pago", "Cancelado" ou "Prazo encerrado") e o link para o detalhe;
- o comprador suspenso vê a lista, mas sem o botão de pagar.

**`GET /pedidos/<id>/`** (`pedidos_detalhe`, `exige_comprador`; pedido de outro comprador: 404). Mostra:

- os itens, com nome, quantidade e unidade, preço unitário e subtotal;
- produtos, serviço, frete e total;
- o prazo, no fuso da operação, com "Esse prazo de 24 horas não é prorrogado.";
- a situação;
- conforme a tentativa:
  - **aberta e criada:** o código Pix copia e cola, com "Pague pelo aplicativo do seu banco. A confirmação pode levar alguns minutos.";
  - **solicitada:** "Estamos gerando a sua cobrança. Atualize esta página em alguns instantes.";
  - **última `nao_criada` por `prazo_encerrado`:** "Não foi possível gerar a cobrança antes do fim do prazo.";
- o botão "Pagar com Pix", só com o pedido `aguardando_pagamento`, antes do prazo, sem tentativa aberta e com o comprador ativo.

**`POST /pedidos/<id>/pagar/`** (`pedidos_pagar`, `exige_comprador_ativo`, `require_POST`):

- chama `pedir_pagamento` e redireciona para o detalhe;
- `PagamentoRecusado` responde 409, com a página do detalhe e a mensagem;
- pedido de outro comprador: 404.

Nenhuma tela mostra o pedido de outro comprador. O fornecedor e o administrador não usam estas rotas: o administrador acompanha pela E08-05.

## Interfaces

- `apps/pedidos/models.py`: `TentativaDePagamento`, com a migração.
- `apps/pedidos/pagamento.py`: `pedir_pagamento`, `PagamentoRecusado` e `agendar_cancelamento`.
- `apps/pedidos/operacoes.py`: o registro de `criar_cobranca` e `cancelar_cobranca`, carregado no `ready()` do app.
- `apps/pagamentos/chamadas.py`: `FalhaDefinitiva`.
- `apps/pedidos/views.py`, os templates e `config/urls.py`: as três rotas.

## Invariantes

- No máximo uma tentativa aberta por pedido.
- Toda cobrança criada pelo sistema tem a chave da tentativa e a referência do pedido.
- Nenhuma tentativa é criada a partir de `T0 + 24h`, nem cobrança no provedor a partir desse instante pelo sistema.
- Nenhum dado pessoal vai ao provedor nem ao log.

## Casos-limite e concorrência

- **Dois cliques em "Pagar" ao mesmo tempo:** a trava da situação do pedido põe os dois em fila. O segundo encontra a tentativa aberta e a devolve. Uma chamada só.
- **Clique em `T0 + 24h − 1 ms`:** a tentativa é aceita. Se a tarefa só executar depois do prazo, a tentativa fica `nao_criada` com `prazo_encerrado`, e nada é criado no provedor.
- **Provedor fora do ar na criação:** a chamada é repetida com a mesma chave (E07-04). O comprador continua vendo "Estamos gerando…".
- **Falha depois de o provedor criar:** a repetição devolve a mesma cobrança (E07-01 A-11 e R03).
- **Cobrança expirada ou cancelada antes do prazo** (simulador): uma nova tentativa é permitida, com número seguinte e chave nova.

## Dependências e decisões em aberto

- Depende de E02-10, E07-01 a E07-04 e E08-02.
- Sem decisões em aberto.
