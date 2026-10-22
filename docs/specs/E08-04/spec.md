# E08-04 — Quitação e destino dos pagamentos aprovados

Fatia 4 de 7 da milestone **E08 — Cobrança: abertura, congelamento e prazos**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Quando o provedor aprova um pagamento, o sistema fica sabendo pela sincronização (E07-03), venha ela de um aviso, de uma tarefa ou de uma busca. Esta fatia decide, uma única vez por pagamento, o destino dele:

- **quita** o pedido; ou
- **gera devolução integral**, com o motivo registrado.

A decisão usa só os horários do provedor (P-6). A ordem de chegada dos eventos não muda o resultado.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §8.3 | Iniciados no prazo e aprovados até `T0 + 48h`: aceitos e quitam. O critério é o horário de aprovação no provedor, e não o da notificação. Aprovados depois de `T0 + 48h`: não quitam e geram devolução. Nunca ignorar dinheiro recebido. Cada pagamento é reconhecido uma vez. Com mais de um pagamento aceito, só um quita, e os outros geram devolução integral. |
| Especificação §9.1 | Motivos de estorno: pagamento depois de `T0 + 48h` e duplicidade (devolução integral). |
| Especificação §12 | "Pagamento confirmado": estado do pagamento e referência ao pedido. |
| Infraestrutura 4.2 | Reconhecimento único. Trava de linha, reconsultando o estado dentro da transação. A decisão depende só do `date_approved`. |
| Infraestrutura 4.3 | "Pagamento já iniciado" = criação no provedor antes de `T0 + 24h`. Criação em `T0 + 24h` ou depois não é aceita e gera devolução. `date_approved = T0 + 48h` exato é aceito. |
| Infraestrutura 4.4 | Aprovados na margem quitam e geram "Pagamento confirmado". Depois de `T0 + 48h`: registrados, não quitam e geram devolução. |
| Cenários §16 | 25, 26 e 39 (parte do pagamento; a identificação na apuração é da E11). |
| Testes técnicos | T-2, T-3. |
| Herdado da E04 | `pagamento_confirmado` emitido na transação do fato (só site e e-mail), com a chave derivada. |
| Herdado da E07 | A quitação usa o sinal `situacao_do_pagamento_mudou` e decide P-6 por `aprovado_no_provedor_em`. A ordem das travas é definida aqui. |

## Escopo

**Dentro:**

- O modelo `DestinoDoPagamento`.
- O serviço `decidir_destino`.
- O receptor do sinal.
- A transição `aguardando_pagamento → pago`.
- O aviso `pagamento_confirmado`.

**Fora:**

- A execução das devoluções, que é a E10. Ela parte dos destinos `devolucao` desta fatia.
- Os lançamentos no livro-razão (E09).
- A apuração e o pagamento informado depois dela (E11).

## Decisões técnicas

- **Destino como registro só de inserção.** `DestinoDoPagamento` tem um registro por `PagamentoNoProvedor` (`UNIQUE`). Esse é o reconhecimento único da decisão comercial: um pagamento nunca quita duas vezes nem gera duas devoluções. A devolução em si, com os estados, a chave e a execução, é da E10.
- **Quem quita entre dois aceitos.** O primeiro pagamento aceito a ser decidido quita, e os seguintes vão para devolução por duplicidade. Os pagamentos do mesmo pedido têm o mesmo valor (o total congelado). Por isso o resultado observável é o mesmo em qualquer ordem: pedido pago, uma devolução integral de igual valor e os mesmos totais. A especificação não diz qual dos dois quita.
- **Ordem das travas:** `PagamentoNoProvedor` → `SituacaoDoPedido` → `TentativaDePagamento` (a mesma da E08-03). O receptor roda dentro da sincronização, que já travou o pagamento, e então trava a situação do pedido.
- **Pagamento aprovado sem horário de aprovação.** É uma anomalia, porque o simulador sempre informa o horário e o Mercado Pago informa `date_approved` (L-4). Nenhum destino é gravado, e um log `error` é registrado. A varredura da margem (E08-05) tenta de novo, e o alerta é da E15.
- **Pedido cancelado por suspensão ou remoção** (E08-06). Se o provedor aprovou antes do cancelamento (`aprovado_no_provedor_em < cancelado_em`), o pedido já estava pago quando a conta foi suspensa. Pela especificação, pedidos pagos são preservados (§2), e o horário do provedor decide (§8.3). Então o pagamento quita, e o cancelamento fica sem efeito, com auditoria. Se o provedor aprovou depois, vai para devolução, com o motivo `pedido_cancelado`. Essa exceção vale só para os motivos `suspensao` e `remocao_da_conta`. A E11 não a estende ao cancelamento por inadimplência, porque um pedido apurado não é editado (§8.3).
- **Valor diferente do total.** Se o provedor informar um valor diferente do total do pedido, o pagamento não quita e vai para devolução com o motivo `valor_divergente`. Isso não acontece com o simulador, e o motivo existe para nunca ignorar dinheiro recebido.

