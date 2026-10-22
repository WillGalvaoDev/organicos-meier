# E09-01 — Livro-razão: destinações, movimentos e proibições

Fatia 1 de 8 da milestone **E09 — Livro-razão, reserva e conciliação**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Divisão da E09

| Fatia | Entrega | Depende de |
|---|---|---|
| E09-01 | Livro-razão: destinações, movimentos e proibições (P-2) | E08 |
| E09-02 | Provedor: tarifa, liberação, saldo e movimentos da conta | E07, E09-01 |
| E09-03 | Alertas financeiros | E04, E09-01 |
| E09-04 | Entradas dos pagamentos e tarifas | E08-04, E09-01 a E09-03 |
| E09-05 | Reserva e aportes | E09-01, E09-03 |
| E09-06 | Apuração no livro, despesas, frete e financiamento das obrigações | E09-04, E09-05 |
| E09-07 | Liquidez, invariante, saídas e conciliação diária | E09-02, E09-06 |
| E09-08 | Telas financeiras do administrador | E09-01 a E09-07 |

**Fronteira com as etapas seguintes.** A E09 entrega o livro-razão e as operações que as etapas seguintes vão chamar:

- a apuração (E11) chama o movimento de apuração da E09-06;
- as devoluções (E10, E11, E12 e E14) usam a obrigação com comprador e a liquidação da E09-06;
- o repasse e o pagamento do frete (E13) usam as saídas da E09-07.

As regras de quando essas operações acontecem continuam nas etapas donas delas. Por isso os cenários 31, 33 e 34 são provados aqui no nível do livro-razão, com as operações chamadas diretamente. Cada etapa seguinte repete o cenário pelo seu fluxo real.

## Contexto e objetivo

O provedor tem um saldo único, mas o dinheiro tem donos diferentes: o fornecedor, o comprador que vai receber de volta, o frete, a plataforma e a reserva. Esta fatia cria o livro-razão, que separa esses valores por destinação. Todo movimento fica registrado de forma imutável e explicada. O servidor recusa qualquer movimento que use recursos de um fornecedor fora do que a P-2 permite.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §9.3 | O livro-razão separa custódia, obrigações com fornecedores, receita de serviço, reserva, despesas, obrigações com compradores e frete. Recursos de um fornecedor são exclusivos dele, ressalvadas as devoluções devidas antes do repasse. Movimentação explícita, justificada, rastreável e auditável. A segregação vale com saldo único no provedor. |
| Especificação §14 | Livro-razão e destinações, com movimentações justificadas e auditáveis. |
| Infraestrutura 3.1 | Todo valor tem destinação. Todo movimento é um lançamento só de inserção, com autor, momento, justificativa e vínculo com a origem. Tabela de destinações e granularidade. |
| Infraestrutura 3.2 | Regras de movimentação e proibições (P-2). Lançamentos de regra fixa são do sistema e citam a regra. Os de escolha de origem exigem o administrador com nova autenticação. |
| Infraestrutura 5 | Dinheiro em decimal exato e registros auditáveis e imutáveis. |
| Cenários §16 | 32 |
| Testes técnicos | T-11, primeira metade (a recusa do lançamento entre fornecedores). A segunda metade, o repasse limitado à liquidez, fica na E09-07. |
| AGENTS.md §6 | Dinheiro: decimal exato, lançamentos imutáveis, idempotência e segregação por destinação. |

## Escopo

**Dentro:**

- O app `apps.financeiro`.
- As contas do livro-razão por destinação e chave.
- O movimento com as suas transferências, só de inserção e com trigger.
- O serviço `lancar`, com a lista fechada de fluxos permitidos, a recusa de saldo negativo e a idempotência.
- As consultas `saldo` e `extrato`.

**Fora:**

- Quem gera cada movimento: as fatias E09-04 a E09-07 e as etapas seguintes.
- Telas (E09-08).
- O saldo comprometido da reserva (E09-05).

## Decisões técnicas

- **Partidas como transferências.** Um movimento é um conjunto de transferências `(de, para, valor)`, com `valor > 0` e duas casas. `de` e `para` são contas do livro-razão ou o **exterior**, que é o dinheiro entrando na conta do provedor ou saindo dela. O saldo de uma conta é o que entrou nela menos o que saiu. O exterior não tem saldo.
  - Consequência: a soma dos saldos de todas as contas é o dinheiro que o livro-razão espera na conta do provedor. A E09-07 compara essa soma com o saldo real.
