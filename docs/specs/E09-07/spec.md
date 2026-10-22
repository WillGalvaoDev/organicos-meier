# E09-07 — Liquidez, invariante, saídas e conciliação diária

Fatia 7 de 8 da milestone **E09 — Livro-razão, reserva e conciliação**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação: como na E09-01.

## Contexto e objetivo

O dinheiro no provedor não fica todo disponível ao mesmo tempo, e o saldo da conta é um só. Esta fatia:

- calcula a **liquidez** da obrigação com cada fornecedor e da receita de serviço, isto é, quanto dela vem de pagamentos já liberados;
- registra as **saídas** da conta (repasse, retirada de receita e pagamento do frete), limitando o repasse e a retirada à parte liberada;
- verifica o **invariante**: o saldo do provedor cobre o dinheiro de terceiros. Se não cobre, abre um alerta crítico e bloqueia os usos da reserva e as retiradas;
- faz a **conciliação diária**: compara os movimentos e o saldo do provedor com o livro-razão e alerta cada divergência e cada pagamento sem lançamento.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 3.4 | Liquidez por destinação, separando liberado de a liberar (L-10). Repasse limitado à parte liberada da obrigação com aquele fornecedor. Invariante: saldo do provedor ≥ custódia + obrigações com fornecedores + frete arrecadado não pago + obrigações com compradores. Violação gera alerta crítico e bloqueia novas utilizações da reserva e retiradas de receita. |
| Infraestrutura 3.5 | Conciliação diária com o saldo e os movimentos do provedor (L-9). Divergência gera alerta. Toda saída da conta do provedor é registrada no livro-razão. Devoluções excepcionais não são divergência (E10). |
| Infraestrutura 3.2 | Repasse manual: baixa da obrigação com aquele fornecedor. Retirada da receita de serviço pelo admin: baixa da receita. |
| Infraestrutura 3.6 | Alertas de violação do invariante, de pagamento sem conciliação e de divergência na conciliação diária. |
| Cenários §16 | 40 (no nível do livro-razão; o fluxo do repasse é da E13) |
| Testes técnicos | T-11, segunda metade (repasse a A limitado ao valor liberado de A) |

## Escopo

**Dentro:**

- `liquidez(conta)`, para `obrigacao_fornecedor` e `receita_servico`.
- `registrar_saida`.
- `verificar_invariante` e a tarefa a cada 10 minutos.
- `conciliar_dia` e a tarefa da conciliação diária.
- O registro `ConciliacaoDiaria`.
- A resolução automática dos alertas de conciliação.

**Fora:**

- A tela do repasse e o fluxo do pedido formal (E13).
- A tela da retirada e da conciliação (E09-08).
- Os movimentos de devolução no provedor (E10).

## Decisões técnicas

- **Liquidez por cadeia de componente.** A obrigação com o fornecedor `(f, r)` só recebe dinheiro da apuração (produtos dos pedidos válidos da rodada). A receita de serviço `r` também (serviço dos mesmos pedidos). Por isso:

  ```
  liberado(D) = max(0, min(saldo(D), E_lib(D) − S(D)))
  a_liberar(D) = saldo(D) − liberado(D)
  ```

  - `E_lib(D)` é a soma do que a apuração transferiu para `D` a partir de pedidos cujo pagamento que quitou tem `liberado_no_provedor_em ≤ agora`.
  - `S(D)` é a soma de tudo que já saiu de `D` por qualquer fluxo (repasses, retiradas, financiamentos de obrigação e coberturas).

  Sem `liberado_no_provedor_em`, o pagamento conta como a liberar (E09-02). As outras destinações não têm liquidez nesta etapa. O frete pode ganhá-la na E13, se o pagamento do frete precisar.
