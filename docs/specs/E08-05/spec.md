# E08-05 — Prazo de pagamento, bloqueio, margem e acompanhamento

Fatia 5 de 7 da milestone **E08 — Cobrança: abertura, congelamento e prazos**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

A linha do tempo da cobrança tem três marcos fixos, contados a partir de `T0`:

| Marco | O que acontece |
|---|---|
| `T0 + 24h` | Fim do prazo de pagamento. Novas tentativas são recusadas, e as cobranças pendentes são canceladas no provedor. |
| `T0 + 24h` a `T0 + 48h` | Margem. Só se confirmam e se conciliam os pagamentos já iniciados. |
| a partir de `T0 + 48h` | A apuração pode começar, mas só com a autorização do administrador (E11). |

Nenhum desses prazos é prorrogável. Esta fatia entrega:

- as funções da linha do tempo;
- a tarefa de bloqueio;
- a tarefa de reconsulta da margem;
- a verificação de que a apuração pode começar, para a E11 usar;
- a situação de cada pedido na página do administrador.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §7 | Pagamento: prazo de exatamente 24h, improrrogável, inclusive pelo administrador. Margem de `T0 + 24h` a `T0 + 48h`: não reabre compras, não altera pedidos, não autoriza cobranças e não é prorrogável. Apuração a partir de `T0 + 48h`, só com autorização, nunca antecipada. O encerramento automático dos prazos não autoriza nenhuma etapa. |
| Especificação §8.2 | Em `T0 + 24h`, bloquear novas tentativas. Na margem, confirmar e conciliar. Pedidos não pagos não são cancelados na margem. |
| Infraestrutura 4.3 | Bloqueio ativo em `T0 + 24h`: a tarefa cancela as tentativas pendentes [Validar L-2]. Durante a margem, uma tarefa reconsulta as tentativas e busca por `external_reference` [Validar L-6]. O painel mostra a situação de cada pedido. Apuração recusada antes de `T0 + 48h`. Fronteiras em milissegundos: `T0 + 24h` exato já é bloqueado. |
| Infraestrutura 4.2 | Bloqueio por prazo, webhook, conciliação e autorização atualizam o pedido sob trava, reconsultando o estado. A ordem dos eventos não altera o resultado. |
| Cenários §16 | 12, 27 (parte da verificação), 28. |
| Testes técnicos | T-4 (parte da verificação), T-5, T-7. |
| Herdado da E06 | Os prazos de pagamento e de margem são improrrogáveis, e `prorrogar_fechamento` só atende `fechamento`. |

## Escopo

**Dentro:**

- As funções de `apps/pedidos/prazos.py`.
- As tarefas `bloquear_tentativas_vencidas` e `reconsultar_pagamentos_da_margem`.
- `pode_iniciar_apuracao`.
- A situação dos pedidos no bloco da página de estoque.
- As provas de que nenhum prazo é prorrogável.

**Fora:**

- A apuração e a autorização dela (E11).
- O alerta de tarefa atrasada ou de cancelamento que falhou (E15).

## Decisões técnicas

- **Prazos derivados de `T0`, nunca gravados à parte.** `prazo_de_pagamento = somar_horas(T0, 24)` e `fim_da_margem = somar_horas(T0, 48)`. Como `AberturaDoPagamento` só aceita inserção e não há rota que mude `T0`, nenhum prazo pode ser alterado.
- **Não há etapas novas.** A rodada fica em `pagamento` do `T0` até a apuração. Margem e "apta para apuração" são situações de tempo (§7: "bloqueios por prazo"), calculadas pelas funções.
- **Bloqueio em duas camadas.**
  - A recusa no servidor (E08-03) vale sozinha, mesmo com a tarefa parada.
  - A tarefa só cancela no provedor as cobranças pendentes.
  - O cancelamento de cada tentativa é agendado uma única vez. Se a chamada falhar definitivamente, ela não é reagendada: fica `falhou` na tabela e no log, para o alerta da E15. A cobrança também vence sozinha no provedor em `T0 + 24h` (`expira_em`).
- **Reconsulta da margem a cada 10 minutos.** A especificação não fixa a frequência. Dez minutos mantêm o painel atualizado sem sobrecarregar o provedor. Cada reconsulta usa `consultar_antes_de_decidir` (E07-06), que busca pela referência e reconsulta os pagamentos conhecidos.
  - Os pedidos reconsultados são os `aguardando_pagamento` e os `cancelado`, porque um pedido cancelado ainda pode receber dinheiro, que nunca é ignorado.
  - A mesma passada decide o destino dos pagamentos aprovados que ainda não têm destino (E08-04, aprovação sem horário ou falha anterior).
- **Ordem dos eventos.** O bloqueio só agenda cancelamentos, e o resultado de um cancelamento passa pela sincronização e pela decisão da E08-04. Por isso, um aviso e o bloqueio chegam ao mesmo resultado em qualquer ordem: vale o que o provedor registrou.

## Regras

### Linha do tempo (`apps/pedidos/prazos.py`)

```
prazo_de_pagamento(abertura) -> datetime        # T0 + 24h
fim_da_margem(abertura) -> datetime             # T0 + 48h
aceita_tentativas(abertura, instante) -> bool   # not prazo_encerrado(instante, T0 + 24h)
em_margem(abertura, instante) -> bool           # T0 + 24h ≤ instante ≤ T0 + 48h
pode_iniciar_apuracao(abertura, instante) -> bool   # prazo_encerrado(instante, T0 + 48h)
```