- **Contas por destinação.** A conta é identificada pela destinação e pela chave. Ela nasce no primeiro movimento, uma vez só (`UNIQUE` na destinação e na chave):

  | Destinação | Chave | Contém |
  |---|---|---|
  | `custodia` | rodada, ciclo, comprador, componente (`produtos`, `servico`, `frete`) | o que o comprador pagou antes da apuração |
  | `obrigacao_fornecedor` | fornecedor, rodada | produtos devidos ao fornecedor depois da apuração |
  | `frete` | rodada | frete arrecadado e coberturas de déficit, até o pagamento do frete |
  | `obrigacao_comprador` | obrigação (E09-04, E09-06) | o que já está financiado para uma devolução devida |
  | `receita_servico` | rodada | taxa de serviço dos pedidos válidos |
  | `reserva` | única | aportes menos utilizações |
  | `despesas_a_cobrir` | única | tarifas que o provedor já descontou e que ainda não foram cobertas |

- **O único saldo negativo** permitido é o de `despesas_a_cobrir`. A tarifa sai do saldo do provedor antes de ter uma fonte, e o saldo negativo mostra exatamente o que ainda falta cobrir. Qualquer movimento que deixe outra conta negativa é recusado inteiro.
- **Fluxos permitidos por lista fechada.** A P-2 fica garantida por uma lista do que é permitido, e não por uma lista do que é proibido. Um par (origem, destino) fora da lista é recusado com `MovimentoProibido`, mesmo que o código chamador esteja errado. A lista está em "Regras".
- **Ordem das travas.** O `lancar` trava as contas envolvidas em ordem crescente de `pk` e confere os saldos sob a trava. Ele roda dentro da transação de quem chama e vem depois das travas da E08: `PagamentoNoProvedor` → `SituacaoDoPedido` → `TentativaDePagamento` → contas do livro-razão.
- **Idempotência.** Todo movimento tem uma `chave` única, derivada da origem (por exemplo, `entrada:<destino>`). Repetir com a mesma chave e o mesmo conteúdo devolve o movimento existente, sem gravar nada. Com a mesma chave e conteúdo diferente, levanta `MovimentoConflitante`. Uma repetição nunca vira um segundo lançamento.
- **Autor e justificativa.**
  - No movimento do sistema, o autor é `SISTEMA`, e a justificativa é o código da regra mais um texto fixo (por exemplo, `P-1`).
  - No movimento do administrador, o autor é a conta, a justificativa é um texto não vazio digitado por ele, e uma `EntradaAuditoria` é gravada na mesma transação.

## Regras

**Fluxos permitidos.** Na tabela, `r` é a rodada da conta de origem. "Obrigação da rodada `r`" é uma `obrigacao_comprador` cuja obrigação pertence à rodada `r`.

| Nº | De | Para | Condição |
|---|---|---|---|
| F1 | exterior | `custodia(r, c, b, comp)` | tipo `entrada_de_pagamento` |
| F2 | exterior | `obrigacao_comprador(o)` | tipo `entrada_para_devolucao` |
| F3 | exterior | `reserva` | tipo `aporte` |
| F4 | `despesas_a_cobrir` | exterior | tipo `tarifa` |
| F5 | `custodia(r, c, b, produtos)` | `obrigacao_fornecedor(f, r)` | tipo `apuracao`; `f` é o fornecedor da rodada `r` |
| F6 | `custodia(r, c, b, servico)` | `receita_servico(r)` | tipo `apuracao` |
| F7 | `custodia(r, c, b, frete)` | `frete(r)` | tipo `apuracao` |
| F8 | `custodia(r, c, b, comp)` | `obrigacao_comprador(o)` | tipo `financiamento_de_obrigacao`; `o` é da rodada `r`, do ciclo `c` e do comprador `b` |
| F9 | `obrigacao_fornecedor(f, r)` | `obrigacao_comprador(o)` | tipo `financiamento_de_obrigacao`; `o` é da rodada `r` |
| F10 | `frete(r)` | `obrigacao_comprador(o)` | tipo `financiamento_de_obrigacao`; `o` é da rodada `r` |
| F11 | `receita_servico(qualquer)` ou `reserva` | `despesas_a_cobrir`, `frete(qualquer)` ou `obrigacao_comprador(qualquer)` | tipos `cobertura_de_despesa` ou `financiamento_de_obrigacao` |
| F12 | `obrigacao_fornecedor(f, r)` | exterior | tipo `repasse` |
| F13 | `receita_servico(r)` | exterior | tipo `retirada_de_receita` |
| F14 | `frete(r)` | exterior | tipo `pagamento_do_frete` |
| F15 | `obrigacao_comprador(o)` | exterior | tipo `devolucao` |

