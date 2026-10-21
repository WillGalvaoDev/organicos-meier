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

## Correção E08-R02 e E08-R03 — criação de cobrança que não pode mais ser paga (2026-10-21)

Origem: parecer do agente 3 sobre `2714a6a` (`docs/specs/E08-01/review.md`, R02 e R03). A parte do bloqueio está na E08-05 e a da moderação na E08-06, cada uma na sua seção de correção.

### Diagnóstico

As duas falhas têm a mesma raiz. A operação `criar_cobranca` só sabe recusar por prazo. Além disso, ela trata a recusa como prova de que nada existe no provedor.

- **R02, pedido cancelado com a tentativa ainda `solicitada`.** A moderação só cancela as tentativas `criada`, e o `executar` não confere a situação do pedido. A cobrança nasce depois do cancelamento e fica `pendente`, sem chamada de cancelamento. O mesmo acontece quando a moderação chega enquanto a chamada ao provedor está em andamento: o `concluir` grava `criada` sem olhar o pedido.
- **R03, resposta perdida perto de `T0 + 24h`.** O provedor criou a cobrança, mas a resposta se perdeu. Na repetição, depois do prazo, o `executar` recusa antes de chamar o provedor e a tentativa vira `nao_criada`. A cobrança continua `pendente` no provedor e nada a cancela, porque o bloqueio só percorre tentativas `criada`.

### Decisão técnica: a recusa sempre procura o que existe no provedor

O sistema não tem como saber, pelos próprios registros, se uma execução anterior chegou ao provedor.

- **Contador de tentativas.** O contador da chamada não serve como prova. Uma falha local no `concluir` desfaz a transação da chamada inteira, e o contador volta junto, embora o provedor já tenha criado a cobrança.
- **Solução: perguntar ao provedor.** Toda criação recusada busca a cobrança pela referência do pedido (`buscar_por_referencia`) antes de terminar, e cancela o que achar pendente sem tentativa vinculada. Assim:
  - se a execução nunca chegou ao provedor, a busca não acha nada e a tentativa só fica `nao_criada`;
  - se o resultado ficou incerto, a cobrança que existe é encontrada e cancelada.
- **Nenhuma cobrança nova depois do prazo nem para pedido cancelado.** A proibição continua. A busca só lê, e a recusa nunca chama `criar_cobranca`.

**Cobrança órfã:** um pagamento da referência do pedido que está `pendente` e cujo `id_externo` não é o de nenhuma `TentativaDePagamento`. Ela só aparece quando a resposta da criação se perdeu, porque toda criação concluída vincula o pagamento à tentativa.

### Regras

**`FalhaDefinitiva`** (`apps/pagamentos/chamadas.py`) ganha um argumento opcional, só de palavra-chave: `encontrados: tuple[PagamentoConsultado, ...] = ()`. O tratamento em `_tentar` não muda: a chamada fica `falhou`, com o código, e o `falhou` da operação recebe a exceção.

**`criar_cobranca` — `executar`**, com as leituras sem trava:

1. Lê a tentativa, o pedido, a abertura e a `SituacaoDoPedido`.
2. Decide o motivo de recusa, nesta ordem:

   | Ordem | Condição | Código |
   |---|---|---|
   | 1 | `not aceita_tentativas(abertura, agora())` | `prazo_encerrado` |
   | 2 | situação `cancelado` | `pedido_cancelado` |
   | 3 | situação `pago` | `pedido_pago` |

3. **Com motivo de recusa:**
   - chama `provedor.buscar_por_referencia(tentativa.referencia_externa)`;
   - levanta `FalhaDefinitiva(codigo, encontrados=tuple(resultado))`.

   Se a busca falhar:
   - com `ProvedorIndisponivel`, a exceção segue e a chamada é repetida como falha temporária. A tentativa continua `solicitada` até o provedor responder, e nada se perde;
   - com `RecusaDoProvedor`, levanta `FalhaDefinitiva(codigo)` sem `encontrados` e grava um log `warning` com a tentativa e o código da recusa. A cobrança, se existir, fica para a reconsulta da margem e o bloqueio (E08-05).
4. **Sem motivo de recusa:** cria a cobrança, como hoje.

**`criar_cobranca` — `falhou`**, na ordem das travas (pagamento → situação do pedido → tentativa):

1. Sincroniza cada pagamento de `encontrados` com `sincronizar_pagamento(..., origem="busca")`. Isso vale também para um pagamento aprovado, porque dinheiro nunca é ignorado (§8.3) e a E08-04 decide o destino pelo receptor do sinal.
2. Para cada cobrança órfã entre os encontrados, ordenada por `criado_em` e `id_externo` e numerada de 1 a `n`:
   - agenda `agendar_chamada("cancelar_cobranca", f"t{tentativa.pk}:recuperacao:{n}", parametros={"id_externo": ...})`;
   - grava um log `warning` "Cobrança sem tentativa encontrada na recusa da criação", com a tentativa, o `id_externo` e o código.
