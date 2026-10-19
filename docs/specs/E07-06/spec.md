# E07-06 — Consulta ao provedor antes de decisões irreversíveis

Fatia 6 de 6 da milestone **E07 — Simulador de pagamentos e integração**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Algumas decisões não têm volta: a apuração final, o envio do pedido formal, uma devolução, um repasse. Antes delas, o sistema não pode confiar só no que já registrou, porque um aviso pode ter se perdido ou atrasado. A regra é consultar o provedor na hora e, se a consulta falhar, bloquear a ação (infraestrutura 4.2).

Esta fatia entrega o serviço único que essas decisões chamam:

- busca no provedor os pagamentos de uma referência, inclusive os que o sistema não conhecia;
- reconsulta os já registrados, porque a busca pode atrasar (L-6);
- sincroniza tudo (E07-03);
- levanta um erro próprio quando o provedor não responde. Quem chamou não decide.

As decisões em si chegam nas etapas seguintes, cada uma chamando este serviço.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §8.3 | Uma aprovação feita até `T0 + 48h` e notificada depois "é aceita, desde que identificada na apuração". Nunca ignorar dinheiro recebido. |
| Especificação §15 | Conciliação recuperável. Não presumir comportamento do provedor. |
| Infraestrutura 4.2 | "Consulta obrigatória antes de decisões irreversíveis: apuração final, aprovação do resultado da cobrança, envio do pedido formal, autorização ou nova tentativa de devolução, confirmação de devolução excepcional, registro de repasse, cancelamento da rodada com reembolso. Se a consulta falhar, a ação fica bloqueada." |
| Infraestrutura 4.3 e 4.4 | A apuração reconsulta todas as tentativas e busca por `external_reference`. Risco residual do atraso de consistência (L-6). |
| E07-01, E07-03 | `buscar_por_referencia`, `consultar_pagamento`, `sincronizar_pagamento`. |

## Escopo

**Dentro:**

- O serviço `consultar_antes_de_decidir`.
- O erro `ConsultaAoProvedorFalhou`.
- A lista das decisões que devem usar o serviço, com a etapa de cada uma.

**Fora:**

- As decisões em si (E08, E10, E11, E12 e E13).
- O bloqueio na tela e as mensagens ao administrador. Cada etapa define as suas, sobre o erro desta fatia.

## Decisões técnicas

- **Consulta síncrona, antes da transação da decisão.** O serviço fala com o provedor na hora, e não pela tabela de chamadas (E07-04), porque a decisão precisa da resposta para seguir. Cada pagamento é sincronizado numa transação curta própria. Depois, a decisão abre a sua transação, trava o que precisa e relê os registros, que já trazem a consulta. Quem chama não deve segurar travas durante a consulta, para não esperar o provedor com linhas travadas.
- **Tudo ou bloqueio.** Se a busca ou qualquer reconsulta falhar, o serviço levanta `ConsultaAoProvedorFalhou`. As sincronizações já feitas continuam gravadas, porque são fatos verdadeiros do provedor, mas a decisão não segue com um retrato incompleto.
- **`PagamentoNaoEncontrado` na reconsulta** de um pagamento já registrado também bloqueia. Um pagamento que o sistema registrou e o provedor não encontra é uma anomalia, e uma decisão irreversível não pode seguir com ela.
- **Origem `busca` e `decisao`.** As respostas da busca entram no histórico com origem `busca`, e as reconsultas com origem `decisao` (E07-03).

## Regras

**Serviço** (`apps/pagamentos/consulta.py`):

```
consultar_antes_de_decidir(referencia_externa: str) -> list[PagamentoNoProvedor]
```

1. `encontrados = obter_provedor().buscar_por_referencia(referencia_externa)`.
2. Cada resultado é sincronizado com `origem="busca"`, numa transação própria (`transaction.atomic()`, que vira savepoint se houver transação aberta).
3. Cada `PagamentoNoProvedor` já registrado com essa referência (e o mesmo provedor) que não veio na busca é reconsultado com `consultar_pagamento` e sincronizado com `origem="decisao"`.
4. Devolve os registros da referência, relidos do banco, em ordem de `criado_no_provedor_em` e `id_externo`.

**Falhas:**

- `ProvedorIndisponivel`, `RecusaDoProvedor` ou `PagamentoNaoEncontrado`, na busca ou numa reconsulta, levantam `ConsultaAoProvedorFalhou(referencia_externa, motivo)`, com `motivo` igual a `indisponivel`, `recusa` ou `nao_encontrado`. A exceção original fica encadeada (`raise ... from`).
- A mensagem não traz dados pessoais nem valores.
- O log registra `"Consulta antes de decidir: <referencia_externa> <motivo>"`.

**Decisões que chamam o serviço** (infraestrutura 4.2), para cada referência envolvida e antes de abrir a transação da decisão:

| Decisão | Etapa |
|---|---|
| aprovação do resultado da cobrança | E08 |
| autorização ou nova tentativa de devolução; confirmação de devolução excepcional | E10 |
| apuração final | E11 |
| cancelamento da rodada com reembolso | E12 |
| envio do pedido formal; registro de repasse | E13 |

Cada uma dessas etapas especifica como mostra o bloqueio ao administrador e testa que nada é decidido quando o serviço levanta `ConsultaAoProvedorFalhou`.

## Interfaces

- `apps/pagamentos/consulta.py`: `consultar_antes_de_decidir` e `ConsultaAoProvedorFalhou`.

## Invariantes

- Quando o serviço devolve, todo pagamento da referência conhecido pelo provedor ou pelo sistema foi consultado nesta chamada.
- Quando o provedor falha, o serviço nunca devolve uma lista.

## Casos-limite e concorrência

- **Aviso perdido:** o pagamento aprovado nunca foi avisado. A busca o encontra, e ele é registrado `aprovado`, com auditoria e sinal.
- **Busca atrasada** (L-6): a busca não traz um pagamento já registrado. A reconsulta direta o atualiza.
- **Dois pagamentos aprovados para a mesma referência:** os dois são registrados e devolvidos. Escolher qual quita o pedido é da E08 (§8.3).
- **Provedor fora do ar:** `ConsultaAoProvedorFalhou` com `indisponivel`, e nada é devolvido.
- **Aviso processado ao mesmo tempo** que a consulta: as duas sincronizações ficam em fila pela trava da linha (E07-03), e a mudança é reconhecida uma vez.
- **Referência sem nenhum pagamento:** devolve lista vazia, sem erro.

## Dependências e decisões em aberto

- Depende de E07-01 e E07-03.
- Sem decisões em aberto.