## Regras

### Modelo `DestinoDoPagamento` (`apps/pedidos/models.py`, só inserção, com trigger)

| Campo | Regra |
|---|---|
| `pagamento` | `OneToOne` com `PagamentoNoProvedor` |
| `pedido` | nulo quando não há pedido |
| `destino` | `quita`, `devolucao` ou `sem_pedido` |
| `motivo` | vazio quando `quita`; um dos motivos abaixo quando `devolucao` ou `sem_pedido` |
| `decidido_em` | instante da decisão |

Motivos de `devolucao`:

- `iniciado_fora_do_prazo`;
- `aprovado_apos_a_margem`;
- `duplicidade`;
- `pedido_cancelado`;
- `valor_divergente`.

Motivos de `sem_pedido`:

- `referencia_desconhecida`, quando a referência não leva a um pedido do mesmo ciclo.

### Serviço (`apps/pedidos/quitacao.py`)

```
decidir_destino(pagamento: PagamentoNoProvedor) -> DestinoDoPagamento | None
```

Exige transação e o pagamento já travado: é o caso do receptor, dentro de `sincronizar_pagamento`. A E08-05 chama o serviço depois de travar o pagamento.

1. Se o pagamento não está `aprovado`, devolve `None`.
2. Se já existe destino, devolve o existente, sem gravar nada.
3. Se `aprovado_no_provedor_em` é nulo, grava um log `error` `"Pagamento <id_externo> aprovado sem horário de aprovação"` e devolve `None`.
4. Lê a referência no formato `om-c<ciclo>-p<pedido>`. Se o formato não confere, se o pedido não existe ou se o pedido não é do ciclo indicado, grava `sem_pedido` com `referencia_desconhecida`, um log `error` e uma auditoria `pagamento.destino`.
5. Trava a `SituacaoDoPedido` e lê a abertura: `prazo = T0 + 24h` e `limite = T0 + 48h`.
6. Decide, nesta ordem:

   | Condição | Destino | Motivo |
   |---|---|---|
   | `valor != pedido.total` | `devolucao` | `valor_divergente` |
   | `prazo_encerrado(criado_no_provedor_em, prazo)` | `devolucao` | `iniciado_fora_do_prazo` |
   | `not ate_o_limite(aprovado_no_provedor_em, limite)` | `devolucao` | `aprovado_apos_a_margem` |
   | situação `pago` | `devolucao` | `duplicidade` |
   | situação `cancelado` e `aprovado_no_provedor_em ≥ cancelado_em` | `devolucao` | `pedido_cancelado` |
   | situação `aguardando_pagamento`, ou `cancelado` com `aprovado_no_provedor_em < cancelado_em` | `quita` | — |

