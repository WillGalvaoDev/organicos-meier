# E08-06 — Pedidos de comprador suspenso ou removido

Fatia 6 de 7 da milestone **E08 — Cobrança: abertura, congelamento e prazos**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Quando o administrador suspende ou remove um comprador, os interesses dele já saem (E05-07). Esta fatia trata os pedidos do comprador que ainda não foram pagos:

- o pedido é cancelado;
- as cobranças pendentes são canceladas no provedor;
- os pedidos pagos são preservados.

Um pagamento que o provedor aprovou antes do cancelamento quita o pedido mesmo assim. Um aprovado depois gera devolução (E08-04).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Comprador suspenso: "Interesses e pedidos não pagos são removidos/cancelados." Suspensão reversível. Consulta os pedidos pagos. Comprador removido: acesso bloqueado definitivamente, histórico financeiro preservado, pedidos pagos não são apagados. |
| Especificação §6.3, §7.1 | Não redistribuir compradores entre caixas por inadimplência. O cancelamento é um estado registrado à parte, sem alterar a composição. |
| Especificação §8.3 | Nunca ignorar dinheiro recebido. O horário de aprovação do provedor decide. |
| Cenários §16 | 19 (parte do pedido). |
| Herdado da E02 | Cancelamento dos pedidos não pagos do comprador suspenso, ligado ao sinal `conta_suspensa` (E02-08), com os pedidos pagos preservados para retirada. |
| Herdado da E05 | Tratar o pedido não pago de conta removida durante o prazo de pagamento. Se o destino não puder ser deduzido, levar a pergunta ao responsável. |

## Escopo

**Dentro:**

- Os receptores de `conta_suspensa` e `conta_removida`.
- O serviço `cancelar_pedidos_nao_pagos`.
- A transição `aguardando_pagamento → cancelado`.

**Fora:**

- A caixa que fica incompleta pelo pedido cancelado. A invalidação e o estorno proporcional dos outros compradores são da apuração (E11, §8.2 passo 3), que trata o pedido cancelado como não pago.
- A liberação das parcelas `em_pedido` do comprador cancelado, também da apuração (E11).
- A devolução do pagamento que chegar depois (E10, a partir do destino da E08-04).

## Decisões técnicas

- **Remoção da conta igual à suspensão, para os pedidos.** A especificação diz o que acontece com o pedido não pago do suspenso (é cancelado), mas não do removido. O destino é dedutível sem decisão nova:
  - a remoção é definitiva e bloqueia o acesso, então o removido não consegue pagar no site;
  - a E05-07 (D-1) já tratou os interesses do removido como os do suspenso;
  - os pedidos pagos são preservados nos dois casos (§2).

  Por isso, a pergunta ao responsável não é necessária. O motivo fica registrado (`remocao_da_conta`), para que a E11 e a E10 saibam a origem.
- **Pago é o que o provedor aprovou antes.** O horário de aprovação do provedor decide (§8.3). Um pagamento aprovado antes do instante da suspensão significa que o pedido já estava pago, mesmo que o sistema ainda não soubesse. Nesse caso, a E08-04 quita o pedido e deixa o cancelamento sem efeito, com auditoria. Não há outro caminho em que um pedido cancelado volte a ser pago.
- **Cancelar sem esperar o provedor.** O cancelamento do pedido é local e imediato, na transação da moderação. As cobranças pendentes são canceladas no provedor por `ChamadaAoProvedor`, com o alvo `t<tentativa>:suspensao` ou `t<tentativa>:remocao_da_conta`. São alvos diferentes do bloqueio por prazo, então a moderação não espera nenhuma chamada em andamento (correção E07-R01).
- **Reativação não restaura o pedido.** A especificação cancela o pedido não pago na suspensão e não prevê restaurá-lo na reativação. Depois do `T0`, o pedido também não pode ser recriado (§7.1). O pedido cancelado continua cancelado.
- **Sem aviso ao comprador.** A §12 não tem evento para essa situação. O suspenso vê os pedidos na lista (E08-03), com a situação "Cancelado".

## Regras

### Serviço (`apps/pedidos/cancelamento.py`)

```
cancelar_pedidos_nao_pagos(conta: Conta, *, motivo: str) -> int
```

- Exige transação e `motivo` igual a `suspensao` ou `remocao_da_conta` (`ValueError`).
- Com uma conta que não é de comprador, devolve 0.
- Procura as `SituacaoDoPedido` `aguardando_pagamento` dos pedidos da conta, em qualquer abertura. Em cada uma, por `pedido_id`:
  1. trava a situação;
  2. grava `cancelado`, com `cancelado_em = agora()` (lido depois da trava) e o motivo;
  3. chama `agendar_cancelamento(tentativa, motivo)` para cada tentativa `criada` com pagamento não terminal;
  4. grava a auditoria `pedido.cancelar` (sistema), com o pedido, o motivo e `cancelado_em` em UTC.