Qualquer outra combinação é recusada, inclusive:

- custódia ou obrigação de um fornecedor para destino de outra rodada ou de outro fornecedor;
- custódia ou obrigação de fornecedor para `despesas_a_cobrir`, `reserva` ou `receita_servico`;
- custódia de um comprador para a obrigação de outro comprador;
- um componente para outro, como produtos para receita.

**Recusas de `lancar`, sem nenhuma escrita:**

| Situação | Exceção e código |
|---|---|
| Fluxo fora da lista | `MovimentoProibido("fluxo_nao_permitido")`, com o número do primeiro par recusado e as destinações na mensagem, sem valores |
| Saldo final negativo em conta que não seja `despesas_a_cobrir` | `SaldoInsuficiente`, com a destinação e a chave |
| Valor zero, negativo, com mais de duas casas ou `float` | `MovimentoInvalido("valor")` |
| Movimento sem transferências, com `de == para`, ou com dois sentidos para o mesmo par | `MovimentoInvalido("transferencias")` |
| Autor administrador sem justificativa | `MovimentoInvalido("justificativa")` |
| Mesma chave com conteúdo diferente | `MovimentoConflitante` |
| Fora de transação | `TransactionManagementError` |

**Imutabilidade:** movimentos e transferências só aceitam inserção, pela base `RegistroSoInsercao` mais a trigger `instalar_protecao_so_insercao`. Uma correção é sempre um movimento novo que cita o anterior na justificativa.

## Interfaces

- `Destinacao` (`TextChoices`) e `Componente` (`produtos`, `servico`, `frete`).
- `conta(destinacao, **chave) -> ContaFinanceira`, que cria ou devolve a conta, e `EXTERIOR`, o marcador.
- `Transferencia(de, para, valor)`, uma *dataclass* congelada.
- `lancar(*, tipo, transferencias, autor, justificativa, origem, chave) -> MovimentoFinanceiro`. A `origem` é o objeto de origem: o tipo e a `pk` são gravados como texto, como na auditoria.
- `saldo(conta) -> Decimal`; `extrato(conta) -> list[...]`, em ordem de movimento; `saldo_total_esperado() -> Decimal`, a soma de todas as contas.
- As exceções `MovimentoProibido`, `SaldoInsuficiente`, `MovimentoInvalido` e `MovimentoConflitante`.

## Invariantes

- A soma das transferências que entram e saem de cada conta é o saldo dela. Nenhum saldo fica guardado à parte de forma que possa divergir das transferências.
- Nenhuma conta, exceto `despesas_a_cobrir`, termina um movimento com saldo negativo.
- Nenhum movimento grava pela metade: ou todas as transferências, ou nenhuma.
- Nenhum dinheiro de fornecedor sai por um fluxo fora de F5, F8, F9 e F12, nem é trocado entre fornecedores ou rodadas.
- Nenhum `float` no app, o que a varredura estática da E08-01 já cobre (`apps/`).

## Casos-limite e concorrência

- **Duas retiradas concorrentes da mesma conta,** cada uma menor que o saldo, mas juntas maiores: uma passa e a outra recebe `SaldoInsuficiente`, em qualquer ordem.
- **O mesmo movimento por duas transações** com a mesma chave: um registro só, e a outra devolve o existente.
- **Dois movimentos que travam as mesmas contas em ordens de chamada diferentes:** a trava ordenada por `pk` evita impasse.
- **Um movimento com várias transferências,** em que a última viola o saldo: nenhuma transferência é gravada.

## Dependências e decisões em aberto

- Depende de E08, pelos modelos `Rodada`, `Ciclo`, `Pedido` e `Fornecedor`. Nenhuma decisão em aberto.
- **Limite de verificação:** o comportamento do Mercado Pago não interfere nesta fatia.
