# E11-01 — Início da apuração final: autorização, reconsulta e cancelamento dos não pagos

Fatia 1 de 8 da milestone **E11 — Apuração final e fila de pendentes**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável de 2026-10-15, não há revisão separada da especificação. O especificador verificou clareza, testabilidade e ausência de decisões novas. A especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Divisão da E11

| Fatia | Entrega | Depende de |
|---|---|---|
| E11-01 | Início da apuração final: autorização, reconsulta e cancelamento dos não pagos | E08, E07-06 |
| E11-02 | Perda dos itens do fornecedor pelos inadimplentes | E11-01, E05 |
| E11-03 | Caixas invalidadas e mínimo remanescente: o resultado da apuração | E11-02 |
| E11-04 | Rodada viável: estorno proporcional e restauração na fila de pendentes | E11-03, E10-02 |
| E11-05 | Rodada que volta para interesse por pagamentos insuficientes | E11-03, E10-02, E06-06 |
| E11-06 | Aprovação do resultado e avanço para aguardando fornecedor | E11-04, E09-06 |
| E11-07 | Telas da apuração (administrador) e efeitos para o comprador | E11-01 a E11-06 |
| E11-08 | Fila de pendentes de ponta a ponta, com pendentes reais da apuração | E11-04, E05-02 a E05-05 |

**A apuração tem dois atos do administrador, sempre separados:**
1. **Iniciar a apuração** (E11-01 a E11-05), a partir de `T0 + 48h`. Ela:
   - reconsulta o provedor;
   - cancela os não pagos;
   - invalida as caixas e confere o mínimo remanescente.

   Se o mínimo continua atendido, a rodada fica em `pagamento` com o resultado registrado, à espera do avanço. Se não, a rodada volta na hora para interesse (§8.2, passo 7).
2. **Aprovar o resultado** (E11-06): o avanço para "aguardando fornecedor", com a apuração no livro-razão ("apuração final aprovada", infraestrutura 3.2).

Essa separação vem do §7 ("aguardando fornecedor: resultado válido da cobrança é aprovado pelo administrador"), do §8.2 (passo 6: "apresentar resultado ao administrador para avanço") e da infraestrutura 4.4 ("a nova consulta antes da autorização de avanço").

**As devoluções geradas aguardam autorização.** Os estornos proporcionais (E11-04) e as devoluções integrais (E11-05) nascem como obrigações com o comprador (E10-02). A execução de cada uma é autorizada pelo administrador na tela de devoluções da E10 (§7, "o avanço ou a execução dos estornos aguarda decisão administrativa"; §9.2).

**Fronteira com as etapas seguintes:**
- o pedido formal enviado no avanço é da E13;
- o cancelamento da rodada, inclusive depois da apuração, é da E12;
- o fim das parcelas `em_pedido` ao encerrar a rodada é da E14.

## Contexto e objetivo

A partir de `T0 + 48h`, e só por autorização do administrador, a apuração começa. Esta fatia entrega o primeiro trecho dela:
- a recusa no servidor antes de `T0 + 48h`;
- a reconsulta de todos os pedidos do ciclo no provedor, que bloqueia a apuração se o provedor falhar;
- o cancelamento no provedor das tentativas ainda não terminais;
- a identificação dos pagos e dos não pagos pelo horário de aprovação (P-6);
- o cancelamento por inadimplência dos não pagos;
- o registro único da apuração do ciclo.

