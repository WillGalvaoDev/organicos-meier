# E10-02 — Cálculo do reembolso (Q-7): parcial por item, serviço e frete proporcionais, devolução integral do pedido

Fatia 2 de 7 da milestone **E10 — Devoluções**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E10-01.

## Contexto e objetivo

Toda devolução de parte de um pedido pago usa um mesmo cálculo e um mesmo acumulador. Isso vale para:
- a ocorrência de entrega (E14);
- as unidades de caixa invalidada e o mínimo não atingido (E11);
- o reembolso integral do cancelamento (E12).

Esta fatia entrega esse cálculo como serviço. Ele recebe o pedido, o item, a quantidade e uma chave do fato que gerou o reembolso. Grava o reembolso separado do pedido congelado e cria a obrigação com o comprador (E09-06), financiada pela regra da própria rodada.

O cálculo usa só os valores registrados no ciclo original, nunca o preço atual do catálogo. Ele é determinístico, inclusive com vários reembolsos parciais do mesmo item, e nunca devolve mais do que foi cobrado em nenhum componente.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §9.2 | Estorno proporcional de produtos, serviço e frete (exemplo de 31,25). Estornos sucessivos não passam do pago nem devolvem duas vezes a mesma parcela. O estorno integral completa exatamente o saldo restante. Os valores são os registrados. Reembolso parcial de item: `subtotal × (quantidade reembolsada ÷ quantidade do item)`, `ROUND_HALF_UP`, acumulado por item limitado ao saldo, e a última parcela é o saldo exato. Serviço e frete com o mesmo controle por componente. Cada devolução registrada separadamente, sem alterar o pedido. |
| Especificação §9.1 | Motivos previstos de estorno. |
| Infraestrutura 4.12 (Q-7) | Rotina `reembolso_parcial(item, quantidade)` sob trava do item e do acumulador: os passos 1 a 4. Serviço e frete pelo mesmo esquema por componente, com acumulador próprio. A mesma rotina atende ocorrências, caixas invalidadas e o reembolso integral do cancelamento, com a quantidade restante. |
| Infraestrutura 3.2 e 4.8 | A devolução integral é o valor pago menos as devoluções concluídas ou pendentes. |
| Herdado da E09 | Cada devolução vira `registrar_obrigacao_com_comprador` (E09-06), com os componentes calculados aqui. |
| Cenários §16 | 90, 91, 112, 113, 114, 115, 116 e 117, no nível do serviço |
| Testes técnicos | T-40, T-51, T-52 e T-53 |

## Escopo

**Dentro:**
- Os registros `Reembolso` e `ItemReembolsado`.
- Os serviços `reembolso_parcial` e `reembolso_integral_do_pedido`.
- A obrigação gerada por cada reembolso com valor.

**Fora:**
- Quem chama e quando: E11, E12 e E14.
- A execução da devolução (E10-04 a E10-06).
- Telas (E10-07).
- As devoluções dos pagamentos que não quitam (destinos `devolucao` e `sem_pedido` da E09-04). Elas não passam por aqui, porque devolvem o pagamento inteiro de outro pagamento, e não parte do pedido.

## Regras

**Pedido elegível.** Só um pedido com `SituacaoDoPedido.situacao = pago` recebe reembolso. Fora disso: `ReembolsoRecusado("o pedido não está pago")`, sem escrita.

**Registros (só inserção):**

| Registro | Campos |
|---|---|
| `Reembolso` | `pedido`; `chave` (texto não vazio, até 64 caracteres, única: identifica o fato, por exemplo `ocorrencia:<pk>`); `motivo`; `produtos`, `servico` e `frete` (`Decimal`, ≥ 0); `autor` (conta ou `SISTEMA`); `criado_em` |
| `ItemReembolsado` | `reembolso`; `item` (`ItemDoPedido` do mesmo pedido); `quantidade` (> 0, no máximo 3 casas); `valor` (≥ 0) |

**Motivos:**
- `minimo_nao_atingido`;
- `caixa_invalidada`;
- `ocorrencia_de_entrega`;
- `cancelamento_da_rodada`.

Outro motivo é recusado com `ValueError`.

**Acumulados.** São lidos dos registros, sempre depois da trava (abaixo):
- **por item** (`ItemDoPedido`): `q_r`, a soma das quantidades reembolsadas, e `R`, a soma dos valores;
- **por pedido:** `R_p`, `R_s` e `R_f`, as somas de `produtos`, `servico` e `frete` de todos os reembolsos do pedido.

Todo reembolso registrado conta, qualquer que seja o estado da devolução depois: devida, em processamento, concluída ou falha. É o "concluídas ou pendentes" do §9.2 e da infraestrutura 4.8.

**`reembolso_parcial(item, quantidade, *, chave, motivo, autor)`**, para o item com subtotal `S` e quantidade `Q` registrados no `ItemDoPedido`:
1. A `quantidade` precisa ser um `Decimal` maior que zero, com no máximo 3 casas e múltiplo do `incremento` registrado no item. Senão: `ReembolsoRecusado("quantidade inválida")`.
2. Se `q_r + quantidade > Q`: `ReembolsoRecusado("passa da quantidade paga")`.
3. Valor dos produtos:
   - se `q_r + quantidade == Q`, `v = S − R` (saldo exato);
   - senão, `v = min(arredondar((S × quantidade) / Q), S − R)`.