3. Trava a tentativa e grava `nao_criada`, com o código, como hoje.

O alvo `t<tentativa>:recuperacao:<n>` só é agendado por este `falhou`, que roda uma vez por chamada. Nenhuma outra transação espera essa chamada, então vale a regra contra impasse da correção E07-R01.

**`criar_cobranca` — `concluir`**, para a moderação que chega com a criação em andamento:

1. `sincronizar_pagamento(resultado.pagamento, origem="tarefa")`, como hoje. Isso trava o pagamento.
2. **Novo:** trava a `SituacaoDoPedido` do pedido.
3. Trava a tentativa e grava `criada`, como hoje.
4. **Novo:** se a situação travada é `cancelado`, chama `agendar_cancelamento(tentativa, situacao.motivo_do_cancelamento)`. Se é `pago`, chama `agendar_cancelamento(tentativa, "pedido_pago")`.

O motivo `pedido_pago` entra na lista de motivos do alvo de cancelamento, ao lado de `prazo`, `suspensao` e `remocao_da_conta`.

**Ordem das travas.** O `concluir` segue `PagamentoNoProvedor` → `SituacaoDoPedido` → `TentativaDePagamento`, sem exceção.

**Espera da moderação.** Ela trava a situação do pedido, e o `concluir` só segura essa trava depois que o provedor respondeu. Por isso a moderação nunca espera uma chamada externa.

Com isso, a moderação e a criação chegam ao mesmo resultado em qualquer ordem:

| O que acontece primeiro | Resultado |
|---|---|
| A moderação, antes do `executar` | a criação é recusada com `pedido_cancelado` e não chama `criar_cobranca` |
| O `executar`, com a moderação durante a chamada | o `concluir` vê `cancelado` e agenda o cancelamento |
| O `concluir`, antes da moderação | a moderação vê a tentativa `criada` e agenda o cancelamento (E08-06) |

**Tela do detalhe.**

- A mensagem "Estamos gerando a sua cobrança…" só aparece quando o pedido está `aguardando_pagamento` e ainda dentro do prazo.
- Uma tentativa `nao_criada` com o código `pedido_cancelado` ou `pedido_pago` não mostra mensagem de tentativa: a situação do pedido já explica.

### Casos-limite

- **A busca demora a mostrar a cobrança** (atraso de consistência, L-6). A recusa não acha nada e a tentativa fica `nao_criada`. A cobrança é achada depois pela reconsulta da margem, pela referência, e cancelada pelo bloqueio por pagamento (E08-05, correção E08-R03). Ela também vence sozinha em `T0 + 24h` (`expira_em`).
- **O comprador não consegue pagar a cobrança órfã.** Os dados para pagar se perderam com a resposta e nunca foram mostrados. Se um pagamento aprovado aparecer mesmo assim, a sincronização no `falhou` leva a decisão à E08-04.
- **Cancelamento repetido.** A recuperação e o bloqueio podem agendar o cancelamento da mesma órfã por alvos diferentes. O bloqueio pula o pagamento que já tem uma chamada de cancelamento (E08-05). Se as duas chegarem a executar:

- no simulador, a segunda encontra a cobrança já terminal e só sincroniza a mesma situação;
- no provedor real, o comportamento de cancelar uma cobrança já cancelada não foi validado (L-2). Uma recusa dele deixa só a segunda chamada `falhou`, sem efeito sobre o pagamento.

## Correção E08-R08 — recuperação de vários pagamentos sem inverter as travas (2026-10-21)

Origem: segunda revisão do agente 3, sobre `584b323` (`docs/specs/E08-01/review.md`, R08). É uma correção técnica, sem decisão comercial nova.

### Diagnóstico

O `falhou` da `criar_cobranca` (`apps/pedidos/operacoes.py`, `_criacao_falhou`) roda dentro da transação da chamada, aberta por `processar_chamadas`. Ele sincroniza, um depois do outro, todos os pagamentos que a busca encontrou.

1. A sincronização do primeiro pagamento (P1) trava P1. Se ele está aprovado, o receptor decide o destino e trava também a `SituacaoDoPedido` (S). As duas travas ficam até o fim da transação da chamada.
2. Ao mesmo tempo, o aviso do segundo pagamento (P2) trava P2 e espera S para decidir o destino.
3. A recuperação passa para P2 ainda segurando S e espera P2. A ordem fica S → P2, o inverso da ordem global P → S → T.
4. O PostgreSQL aborta uma das duas com `deadlock detected`.

Repetir depois recupera os dois destinos sem duplicá-los. Mesmo assim, uma sincronização financeira é abortada por uma inversão de travas que a correção R03 introduziu.

Só ordenar os pagamentos não resolve, porque a transação continua segurando S quando vai buscar o pagamento seguinte. Travar todos os pagamentos antes também não serve: um pagamento ainda desconhecido teria de ser inserido fora de `sincronizar_pagamento`, que é o único que grava `PagamentoNoProvedor` (E07-03, cenário 37).

