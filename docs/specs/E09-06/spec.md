# E09-06 — Apuração no livro, despesas, frete e financiamento das obrigações

Fatia 6 de 8 da milestone **E09 — Livro-razão, reserva e conciliação**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação: como na E09-01.

## Contexto e objetivo

Esta fatia entrega as operações do livro-razão que as etapas seguintes vão chamar:

- **Apuração no livro:** depois da apuração final (E11), a custódia dos pedidos válidos vai para as obrigações com o fornecedor, a receita de serviço e o frete. O frete efetivo e o déficit são registrados separadamente, e as tarifas pendentes da rodada são cobertas pela receita de serviço dela (P-1).
- **Obrigação com comprador:** cada devolução devida (E10, E11, E12 e E14) vira uma obrigação, financiada pela regra. Antes do repasse, saem os recursos da própria rodada. O que faltar depois do repasse fica sem cobertura, até o administrador escolher a fonte.
- **Coberturas pelo administrador:** de despesas e de obrigações, a partir da receita de serviço ou da reserva.
- **Liquidação:** a baixa da obrigação quando a devolução é feita, uma única vez.

A E09 não decide quando a apuração ou uma devolução acontece: isso continua nas etapas donas delas. Os cenários 30, 31 e 33 são provados aqui no nível do livro-razão.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 3.1 | Frete arrecadado, frete efetivo e déficit, registrados separadamente. Frete efetivo só existe quando a compra ao fornecedor é realizada e corresponde ao `F` da abertura. Déficit = frete efetivo − frete arrecadado líquido de devoluções, e inclui inadimplentes e devoluções proporcionais de frete. |
| Infraestrutura 3.2 | Apuração aprovada: custódia → obrigações com fornecedores, frete arrecadado e receita de serviço. Devolução antes do repasse: financiada pela custódia ou pela obrigação da mesma rodada. Depois do repasse: receita de serviço, reserva ou novo aporte. Déficit: receita, reserva ou novo aporte. Tarifa sem receita suficiente: pendente, e o admin escolhe a origem. |
| Especificação §9.3 | Tarifas cobertas pela receita da taxa de serviço; déficit de frete é do administrador; sem cobrança retroativa. |
| Cenários §16 | 30, 31 e 33 (nível do livro-razão) |
| Decisões | P-1, P-2, P-3 |

## Escopo

**Dentro:**

- `registrar_apuracao_no_livro`.
- `frete_do_ciclo`, o relatório de efetivo, arrecadado, devolvido, déficit e coberto.
- `registrar_obrigacao_com_comprador`, com o financiamento automático.
- `cobrir_obrigacao_com_receita` e `cobrir_despesa`.
- `liquidar_obrigacao`.
- A cobertura automática das tarifas pela receita da rodada.

**Fora:**

- Quando a apuração ocorre e quais pedidos são válidos (E11).
- O cálculo dos componentes de cada devolução e o acumulado por item (E10, Q-7).
- A execução da devolução no provedor (E10).
- O repasse e o pagamento do frete (E09-07 e E13).

## Decisões técnicas

- **Cobertura automática das tarifas.** "Tarifa coberta pela receita de serviço" é uma regra de origem fixa (P-1), então o sistema lança sozinho. A fonte é a receita de serviço da rodada do pagamento, que só existe depois da apuração.
  - A tentativa acontece na apuração (para as tarifas pendentes da rodada) e no registro de cada tarifa nova de uma rodada já apurada (E09-04, `registrar_tarifa`).
  - A cobertura é inteira ou nada, por tarifa, na ordem de criação. Se a receita da rodada não cobre a tarifa inteira, ela fica pendente para o administrador. Esse é o caso da infraestrutura em que a receita é insuficiente, por exemplo quando a rodada volta para interesse e devolve o serviço. Tarifa sem rodada (`sem_pedido`) fica sempre para o administrador.
- **Fontes da regra por componente.** A obrigação com comprador é financiada pelo sistema, na criação, componente por componente, até onde houver saldo:

  | Componente | Antes da apuração do ciclo | Depois da apuração do ciclo |
  |---|---|---|
  | produtos | `custodia(r, c, b, produtos)`, F8 | `obrigacao_fornecedor(f, r)`, F9 |
  | serviço | `custodia(r, c, b, servico)`, F8 | `receita_servico(r)`, F11 |
  | frete | `custodia(r, c, b, frete)`, F8 | `frete(r)`, F10, mais uma despesa de déficit do mesmo valor |

  O "depois do repasse" da infraestrutura aparece como falta de saldo: o repasse consumiu a obrigação com o fornecedor. O que não couber fica **sem cobertura**. A obrigação continua com o devido integral, e `avaliar_reserva` roda (E09-05).
- **Frete devolvido depois da apuração.** Devolver frete a partir de `frete(r)` reduz o frete arrecadado líquido. Por isso nasce uma `Despesa(tipo="deficit_frete")` com o mesmo valor, pendente, que o administrador cobre de volta em `frete(r)`. Se o frete já foi pago (sem saldo em `frete(r)`), o componente fica sem cobertura na própria obrigação, e o relatório conta o frete devolvido do mesmo jeito.
- **Apuração idempotente.** Uma apuração por ciclo, com a chave `apuracao:<ciclo>`. Repetir com o mesmo conjunto de pedidos devolve a existente. Com um conjunto diferente, levanta `MovimentoConflitante`.
- **Liquidação.** Primeiro usa o saldo financiado na conta da obrigação e depois as designações ativas, na ordem de criação. O consumo de uma designação é um movimento F11 da `reserva` para a obrigação, que cita a designação, e pode ser parcial. Depois vem a saída F15. A chave é `devolucao:<referencia>`, dada por quem executou a devolução (E10). Quando a obrigação fica totalmente liquidada e veio de um destino com motivo `aprovado_apos_a_margem` ou `duplicidade`, o alerta respectivo é resolvido.

