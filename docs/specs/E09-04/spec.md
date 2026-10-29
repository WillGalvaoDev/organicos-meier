# E09-04 — Entradas dos pagamentos e tarifas

Fatia 4 de 8 da milestone **E09 — Livro-razão, reserva e conciliação**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação: como na E09-01.

## Contexto e objetivo

A E08-04 decide, uma vez por pagamento aprovado, se ele quita o pedido ou gera devolução integral. Esta fatia leva essa decisão ao livro-razão:

- **Pagamento que quita:** entra na custódia da rodada, separado em produtos, serviço e frete do pedido congelado.
- **Pagamento em devolução ou sem pedido:** vira uma obrigação com o comprador, financiada pelo próprio pagamento, e nunca receita.
- **Tarifa do pagamento:** é registrada como despesa, e não muda nenhum valor de fornecedor ou de comprador.

Os pagamentos aprovados depois da margem ou em duplicidade abrem o alerta respectivo.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 3.2 | Pagamento aprovado e aceito: entrada na custódia da rodada, por componente. Aprovado depois de `T0 + 48h` ou em duplicidade: obrigação de devolução integral, financiada pelo próprio pagamento. Tarifa: despesa coberta pela receita de serviço. |
| Infraestrutura 3.1 | Custódia por rodada, ciclo e comprador, por componente. Obrigações com compradores. Despesas por tipo. |
| Infraestrutura 3.6 | Alertas de pagamento depois de `T0 + 48h` e de duplicidade. |
| Especificação §8.3 | Nunca ignorar dinheiro recebido. |
| Especificação §9.2 e §9.3 | Tarifas não são repassadas ao comprador. Recursos de fornecedor não pagam tarifa. |
| Cenários §16 | 30 (o registro da tarifa como despesa; a cobertura pela receita fica na E09-06) e 39 (a parte do livro-razão) |
| Herdado da E08 | `DestinoDoPagamento` `quita` é a fonte da entrada na custódia, com os componentes do `Pedido`; `devolucao` e `sem_pedido` viram obrigação com o comprador, nunca receita. |

## Escopo

**Dentro:**

- O sinal `destino_do_pagamento_decidido`.
- O receptor no app financeiro.
- Os modelos `ObrigacaoComComprador` e `Despesa`.
- As entradas F1 e F2 e a tarifa F4.
- A tarefa `registrar_tarifas_pendentes`.
- Os alertas `aprovado_apos_a_margem` e `duplicidade`.

**Fora:**

- A cobertura da tarifa pela receita (E09-06).
- A execução e a liquidação da devolução (E10).
- A apuração (E11).

## Decisões técnicas

- **Sinal emitido pela quitação.** `decidir_destino` (E08-04) emite `destino_do_pagamento_decidido(destino)` logo depois de gravar o destino, na mesma transação. Assim `apps.pedidos` não depende de `apps.financeiro`. O receptor roda com a trava do pagamento e da `SituacaoDoPedido` já obtidas. A ordem completa fica `PagamentoNoProvedor` → `SituacaoDoPedido` → contas do livro-razão.
- **Obrigação com comprador como registro só de inserção.** `ObrigacaoComComprador` tem:
  - a rodada, o ciclo, o pedido e o comprador, todos nulos no destino `sem_pedido`;
  - a origem (tipo e `pk`, como texto) e o motivo;
  - o valor devido por componente (`produtos`, `servico`, `frete`) e um componente `integral`, para o que não se separa, como o pagamento devolvido inteiro.

  O valor devido é a soma dos componentes, e o registro nunca muda. O financiado, o designado e o liquidado saem do livro-razão e das designações (E09-05), e não de campos alteráveis. Uma restrição `UNIQUE` na origem garante uma obrigação por destino.
- **Despesa como registro só de inserção.** `Despesa` tem o tipo (`tarifa` ou `deficit_frete`), o valor (> 0), a rodada (nula quando não houver), o pagamento ou o ciclo de origem e a criação. O coberto é a soma dos movimentos de cobertura daquela despesa. O pendente é o valor menos o coberto. Para a tarifa, a restrição `UNIQUE` no pagamento garante uma tarifa por pagamento.
- **Tarifa informada depois.** Se a sincronização preencher a tarifa depois da decisão do destino, porque o provedor a informou mais tarde, a tarefa periódica `registrar_tarifas_pendentes` (a cada 10 minutos) registra a despesa dos pagamentos que têm destino e tarifa, mas ainda não têm despesa. A chave idempotente impede o duplo registro.
- **Liberação pela origem.** A transferência de entrada guarda o pagamento como origem. A data de liberação é lida de `PagamentoNoProvedor.liberado_no_provedor_em` (E09-02), que pode chegar depois. Isso atende ao "cada entrada registra a data de liberação" sem alterar um lançamento imutável.