4. Serviço e frete, com `P`, `Sv` e `Fr` os valores `produtos`, `servico` e `frete` do `Pedido`:
   - se `R_p + v == P` (o pedido fica todo reembolsado em produtos), `servico = Sv − R_s` e `frete = Fr − R_f`;
   - senão, `servico = min(arredondar(Sv × v / P), Sv − R_s)` e `frete = min(arredondar(Fr × v / P), Fr − R_f)`.
5. Grava um `Reembolso` com uma linha (`ItemReembolsado`: o item, a quantidade e `v`).

**`reembolso_integral_do_pedido(pedido, *, chave, motivo, autor)`**:
- cada item com `q_r < Q` ganha uma linha com `quantidade = Q − q_r` e `valor = S − R`;
- `servico = Sv − R_s` e `frete = Fr − R_f`.

Se tudo for zero (nada restante), não grava nada e devolve `None`.

**`arredondar`** é `arredondar_centavos` (`ROUND_HALF_UP`, 2 casas) sobre o cálculo em `Decimal` exato. Nenhum `float` aparece.

**A obrigação.** Quando `produtos + servico + frete > 0`, o mesmo serviço chama, na mesma transação, `registrar_obrigacao_com_comprador(origem=reembolso, ...)`, com:
- a rodada e o ciclo da abertura do pedido;
- o comprador e o pedido;
- o motivo;
- os três componentes.

O financiamento segue a tabela das fontes da E09-06, antes ou depois da apuração.

Um reembolso com total zero é gravado sem obrigação, como a sexta ocorrência do cenário 115. Ele existe para o acumulado de quantidade.

**Idempotência pela `chave`:**
- **A mesma chave e o mesmo conteúdo** (pedido, motivo, linhas com item e quantidade): a função devolve o reembolso existente, sem nada novo.
- **A mesma chave com conteúdo diferente:** `ReembolsoConflitante`, sem escrita.

**Retorno.** `ReembolsoRegistrado(reembolso, obrigacao, sem_cobertura)`. Sem obrigação, `obrigacao` é `None` e `sem_cobertura` é 0,00.

**Pedido congelado.** `Pedido`, `ItemDoPedido` e `ParcelaNoPedido` nunca são alterados (trigger da E08).

## Interfaces

- `reembolso_parcial(item: ItemDoPedido, quantidade: Decimal, *, chave: str, motivo: str, autor: Conta | Sistema) -> ReembolsoRegistrado`
- `reembolso_integral_do_pedido(pedido: Pedido, *, chave: str, motivo: str, autor: Conta | Sistema) -> ReembolsoRegistrado | None`
- `acumulado_do_item(item) -> (quantidade, valor)` e `acumulado_do_pedido(pedido) -> (produtos, servico, frete)`, só leitura, usados pelas telas e pela E14.
- Exceções `ReembolsoRecusado` (com a mensagem) e `ReembolsoConflitante`.
- As duas funções exigem uma transação aberta, como as do livro-razão (E09).

## Decisões técnicas

- **Trava única por pedido.** A trava é a linha da `SituacaoDoPedido` (`select_for_update`), tomada antes de ler qualquer acumulado. Ela serializa todos os reembolsos do pedido, de qualquer item, porque os acumulados de serviço e frete são do pedido. A ordem global fica `PagamentoNoProvedor` → `SituacaoDoPedido` → `TentativaDePagamento` → contas do livro-razão (regra única da E09-01). A obrigação trava as contas dentro de `registrar_obrigacao_com_comprador`, depois da `SituacaoDoPedido`.
- **Acumulado lido dos registros.** Não há campo de acumulado que possa divergir. A soma vem de `ItemReembolsado` e de `Reembolso`, sob a trava. Os dois registros são só de inserção, como os do livro-razão.
- **"Completa o pedido" pelos produtos.** O serviço e o frete são proporcionais aos produtos (§9.2). Por isso o saldo exato desses dois componentes é devolvido quando os produtos do pedido ficam inteiros. Assim, o reembolso integral e uma sequência de parciais que cobre todos os itens terminam com o pedido inteiro devolvido, componente por componente.
- **A integral não depende do motivo.** O cancelamento (E12) e o mínimo não atingido (E11) chamam a mesma função.

## Invariantes

- Para cada item: `Σ quantidade ≤ Q` e `Σ valor ≤ S`. Com `Σ quantidade = Q`, `Σ valor = S` exatamente.
- Para o pedido: `R_p ≤ P`, `R_s ≤ Sv` e `R_f ≤ Fr`. Com `R_p = P`, os três são iguais aos registrados.
- Cada reembolso com valor tem exatamente uma obrigação, com os mesmos componentes.
- Nenhum preço de catálogo é lido.

## Casos-limite e concorrência

- **Dois parciais do mesmo item em paralelo** (T-53): eles se serializam pela trava. A soma fica ≤ `S`, e uma quantidade que passaria de `Q` é recusada.
- **Parcial e integral do mesmo pedido em paralelo:** em qualquer ordem, a soma final de cada componente é exatamente o registrado.
- **Integral depois de parciais** (cenário 114): devolve exatamente o saldo de cada item e de cada componente.
- **Item com subtotal zero:** o valor é 0,00. Só a quantidade acumula.
- **Pedido com frete zero:** o componente frete fica sempre 0,00.
- **A transação de quem chama é desfeita:** o reembolso e a obrigação também.

## Dependências e decisões em aberto

Depende de E08 (pedido congelado e situação), E09-06 (obrigação) e da regra única de travas (E09-01). Nenhuma decisão em aberto.