### Decisão técnica: a recuperação agenda uma consulta por pagamento

O `falhou` deixa de sincronizar. Cada pagamento encontrado é entregue à operação `consultar_pagamento` da E07, que roda numa transação própria. Esse é o padrão da E07-06: uma sincronização individual por transação curta.

Assim a recuperação não trava nenhum pagamento e nenhuma situação de pedido, e a ordem P → S → T fica preservada em cada consulta. O dinheiro continua sem ser ignorado: as consultas são gravadas na mesma transação que marca a tentativa, então ou existem todas, ou a chamada inteira volta a `pendente` e é repetida.

### Regras

**1. O `falhou` da `criar_cobranca`,** quando a busca encontrou pagamentos, faz nesta ordem e na transação da chamada:

1. **Agenda uma consulta por pagamento.** Para cada pagamento encontrado, em qualquer situação e na ordem de `(criado_em, id_externo)`, agenda `consultar_pagamento` com alvo igual ao `id_externo` e `parametros={"origem": "busca"}`.
   - Se o par já tiver uma consulta pendente (de um aviso, por exemplo), ela absorve o agendamento pela regra de combinação da E07-06. A origem resultante segue essa regra.
2. **Agenda o cancelamento das órfãs.** As cobranças órfãs são as pendentes na resposta da busca e sem tentativa com esse `id_externo`. Cada uma recebe o cancelamento com alvo `t<tentativa>:recuperacao:<n>` e o log `warning`, como na correção R03. A identificação usa só a resposta da busca e as tentativas, sem travar o pagamento.
3. **Marca a tentativa** como `nao_criada`, com o código.

O `falhou` não chama `sincronizar_pagamento` nem `decidir_destino`. Ele também não trava `PagamentoNoProvedor` nem `SituacaoDoPedido`.

**2. O registro de cada pagamento encontrado** passa a nascer na consulta, com a resposta atual do provedor:

- se o provedor estiver indisponível ou o pagamento ainda não aparecer (L-6), vale a falha temporária da E07;
- o destino de um aprovado é decidido pela E08-04 dentro dessa consulta.

**3. O que não muda:**

- a recusa no `executar` e a busca, com a ordem `prazo_encerrado`, `pedido_cancelado`, `pedido_pago`;
- a `RecusaDoProvedor` na busca;
- o `concluir` da criação, que sincroniza um único pagamento na ordem P → S → T;
- nenhuma cobrança é criada depois do prazo.

**4. Invariante nova:** nenhuma transação de chamada ao provedor sincroniza mais de um pagamento. Quem precisa sincronizar vários usa uma transação curta por pagamento, como `consultar_antes_de_decidir`, ou agenda uma consulta por pagamento. O implementador confere os outros chamadores de `sincronizar_pagamento` e registra o resultado. Se outro caminho violar a invariante, ele para e devolve ao especificador, sem ampliar o escopo.

### Efeito nos critérios da correção R03

Nos critérios A-23 a A-26, o pagamento encontrado passa a ser registrado pela consulta agendada, e não mais pelo `falhou`. Por isso a observação acontece depois do `processar_chamadas()` que processa essa consulta.

- O comportamento observado fica igual: o registro, o destino, o cancelamento da órfã e nenhuma criação depois do prazo.
- O único ajuste permitido nos testes existentes é acrescentar a chamada a `processar_chamadas()` necessária, ou mover a asserção para depois dela.
- O implementador lista cada teste ajustado no registro, com o antes e o depois.
- No A-26, onde está "o `falhou` sincroniza o pagamento `aprovado`", passa a valer: "a consulta agendada pelo `falhou` sincroniza o pagamento `aprovado`".

### Prova do revisor

A prova R08 do parecer pausa a recuperação dentro de `operacoes.sincronizar_pagamento`. Depois da correção, o `falhou` não chama mais essa função. A pausa nunca acontece, e a thread do aviso falha na espera dela.

A prova fica substituída pelo A-29, que reproduz a mesma corrida com um ponto de pausa que existe antes e depois da correção. O A-29 também serve como Red real.

### Casos-limite

| Caso | Comportamento |
|---|---|
| Uma exceção no `falhou` depois de agendar | A transação da chamada é desfeita: nenhuma consulta, nenhum cancelamento, a tentativa continua `solicitada` e a chamada `pendente`. A repetição refaz a recusa e a busca e termina com um destino por pagamento e um cancelamento por órfã. |
| A busca devolve o mesmo pagamento que um aviso já mandou consultar | Fica uma consulta pendente só para esse `id_externo`, e um destino só. |
| A órfã é aprovada entre a busca e a consulta | A consulta registra `aprovado` e a E08-04 decide o destino. O cancelamento agendado devolve o estado terminal (E07), e o destino não muda. |
| A consulta falha por indisponibilidade | A consulta fica `pendente` com nova tentativa. A tentativa já está `nao_criada`, e o dinheiro é reconhecido quando a consulta conseguir. A reconsulta da margem (E08-05) também cobre esse pagamento. |