## Regras

**No destino `quita`,** um movimento `entrada_de_pagamento`, com a chave `entrada:<destino.pk>` e o autor `SISTEMA`. A justificativa é "Pagamento aprovado e aceito (P-6): entrada na custódia". São três transferências F1, de exterior para `custodia(rodada, ciclo, comprador, componente)`, com os valores `produtos`, `servico` e `frete` do `Pedido`. Um componente com valor zero não gera transferência. A soma é igual a `pagamento.valor`.

**No destino `devolucao`** (qualquer motivo da E08-04) **ou `sem_pedido`:**

1. Uma `ObrigacaoComComprador`, com `integral = pagamento.valor` e o motivo do destino.
2. Um movimento `entrada_para_devolucao`, com a chave `entrada:<destino.pk>` e F2 de exterior para `obrigacao_comprador(obrigacao)` com o valor inteiro. A justificativa é "Pagamento que não quita (§8.3): obrigação de devolução integral financiada pelo próprio pagamento".
3. Nos motivos `aprovado_apos_a_margem` e `duplicidade`, `abrir_alerta` do tipo respectivo, com a chave `id_externo` e os dados pagamento, pedido e valor.

**Tarifa:** quando o pagamento tem `tarifa > 0` e destino, e ainda não tem despesa:

1. Uma `Despesa(tipo="tarifa")` com a rodada do pedido, ou nula em `sem_pedido`.
2. Um movimento `tarifa`, com a chave `tarifa:<pagamento.pk>` e F4 de `despesas_a_cobrir` para exterior com o valor. A justificativa é "Tarifa do provedor (P-1): despesa operacional".

Isso acontece no receptor, quando a tarifa já veio, ou na tarefa. Tarifa zero ou nula não gera despesa.

**O que não acontece:** nenhuma entrada na custódia nem na receita para pagamento que não quita. Nenhuma transferência de custódia ou de obrigação de fornecedor para cobrir tarifa (lista de fluxos da E09-01). Nenhuma mudança em `Pedido`, `ItemDoPedido` ou nos valores cobrados.

## Interfaces

- O sinal `apps.pedidos.sinais.destino_do_pagamento_decidido` (argumento `destino`).
- `ObrigacaoComComprador` e `Despesa`.
- `registrar_entrada(destino)`, o mesmo serviço chamado pelo receptor, idempotente.
- `registrar_tarifa(pagamento)`, idempotente.
- `registrar_tarifas_pendentes_agora() -> int` e a tarefa periódica `registrar_tarifas_pendentes`.

## Invariantes

- Cada destino tem exatamente um movimento de entrada, e cada pagamento com tarifa tem exatamente uma despesa de tarifa.
- A soma da entrada é o valor do pagamento.
- Pagamento que não quita nunca chega à custódia, à receita nem à obrigação com fornecedor.
- A soma das custódias de um pedido quitado é exatamente o total dele.

## Casos-limite e concorrência

- **Aviso e reconsulta da margem decidindo o mesmo pagamento em paralelo:** o destino é um só (E08-04), e a entrada também, pela chave.
- **Dois pagamentos do mesmo pedido em paralelo:** um quita, com entrada na custódia, e o outro vira obrigação, em qualquer ordem (cenário 39).
- **A transação do destino é desfeita** (por exemplo, a falha local da E07): a entrada, a obrigação, a despesa e o alerta também.
- **A tarifa chega antes do destino** (a sincronização grava a tarifa, mas o pagamento não tem horário de aprovação): a despesa espera o destino. A tarefa só registra tarifa de pagamento que tem destino.
- **Uma exceção no receptor** desfaz a sincronização inteira (E07-03), e a recuperação da E07 repete.

## Dependências e decisões em aberto

Depende de E08-04, E09-01, E09-02 e E09-03. Nenhuma decisão em aberto.