Ela também fecha a regra dos pagamentos informados depois da apuração: nunca quitam, viram devolução integral (E08-04 e E09-04) e, quando teriam sido aceitos pela P-6, abrem um alerta crítico (infraestrutura 4.4).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7 | Apta para apuração a partir de `T0 + 48h`, só por autorização administrativa, nunca antecipada. Toda intervenção auditada. |
| Especificação §8.2, passo 3.1 e 3.2 | Identificar os pagamentos aceitos (§8.3) e os não pagos; cancelar os não pagos. |
| Especificação §8.3 | Aceitação pelo horário de aprovação até `T0 + 48h`. Pagamentos comunicados tardiamente não editam pedidos apurados e são tratados financeiramente, com auditoria. |
| Especificação §7.1 | Cancelamento por inadimplência é mudança de estado, sem alterar a composição do pedido. |
| A2, P-6, P-8 | Apuração a partir de `T0 + 48h`, com autorização; aceitação pelo horário de aprovação; nunca antecipada. |
| Infraestrutura 4.3 | Apuração recusada no servidor antes de `T0 + 48h`. Ordem: reconsulta e busca por referência, cancelamento das tentativas não terminais, P-6, passos do §8.2. Provedor indisponível bloqueia a apuração. Fronteira: `T0 + 48h` exato já pode. |
| Infraestrutura 4.4 | Pagamento informado depois da apuração com aprovação até `T0 + 48h`: registrado, alerta crítico, tratamento financeiro auditado, sem editar o pedido. |
| Herdado da E07 | A apuração chama `consultar_antes_de_decidir` para cada referência do ciclo e fica bloqueada com `ConsultaAoProvedorFalhou`. |
| Herdado da E08 | `pode_iniciar_apuracao` (E08-05) e T-4 completo. Pedido `cancelado` (suspensão ou remoção) é não pago. A exceção "aprovado antes do cancelamento quita" vale só para `suspensao` e `remocao_da_conta`, nunca para o cancelamento por inadimplência nem depois da apuração. Ordem de travas `PagamentoNoProvedor` → `SituacaoDoPedido` → `TentativaDePagamento`. |
| Herdado da E09 | Pagamento informado depois da apuração (cenário 51, T-19) entra pelo destino `devolucao` da E08-04 e vira obrigação (E09-04). |
| Cenários §16 | 26 (na apuração) e 51 (na parte da apuração) |
| Testes técnicos | T-4 (completo), T-7 (com a apuração) e T-19 (na parte da apuração) |

## Escopo

**Dentro:**
- O registro `ApuracaoFinal`, um por ciclo.
- O serviço `iniciar_apuracao(autor, rodada)` com os passos desta fatia.
- O motivo de cancelamento `inadimplencia`.
- A regra de destino dos pagamentos depois da apuração e o alerta crítico.

**Fora:**
- A perda dos itens pelos inadimplentes (E11-02).
- As caixas, o mínimo e o resultado (E11-03).
- Os efeitos do resultado (E11-04 e E11-05).
- O avanço (E11-06).
- As telas (E11-07). Nesta fatia, o serviço é testado diretamente.

## Modelo

**`ApuracaoFinal`** (só inserção; app `pedidos`):
- `ciclo` (um para um, único);
- `abertura` (um para um);
- `autor` (o administrador);
- `iniciada_em` (o instante lido depois das travas);
- `pedidos_pagos` e `pedidos_nao_pagos` (contagens).

A E11-03 acrescenta o resultado.

**`MotivoDoCancelamento.INADIMPLENCIA = "inadimplencia"`**, "Falta de pagamento". A restrição `situacao_do_pedido_coerente` aceita o novo valor.

## Regras

**`iniciar_apuracao(autor, rodada) -> ApuracaoFinal`**

1. **Autor:** administrador. Senão, `PermissionDenied`.
2. **Só fora de transação.** A função consulta o provedor antes da decisão (contrato da E07-06, infraestrutura 4.2). Chamada dentro de outra transação, levanta `RuntimeError` antes de qualquer consulta, como a nova tentativa manual da E10-04 (P1).
3. **Conferência prévia, sem travas:**
   - a rodada está em `pagamento`, com a abertura do ciclo vigente;
   - o ciclo ainda não tem `ApuracaoFinal`;
   - `pode_iniciar_apuracao(abertura, agora())` é verdadeiro.

   Senão, `ApuracaoRecusada` com o código, sem consulta e sem escrita. Esta conferência evita consultas inúteis; a decisão vale só a do passo 5.