- **Saídas registradas pelo administrador.** O repasse, a retirada e o pagamento do frete são feitos fora do sistema, por Pix ou transferência a partir da conta do provedor (A3: repasse manual). Depois, o administrador registra a saída com a identificação do movimento no provedor. A chave é `saida:<identificacao>`, e a mesma saída nunca entra duas vezes. A conferência com o provedor é da conciliação. O registro não consulta o provedor (L-8).
- **Invariante pela soma das contas.**

  ```
  obrigacoes_de_terceiros = Σ saldo(custodia) + Σ saldo(obrigacao_fornecedor) + Σ saldo(frete) + Σ saldo(obrigacao_comprador)
  ```

  O saldo do provedor vem de `consultar_saldo()`, chamado fora de transação. A soma é lida numa única consulta, só com as transferências de movimentos até o `referente_a` desse saldo (E09-02). Assim um saldo de relatório, que no Mercado Pago não é em tempo real, é comparado com o livro-razão do mesmo instante. Com `liberado + a_liberar < obrigacoes_de_terceiros`, abre o alerta `invariante_violado` (`"geral"`), com a diferença. Quando volta a valer, ele é resolvido. Se o provedor não responde, um log `warning` é gravado, e o alerta fica como estava.
- **Cadência.**
  - O invariante roda a cada 10 minutos, como a reconsulta da margem.
  - A conciliação roda de hora em hora e concilia cada dia ainda não conciliado. O primeiro é o dia seguinte ao último conciliado, e o último é o dia anterior. Na primeira execução, só o dia anterior. Um dia só é conciliado depois que termina no horário de Brasília. Se o provedor falha, o dia fica para a próxima hora.
- **Conciliação de um dia `D`,** de 00:00 a 24:00 no horário de Brasília. Cada movimento do provedor no dia procura o seu par no livro-razão:

  | Movimento do provedor | Par esperado | Sem par ou com valor diferente |
  |---|---|---|
  | `pagamento` | o `PagamentoNoProvedor` aprovado com o `id_externo`, com destino e entrada (F1 ou F2) de igual valor | `pagamento_sem_conciliacao` (chave `id_externo`) e uma consulta agendada (`agendar_chamada("consultar_pagamento", id_externo)`); valor diferente: `divergencia_na_conciliacao` |
  | `tarifa` | a `Despesa(tarifa)` do pagamento, com o mesmo valor (em módulo) | `divergencia_na_conciliacao` (chave `id_movimento`) |
  | `deposito` | o aporte com a identificação igual ao `id_movimento` e o mesmo valor | `divergencia_na_conciliacao` |
  | `saida` | a saída registrada com a identificação igual ao `id_movimento` e o mesmo valor (em módulo) | `divergencia_na_conciliacao` |
  | `ajuste`, `outro` ou tipo desconhecido | não há | `divergencia_na_conciliacao`, com o `descricao_no_provedor` nos dados |

  No sentido inverso: cada aporte ou saída registrado no livro-razão com momento no dia `D` precisa de um movimento do provedor com a mesma identificação, entre `D − 3 dias` e o fim de `D`. Sem ele, abre `divergencia_na_conciliacao`, com a chave `livro:<identificacao>`.
- **Diferença de saldo.** Na execução:

  ```
  diferenca = saldo do provedor − saldo_total_esperado(até referente_a) − Σ(movimentos do provedor sem par, de D até referente_a) + Σ(aportes e saídas do livro sem par)
  ```

  Diferente de zero abre `divergencia_na_conciliacao` com a chave `saldo:<D>`, porque é uma diferença que nenhum movimento explica. Uma conciliação posterior com diferença zero resolve as chaves `saldo:*` abertas.
- **Resolução automática:**
  - `registrar_entrada` (E09-04) resolve `pagamento_sem_conciliacao` do pagamento;
  - `registrar_aporte` e `registrar_saida` resolvem `divergencia_na_conciliacao` com a chave do `id_movimento` igual à identificação;
  - `registrar_tarifa` resolve a do movimento de tarifa daquele pagamento.

## Regras

**`registrar_saida(autor, *, tipo, conta, valor, identificacao, justificativa)`**

O autor é o administrador, com nova autenticação por passkey na rota.

| Tipo | Conta | Limite | Bloqueada com invariante violado |
|---|---|---|---|
| `repasse` | `obrigacao_fornecedor(f, r)` | `liberado(conta)` | não |
| `retirada_de_receita` | `receita_servico(r)` | `liberado(conta)` | sim |
| `pagamento_do_frete` | `frete(r)` | `saldo(conta)` | não |