- `pedir_pagamento` (E08-03) e `decidir_destino` (E08-04) passam a usar estas funções.
- `pode_iniciar_apuracao` responde só ao tempo. A autorização do administrador e a ação de apurar são da E11, que deve recusá-la no servidor quando a função devolver falso.

### Tarefa de bloqueio (`apps/pedidos/tarefas.py`)

`bloquear_tentativas_vencidas`, periódica a cada minuto, com `queueing_lock` igual ao nome. A função testável é `bloquear_tentativas_vencidas_agora() -> int`.

1. Seleciona as aberturas cuja rodada está em `pagamento` e cujo `prazo_de_pagamento` já passou.
2. Para cada uma, numa transação própria, olha cada tentativa `criada` cujo pagamento não é terminal e que ainda não tem chamada `cancelar_cobranca` com o alvo `t<tentativa>:prazo`, em qualquer situação. Para essas, chama `agendar_cancelamento(tentativa, "prazo")`.
3. Uma falha numa abertura vai para o log, com o id e o tipo da exceção, e não impede as outras.
4. Devolve quantos cancelamentos agendou.

Tentativas `solicitada` não precisam de nada: o `executar` da criação recusa depois do prazo (E08-03).

### Tarefa da margem

`reconsultar_pagamentos_da_margem`, periódica a cada 10 minutos (`*/10 * * * *`), com `queueing_lock` igual ao nome. A função testável é `reconsultar_pagamentos_da_margem_agora() -> int`.

1. Seleciona as aberturas cuja rodada está em `pagamento` e que estão `em_margem(abertura, agora())`.
2. Para cada pedido `aguardando_pagamento` ou `cancelado` dessas aberturas:
   - chama `consultar_antes_de_decidir(pedido.referencia_externa)` fora de qualquer transação;
   - com `ConsultaAoProvedorFalhou`, grava um log `warning` com o pedido e o motivo, e segue para o próximo.
3. Depois, para cada `PagamentoNoProvedor` `aprovado` com a referência desses pedidos e sem destino:
   - numa transação, trava o pagamento e chama `decidir_destino`.
4. Devolve quantos pedidos foram reconsultados com sucesso.

### Situação dos pedidos para o administrador

O bloco "Fechamento" da página de estoque, em `pagamento` (E08-02), ganha:

- **Linha do tempo:** "Prazo de pagamento até <data e hora>. Margem até <data e hora>. A apuração só pode começar depois disso, com a sua autorização.", no fuso da operação.
- **Tabela dos pedidos**, com comprador (nome de exibição), total e situação:

  | Situação | Condição |
  |---|---|
  | Pago no prazo | `pago`, com `quitado_em` antes do prazo de pagamento |
  | Pago na margem | `pago`, com `quitado_em` a partir do prazo de pagamento |
  | Cancelado (suspensão) ou Cancelado (remoção da conta) | `cancelado`, com o motivo |
  | Sem resposta do provedor | `aguardando_pagamento`, e a última chamada de criação, cancelamento ou consulta do pedido está `pendente` com `ultimo_erro` preenchido |
  | Pagamento pendente | `aguardando_pagamento`, com tentativa aberta |
  | Não pago | `aguardando_pagamento`, nos outros casos |

- **Devoluções devidas:** a lista dos destinos `devolucao` e `sem_pedido` dos pagamentos com a referência dos pedidos da abertura, com o `id_externo`, o valor e o motivo por extenso. Os motivos por extenso são:
  - "aprovado depois da margem";
  - "iniciado fora do prazo";
  - "pagamento em duplicidade";
  - "pedido cancelado";
  - "valor diferente do pedido";
  - "referência desconhecida".

  Lista vazia: "Nenhuma devolução devida."

A página não tem nenhum campo, botão ou rota para alterar `T0`, os prazos, os pedidos ou os pagamentos. A página continua `somente_administrador`.

## Interfaces

- `apps/pedidos/prazos.py`: as cinco funções.
- `apps/pedidos/tarefas.py`: as duas tarefas e as funções testáveis.
- `apps/pedidos/acompanhamento.py`: `situacao_dos_pedidos(abertura) -> list[LinhaDoPedido]` e `devolucoes_devidas(abertura)`, usadas pela página.
- `apps/rodadas/views.py` e o template: o bloco.

## Invariantes

- Nenhuma tentativa nova a partir de `T0 + 24h`, com ou sem as tarefas.
- Nenhum pedido é cancelado por falta de pagamento nesta etapa: isso é da apuração (E11).
- A rodada não muda de etapa sozinha a partir de `T0 + 24h` nem de `T0 + 48h`.
- Nenhuma tela, rota ou serviço altera `T0` ou os prazos.

## Casos-limite e concorrência

- **Tarefa de bloqueio atrasada:** as tentativas continuam recusadas no servidor. Quando a tarefa roda, cancela o que estiver pendente.
- **Pagamento concluído no instante do cancelamento:** vale o que o provedor registrou (E08-03 A-11, E08-04).
- **Provedor fora do ar na margem:** a reconsulta registra o motivo no log, e o painel mostra "Sem resposta do provedor" quando houver chamada pendente com erro.
- **Aviso, bloqueio e reconsulta ao mesmo tempo:** a trava do pagamento e a da situação do pedido põem as decisões em fila. Há um destino só, e o resultado depende só dos horários do provedor.

## Dependências e decisões em aberto

- Depende de E06-04, E07-04, E07-06 e E08-02 a E08-04.
- Sem decisões em aberto.