4. **Reconsulta:** `consultar_antes_de_decidir(pedido.referencia_externa)` para cada pedido da abertura, na ordem de `pk`. Com isso:
   - a sincronização da E07-06 registra o que o provedor tem;
   - a decisão de destino da E08-04 aplica a P-6 a cada pagamento aprovado.

   Uma `ConsultaAoProvedorFalhou` interrompe a apuração e é propagada, sem `ApuracaoFinal` e sem cancelamento. O que as sincronizações anteriores gravaram fica, porque é registro do provedor.
5. **Decisão, numa transação:**
   - **Travas, nesta ordem:**
     - o fornecedor;
     - a rodada;
     - todos os produtos do fornecedor, por `pk`, inclusive os de fora do estoque da rodada (a E11-02 remove pendentes deles);
     - em cada produto, o estoque da rodada, quando houver, e as parcelas (`travar_parcelas`), para as fatias seguintes;
     - as `SituacaoDoPedido` de todos os pedidos da abertura, por `pedido_id`.

     A ordem segue a das operações de interesse (E05-07) e, depois, a da E08-03 (a situação vem depois do pagamento, e a apuração não trava pagamento nenhum).
   - **Releitura:** o instante é lido depois das travas. São refeitas as três conferências do passo 3, agora sob as travas. A primeira recusa vale, sem escrita.
   - **Classificação:**
     - **pago:** `situacao = pago`;
     - **não pago:** `aguardando_pagamento`, ou `cancelado` por qualquer motivo.
   - **Cancelamento por inadimplência:** cada `aguardando_pagamento` passa a `cancelado`, com `cancelado_em` igual ao instante da apuração e o motivo `inadimplencia`. Os pedidos já cancelados por suspensão ou remoção continuam como estão.
   - **Tentativas não terminais:** para cada pedido da abertura, pago ou não, cada `TentativaDePagamento` `criada` passa por `agendar_cancelamento(tentativa, "apuracao")`. Ela só agenda se o pagamento da tentativa não é terminal (E08-03). O alvo próprio do motivo evita esperar uma chamada em andamento (E07-R01).
   - **Registro:** a `ApuracaoFinal` e a auditoria `rodada.apuracao_final` (autor: o administrador), com:
     - rodada e ciclo;
     - `iniciada_em`;
     - os `pk` dos pedidos pagos;
     - os `pk` dos não pagos, com a situação de cada um antes da apuração;
     - os `pk` dos cancelados agora.

**Recusas (`ApuracaoRecusada(codigo)`, com a mensagem para a tela):**

| Código | Mensagem |
|---|---|
| `fora_de_pagamento` | "Só uma rodada na etapa de pagamento pode ser apurada." |
| `antes_do_prazo` | "A apuração só pode começar a partir de {dd/mm/aaaa} às {hh:mm} (horário de Brasília)." Com `T0 + 48h`. |
| `ja_apurada` | "A apuração deste ciclo já foi feita." |

**Pagamentos informados depois da apuração** (ajuste da decisão de destino, E08-04):
- Depois que o ciclo tem `ApuracaoFinal`, nenhum pagamento quita um pedido não pago, qualquer que seja o motivo do cancelamento e o horário de aprovação. O destino é `devolucao`, com o motivo `pedido_cancelado`.
- O cancelamento por `inadimplencia` também nunca é desfeito por um pagamento, mesmo aprovado antes de `cancelado_em`.
- A exceção da E08-04 ("aprovado antes do cancelamento quita") continua valendo só para `suspensao` e `remocao_da_conta`, e só enquanto o ciclo não foi apurado.
- **A conferência fica sob a trava da situação do pedido,** que a decisão de destino já toma. A apuração segura essa trava de todos os pedidos do ciclo até gravar a `ApuracaoFinal`. Por isso, o pagamento e a apuração dão o mesmo resultado em qualquer ordem:
  - se o pagamento chega antes, o pedido está pago na apuração;
  - se chega depois, o pedido já está cancelado, e vira devolução.