## Regras

**`registrar_apuracao_no_livro(ciclo, pedidos_validos, *, autor)`**

- **Pré-condições:**
  - o ciclo tem abertura;
  - cada pedido é do ciclo e tem destino `quita`;
  - a lista não tem repetição.

  Senão, `ValueError` sem escrita. A lista pode ser vazia, por exemplo quando todos ficaram inadimplentes e a rodada é válida só com pendentes. A E11 decide se chama.
- **Efeitos,** num movimento só, o `apuracao`, com a justificativa "Apuração final aprovada (infraestrutura 3.2)":
  - para cada pedido válido, F5, F6 e F7 com os saldos atuais da custódia de cada componente daquele comprador e ciclo. O saldo atual é o pago menos o que já financiou obrigações antes da apuração;
  - o registro `ApuracaoNoLivro` (ciclo, frete efetivo = `abertura.frete`, frete arrecadado = soma de F7);
  - se `efetivo − arrecadado > 0`, uma `Despesa(deficit_frete)` pendente com esse valor;
  - por último, a cobertura automática das tarifas pendentes da rodada.
- A custódia dos pedidos não válidos fica onde está, para as devoluções da E11.

**`registrar_obrigacao_com_comprador(*, origem, rodada, ciclo, comprador, pedido, motivo, produtos, servico, frete)`**

- Componentes ≥ 0 e soma > 0. A origem é única. Pedido, comprador e ciclo são coerentes com a rodada.
- Cria a obrigação e financia pela tabela das fontes, no mesmo movimento (`financiamento_de_obrigacao`, autor `SISTEMA`, justificativa "Devolução devida (P-2): recursos da própria rodada").
- Devolve a obrigação e o sem cobertura.

**`cobrir_obrigacao_com_receita(autor, obrigacao, rodada_fonte, valor, justificativa)`**

Feita pelo administrador, com F11 de `receita_servico(rodada_fonte)` para a obrigação. As recusas, sem escrita, são:

- valor maior que o sem cobertura (`CoberturaExcedente`);
- valor maior que o saldo da receita (`SaldoInsuficiente`);
- justificativa vazia.

**`cobrir_despesa(autor, despesa, *, fonte, valor, justificativa)`**

Feita pelo administrador. A `fonte` é `("receita", rodada)` ou `"reserva"`. A reserva vai para `utilizar_reserva` (E09-05). A receita gera F11, para `despesas_a_cobrir` (tarifa) ou para `frete(r)` (déficit). As recusas são:

- valor maior que o pendente;
- saldo insuficiente;
- invariante violado, só quando a fonte é a reserva.

**`liquidar_obrigacao(obrigacao, valor, *, referencia)`**

Chamada pelo sistema, a partir da E10. Valor > 0 e ≤ devido − liquidado, e ≤ financiado disponível (saldo da conta mais designações ativas). Senão, `LiquidacaoRecusada`, sem escrita. Repetir com a mesma referência e o mesmo valor devolve o existente; com outro valor, levanta `MovimentoConflitante`.

**`frete_do_ciclo(ciclo) -> FreteDoCiclo(efetivo, arrecadado, devolvido, deficit, deficit_coberto)`**

- `devolvido` é a soma do componente frete das obrigações do ciclo criadas depois da apuração.
- `deficit = efetivo − (arrecadado − devolvido)`.
- `deficit_coberto` é a soma das coberturas das despesas de déficit do ciclo mais as coberturas do componente frete sem cobertura das obrigações.
- Antes da apuração, todos os campos são `None`: não há frete efetivo (infraestrutura 3.1).

## Interfaces

- As funções acima.
- `ApuracaoNoLivro`, um registro só de inserção, um por ciclo.
- As exceções `LiquidacaoRecusada` e `CoberturaExcedente` (esta, da E09-05).

## Invariantes

- A soma do que a apuração tirou da custódia de um pedido é exatamente o saldo da custódia dele naquele momento. Depois da apuração, a custódia do pedido válido fica zerada.
- Nenhuma obrigação é financiada acima do devido, nem liquidada acima do devido.
- A fonte de cada financiamento automático é sempre da mesma rodada da obrigação.
- `deficit` é exatamente o frete efetivo menos o arrecadado líquido, e nunca é cobrado do comprador.

## Casos-limite e concorrência

- **Apuração concorrendo com uma entrada tardia** (um pagamento aprovado durante a margem do mesmo ciclo): a entrada trava a custódia, e a apuração usa os saldos sob a trava. A E11 trata o pagamento depois da apuração (cenário 51). Aqui só se garante que nenhum valor é perdido ou contado duas vezes.
- **Duas obrigações do mesmo comprador concorrendo pela mesma custódia:** serializadas pela trava. A soma financiada ≤ saldo, e o resto fica sem cobertura.
- **Duas liquidações concorrentes da mesma obrigação,** com referências diferentes, que juntas passam do devido: uma passa e a outra é recusada.
- **Cobertura automática de tarifa concorrendo com uma retirada da receita** (E09-07): uma das duas espera a trava. A receita nunca fica negativa.

## Dependências e decisões em aberto

Depende de E09-04 e E09-05. Nenhuma decisão em aberto. Herdados registrados na milestone para E10, E11, E12, E13 e E14.