As recusas, sem escrita, são:

- valor acima do limite: `LiquidezInsuficiente`, com o liberado e o a liberar na mensagem;
- conta de outro tipo: `MovimentoProibido`, pela lista da E09-01;
- identificação repetida: `SaidaRepetida`;
- invariante violado, no tipo bloqueado: `InvarianteViolado`;
- justificativa vazia.

O efeito é um movimento F12, F13 ou F14 com a auditoria.

**`verificar_invariante_agora() -> ResultadoDoInvariante | None`** devolve o saldo do provedor, as obrigações de terceiros e a diferença. Com o provedor indisponível, devolve `None`. A tarefa periódica é `verificar_invariante`.

**`conciliar_dia(data) -> ConciliacaoDiaria`**

- `ConciliacaoDiaria` é um registro só de inserção, único por data. Ele guarda a data, `executada_em`, o resultado (`ok` ou `divergente`) e um resumo: quantos movimentos, quantos sem par e a diferença.
- Conciliar uma data já conciliada devolve o registro existente, sem consultar o provedor.
- Um dia que ainda não terminou é recusado com `ValueError`.
- Com o provedor indisponível, levanta `ConsultaAoProvedorFalhou` e não grava nada.
- A tarefa periódica é `conciliar_dias_pendentes`.

## Interfaces

- `liquidez(conta) -> Liquidez(liberado, a_liberar)`.
- `registrar_saida`.
- `verificar_invariante_agora` e a tarefa `verificar_invariante`.
- `conciliar_dia`, `conciliar_dias_pendentes_agora` e a tarefa `conciliar_dias_pendentes`.
- `ConciliacaoDiaria`.
- As exceções `LiquidezInsuficiente` e `SaidaRepetida`.

## Invariantes

- Nenhum repasse passa da parte liberada da obrigação com aquele fornecedor, então dinheiro liberado de B nunca paga A (T-11).
- Nenhuma retirada passa da parte liberada da receita, nem acontece com o invariante violado.
- Cada dia é conciliado uma única vez, e o registro é imutável.
- A conciliação nunca altera o livro-razão. Só abre e resolve alertas e agenda consultas.

## Casos-limite e concorrência

- **Repasse de A** com B totalmente liberado e A ainda a liberar: recusado, mesmo com o saldo do provedor suficiente.
- **Liberação parcial:** dois pedidos válidos de A, um liberado e um não. O liberado é só a parte do primeiro, menos o que já saiu.
- **Dois repasses concorrentes** que juntos passam do liberado: um passa e o outro é recusado, pela trava da conta e pelo cálculo sob a trava.
- **Pagamento aprovado no provedor e ainda não sincronizado na hora da conciliação:** abre `pagamento_sem_conciliacao` e agenda a consulta. A entrada, quando vier, resolve o alerta.
- **Duas execuções da conciliação do mesmo dia em paralelo:** um registro só, e a outra devolve o existente.

## Dependências e decisões em aberto

- Depende de E09-02 e E09-06.
- **L-8, L-9 e L-10 continuam abertas:** na fase 2a, se a API não der os movimentos ou o saldo, a conciliação desse ponto vira conferência manual.
- A E10 acrescenta o par dos movimentos `devolucao` e exclui as devoluções excepcionais da conciliação.

## Correções da revisão da E09 (2026-10-22)

Origem: parecer sobre `34f9547` (`docs/specs/E09-08/review.md`), achados R05, R06 e R07. Valem a correção E09-R08 e a "Regra única de travas" (E09-01, `spec.md`).

### Correção E09-R05 — a tarefa do invariante avalia a reserva

**Diagnóstico.** A E09-05 manda rodar `avaliar_reserva` também na tarefa do invariante, mas `verificar_invariante_agora` não a chama. Algumas despesas nascem sem nenhuma operação da reserva depois delas: por exemplo, a tarifa registrada pela sincronização ou pela tarefa `registrar_tarifas_pendentes`. Nesses casos, o alerta `reserva_insuficiente` não abre. Pelo mesmo motivo, também não se resolve quando a cobertura automática acontece fora das operações da reserva.