7. **Quitação:**
   - a situação passa a `pago`, com `quitado_por` e `quitado_em = aprovado_no_provedor_em`. Se estava `cancelado`, `cancelado_em` e o motivo são limpos;
   - auditoria `pedido.quitar` (sistema), com:
     - `pedido` e `id_externo`;
     - `aprovado_em` em UTC;
     - `na_margem`, verdadeiro quando `aprovado_no_provedor_em ≥ prazo`;
     - `cancelamento_sem_efeito`, com o motivo anterior ou nulo;
   - aviso `pagamento_confirmado` ao comprador:
     - título: "Pagamento confirmado: <fornecedor>";
     - corpo: "Recebemos o pagamento do seu pedido <id> da rodada de <fornecedor>, no valor de R$ <total>. O pedido está pago.";
     - link: `/pedidos/<id>/`;
     - chave: `pagamento_confirmado:<pedido>:<comprador>`.
8. **Devolução ou sem pedido:** grava o destino, a auditoria `pagamento.destino` (sistema, com `id_externo`, `pedido`, `destino` e `motivo`) e um log `warning` com o `id_externo` e o motivo. O aviso `estorno` ao comprador é da E10, quando a devolução for processada.
9. Devolve o destino.

**Receptor** (`apps/pedidos/receptores.py`, ligado no `ready()`):

- em `situacao_do_pagamento_mudou`, com `atual == aprovado`, chama `decidir_destino(pagamento)`;
- uma exceção no receptor desfaz a sincronização inteira (E07-03), e a próxima consulta tenta de novo.

**Exibição:** no detalhe do pedido (E08-03), a situação `pago` mostra "Pago em <dd/mm/aaaa> às <HH:MM> (horário de Brasília).", com o `quitado_em`.

## Interfaces

- `apps/pedidos/models.py`: `DestinoDoPagamento`, com a migração e a trigger.
- `apps/pedidos/quitacao.py`: `decidir_destino`, `MOTIVOS_DE_DEVOLUCAO` e `ler_referencia(texto) -> tuple[int, int] | None`.
- `apps/pedidos/receptores.py`: o receptor.

## Invariantes

- Cada pagamento aprovado tem no máximo um destino.
- Cada pedido tem no máximo um pagamento `quita`.
- Um pedido `pago` sempre aponta para um pagamento com destino `quita`.
- Nenhum pagamento aprovado com horário fica sem destino depois de uma sincronização bem-sucedida.
- O resultado não depende do instante de recebimento do aviso nem da ordem dos eventos.

## Casos-limite e concorrência

- **T-3:** aprovação em `T0 + 47h59`, com o aviso chegando em `T0 + 50h`. Quita, se a apuração ainda não ocorreu. Depois da apuração, a regra é da E11.
- **Fronteiras:** criação em `T0 + 24h − 1 ms` é aceita, e em `T0 + 24h` não. Aprovação em `T0 + 48h` é aceita, e em `T0 + 48h + 1 ms` não.
- **Dois pagamentos aprovados sincronizados ao mesmo tempo:** cada um trava o próprio pagamento e depois a situação do pedido, que põe as decisões em fila. Um quita, e o outro vai para devolução por duplicidade.
- **O mesmo pagamento sincronizado por aviso e por tarefa ao mesmo tempo:** a trava do pagamento (E07-03) põe os dois em fila. Só o primeiro vê a mudança para `aprovado`, e o destino é único.
- **Aprovação no instante do cancelamento** (`aprovar_no_cancelamento`, E08-03 A-11): decide como qualquer aprovação, pelo horário do provedor.

## Dependências e decisões em aberto

- Depende de E04-02, E07-03 e E08-02 a E08-03. O cancelamento usado na regra é da E08-06.
- Sem decisões em aberto.

## Correção E08-R06 — evidência de TDD (2026-10-21)

Origem: parecer do agente 3 sobre `2714a6a`, R06. Os critérios A-16 e A-17 desta fatia recebem o tratamento da seção "Correção E08-R06" de `docs/specs/E08-02/spec.md`:

- a evidência que já existe, ou o registro da não conformidade no `review.md` desta fatia;
- a prova de sensibilidade por mutação.

A decisão de destino desta fatia não muda. A R01, que impedia o pagamento a mais de chegar a ela, é corrigida na E08-05.