- **Alerta crítico** (infraestrutura 4.4): quando o destino `devolucao` é decidido para um pedido de ciclo apurado, e o pagamento teria quitado pela P-6, abre o alerta `aprovado_no_prazo_depois_da_apuracao`. Teria quitado quando:
  - o valor é igual ao total;
  - foi criado antes de `T0 + 24h`;
  - foi aprovado até `T0 + 48h`.

  Detalhes do alerta:
  - gravidade crítica, aberto uma vez por pagamento;
  - dados: pedido, comprador, valor e horário de aprovação;
  - resolvido quando a obrigação do pagamento é totalmente liquidada, como os de `aprovado_apos_a_margem` e `duplicidade` (E09-06).

  A obrigação de devolução integral nasce pelo caminho que já existe (E09-04), financiada pelo próprio pagamento.

## Interfaces

- `iniciar_apuracao(autor, rodada) -> ApuracaoFinal`.
- `ApuracaoRecusada(codigo)`, com `codigo` e `mensagem`.
- `ApuracaoFinal`.
- `MotivoDoCancelamento.INADIMPLENCIA`.
- `TipoDeAlerta.APROVADO_NO_PRAZO_DEPOIS_DA_APURACAO`, crítico.

## Decisões técnicas

- **A rodada continua em `pagamento` até o avanço.** O §7 diz que os nomes das etapas são funcionais. A "apuração feita" é o registro `ApuracaoFinal`, e não uma etapa nova. Assim, nada que dependa de `pagamento` muda: as interações de interesse continuam bloqueadas e as condições continuam congeladas.
- **Reconsulta de todos os pedidos, inclusive os pagos.** A infraestrutura 4.3 manda reconsultar "todas as tentativas". A reconsulta de um pedido pago detecta duplicidades, que a E08-04 já trata.
- **O pagamento, não a situação, decide.** A classificação lê `SituacaoDoPedido` sob trava, depois de a reconsulta ter aplicado a P-6. A apuração não aplica a P-6 por conta própria, porque a decisão de destino é única (E08-04).

## Invariantes

- Um ciclo tem no máximo uma `ApuracaoFinal`.
- Depois da apuração, nenhum pedido do ciclo está `aguardando_pagamento`.
- Nenhum pedido não pago passa a pago depois da apuração.
- A apuração nunca altera `Pedido`, `ItemDoPedido` nem `ParcelaNoPedido`.

## Casos-limite e concorrência

- **`T0 + 48h − 1 ms`:** recusada, mesmo com 100% pago. **`T0 + 48h` exato:** aceita.
- **Pagamento aprovado exatamente em `T0 + 48h` e informado só na reconsulta:** quita antes da classificação, pela P-6.
- **Pagamento aprovado depois de `T0 + 48h`:** devolução integral (cenário 26). O pedido fica não pago e é cancelado.
- **Duas apurações em paralelo:** uma registra; a outra recebe `ja_apurada` depois de esperar as travas, sem escrita.
- **Apuração e aviso de pagamento ao mesmo tempo, sobre o mesmo pedido** (T-7): o mesmo resultado em qualquer ordem, como descrito acima.
- **Apuração e suspensão do comprador ao mesmo tempo:** serializadas pela trava do fornecedor. Se a suspensão vem antes, o pedido está cancelado por suspensão e é não pago. Se vem depois, o pedido já está cancelado por inadimplência, e a suspensão não o muda.

## Dependências e decisões em aberto

Depende de E08-02 a E08-06 e de E07-06. Nenhuma decisão em aberto. O comportamento real do provedor na busca por referência continua limite L-6.