**Regras.**
- `verificar_invariante_agora`, depois do passo do invariante, avalia a reserva numa transação própria. Ela trava a conta `reserva` (regra única) e chama `avaliar_reserva()`.
- A avaliação da reserva acontece também com o provedor indisponível, porque usa só o livro-razão. Com o provedor indisponível:
  - a função continua devolvendo `None`;
  - grava o log `warning`;
  - deixa os alertas do invariante como estavam (A-10).
- O valor devolvido e o tratamento do invariante não mudam. Uma falha na avaliação da reserva não desfaz o passo do invariante, e vice-versa.

### Correção E09-R06 — identificação de 64 caracteres na conciliação

**Diagnóstico.** Para uma identificação de aporte ou de saída com 64 caracteres, que é válida, a chave `livro:<identificacao>` tem 70 caracteres. A chave do alerta aceitava até 64, então `abrir_alerta` levantava `ValueError`. O dia era desfeito, e a tarefa ficava parada nesse dia.

**Regra.** O limite da chave do alerta passa a 80 caracteres (E09-03, "Correção E09-R06"). A conciliação continua usando `livro:<identificacao>` com a identificação inteira, sem truncar nem resumir. A identificação também fica nos dados do alerta.

### Correção E09-R07 — três recortes separados na conciliação

**Diagnóstico.** A conciliação usa a mesma lista ampla de movimentos do provedor para três coisas:
- os movimentos do dia;
- o par inverso;
- a diferença de saldo.

Na diferença, entravam movimentos posteriores ao `referente_a`. No par inverso, entravam movimentos posteriores ao fim do dia. O resultado era uma diferença falsa (prova `test_conciliacao_respeita_referente_a`) e um `ok` falso (prova `test_conciliacao_nao_parea_movimento_futuro`). O par de um pagamento também era procurado sem olhar o instante, o que dá uma diferença falsa quando a entrada é lançada depois do `referente_a`.

**Regras (substituem a fórmula da diferença e detalham o par inverso acima).** A consulta ao provedor não muda: `listar_movimentos(início de D − 3 dias, max(fim de D, referente_a + 1 µs))`. Sobre essa lista, os três recortes são separados. `t` é o `referente_a` do saldo.

| Recorte | Movimentos do provedor | Movimentos do livro-razão | Uso |
|---|---|---|---|
| **Movimentos do dia** | `ocorrido_em` em [início de D, fim de D) | — | classificação pela tabela acima, alertas desses movimentos e a contagem `movimentos` do resumo |
| **Par inverso** | `ocorrido_em` em [início de D − 3 dias, fim de D) | aportes e saídas com `momento` em [início de D, fim de D) | o aporte ou a saída sem movimento do provedor de mesma identificação nesse intervalo abre `livro:<identificacao>` e conta em `sem_par` |
| **Diferença no instante `t`** | `ocorrido_em` em [início de D, `t`] | aportes e saídas com `momento` em [início de D, `t`] | a fórmula abaixo |

```
diferenca = saldo do provedor
          − saldo_total_esperado(até t)
          − Σ(movimentos do provedor do recorte da diferença sem par no livro até t)
          + Σ(aportes e saídas do recorte da diferença sem movimento do provedor de mesma
              identificação com ocorrido_em em [início de D − 3 dias, t])
```

- **"Sem par no livro até `t`."** O par usa a mesma tabela da classificação, mas só vale um lançamento do livro-razão com `momento ≤ t`:
  - a entrada do pagamento;
  - o movimento da tarifa;
  - o aporte;
  - a saída.

  `ajuste`, `outro` e os tipos desconhecidos nunca têm par.
- **`t` antes do início de D.** As duas somas ficam vazias, e a diferença compara o saldo com o livro-razão até `t`.
- **O resumo e o resultado.** `sem_par` continua sendo a soma dos sem par do dia: sem lançamento, divergentes e do livro. O resultado é `ok` só com `sem_par = 0` e diferença zero. O registro continua imutável e único por dia.