- Pedidos `pago` e `cancelado` não mudam.
- Devolve quantos pedidos cancelou.

### Receptores (`apps/pedidos/receptores.py`)

- `conta_suspensa`: `cancelar_pedidos_nao_pagos(conta, motivo="suspensao")`.
- `conta_removida`: `cancelar_pedidos_nao_pagos(conta, motivo="remocao_da_conta")`.

Os dois rodam na transação da moderação, depois dos receptores de interesses (E05-07). Uma exceção desfaz a moderação inteira.

### Ordem das travas

A moderação trava a conta (E02-08) e os fornecedores, a rodada, os produtos e as parcelas (E05-07). Depois, esta fatia trava as `SituacaoDoPedido`. Ela nunca trava um `PagamentoNoProvedor`, então segue a ordem da E08-03:

`PagamentoNoProvedor` → `SituacaoDoPedido` → `TentativaDePagamento`.

## Interfaces

- `apps/pedidos/cancelamento.py`: `cancelar_pedidos_nao_pagos` e `MOTIVOS_DE_CANCELAMENTO`.
- `apps/pedidos/receptores.py`: os dois receptores.

## Invariantes

- A suspensão e a remoção nunca mudam um pedido `pago`.
- Nenhum pedido cancelado por moderação aceita tentativa nova (E08-03, `pedido_cancelado`).
- A composição do pedido cancelado, as caixas e as parcelas `em_pedido` não mudam nesta etapa.

## Casos-limite e concorrência

- **Suspensão antes da abertura:** não há pedido. Os interesses saem pela E05-07, e a abertura refaz as caixas (E08-02).
- **Suspensão com cobrança pendente que o comprador paga logo depois:** o provedor aprova depois de `cancelado_em`. O destino é `devolucao` com `pedido_cancelado` (E08-04).
- **Suspensão no mesmo instante da aprovação:** só quita se `aprovado_no_provedor_em < cancelado_em`. A igualdade vai para devolução (E08-04 A-12).
- **Suspensão e pagamento ao mesmo tempo:** `pedir_pagamento` trava a situação do pedido. Se ele vem antes, a tentativa criada é cancelada pela suspensão logo em seguida. Se vem depois, recebe `pedido_cancelado` ou `conta_inativa`.
- **Reativação:** o pedido continua `cancelado`.

## Dependências e decisões em aberto

- Depende de E02-08, E05-07 e E08-02 a E08-04.
- Sem decisões em aberto. A dedução sobre a conta removida está registrada nas Decisões técnicas.

## Correção E08-R02 — cobrança só enfileirada na suspensão ou na remoção (2026-10-21)

Origem: parecer do agente 3 sobre `2714a6a` (`docs/specs/E08-01/review.md`, R02).

### Diagnóstico

Quando a moderação chega, a tentativa pode estar só `solicitada`. A criação da cobrança ainda está na fila, ou já em andamento no provedor.

- A moderação só agendava cancelamento para tentativas `criada`.
- O `executar` da criação não conferia o pedido, e o `concluir` também não.
- Resultado: o pedido ficava `cancelado`, mas uma cobrança nascia `pendente` no provedor, sem cancelamento.

O teste anterior do A-11 rodava `pedir_pagamento` e `processar_chamadas` dentro da transação que segurava a trava. Isso fechava justamente a janela entre a solicitação e a criação, que existe na aplicação. O critério foi reescrito.

Além disso, o caso-limite "Suspensão e pagamento ao mesmo tempo" desta especificação dizia que a tentativa criada antes era cancelada pela suspensão. Na verdade, nesse momento ela ainda está `solicitada`. O texto correto está abaixo.

### Regras

- `cancelar_pedidos_nao_pagos` não muda. Ela continua sem travar pagamento e sem esperar chamada externa.
- A coordenação fica na operação `criar_cobranca`, na E08-03, seção "Correção E08-R02 e E08-R03":
  - o `executar` recusa com `pedido_cancelado`, sem chamar `criar_cobranca`;
  - o `concluir` trava a situação do pedido e, se ela estiver `cancelado`, agenda o cancelamento com o motivo da moderação (`suspensao` ou `remocao_da_conta`);
  - uma cobrança órfã, criada com a resposta perdida, é encontrada pela busca da recusa e cancelada.
- O pedido cancelado não é reaberto, e a reativação não o restaura (decisão técnica desta fatia, mantida).

### Caso-limite corrigido

**Suspensão e pagamento ao mesmo tempo.** `pedir_pagamento` e a moderação travam a situação do pedido.

| Quem trava primeiro | O que acontece |
|---|---|
| O pagamento | A tentativa nasce `solicitada`, e a suspensão cancela o pedido em seguida. Depois, a criação é recusada com `pedido_cancelado`, e nada nasce no provedor. Se a criação já estiver em andamento, o `concluir` agenda o cancelamento. |
| A suspensão | O pagamento recebe `pedido_cancelado` ou `conta_inativa`, e nenhuma tentativa nasce. |
