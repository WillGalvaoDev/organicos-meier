# E11-03 — Caixas invalidadas e mínimo remanescente: o resultado da apuração

Fatia 3 de 8 da milestone **E11 — Apuração final e fila de pendentes**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E11-01.

## Contexto e objetivo

Depois de cancelar os não pagos (E11-01 e E11-02), a apuração:
- invalida as caixas que ficaram incompletas por inadimplência, sem reorganizar as unidades (§8.2, passo 3.3);
- recalcula o mínimo considerando só os produtos pagos que ainda podem ser pedidos (passo 3.5).

O resultado é um dos dois:
- **válida:** o mínimo continua atendido, e o resultado vai para o avanço do administrador;
- **retorno para interesse:** o mínimo não é atendido.

Esta fatia calcula e registra o resultado. Os efeitos de cada resultado são das fatias E11-04 (válida) e E11-05 (retorno).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §8.2, passos 3.3, 3.5, 3.6 e 3.7 | Invalidar caixas incompletas por inadimplência, sem reorganizar. Recalcular o mínimo só com produtos pagos que ainda podem ser pedidos. Mínimo atendido: resultado ao administrador. Não atendido: retorno para interesse. |
| Especificação §6.3 | Ao abrir o pagamento, a composição das caixas foi congelada, com as parcelas de cada comprador em cada caixa. Não redistribuir compradores entre caixas por inadimplência. |
| Especificação §6.1 | O mínimo é monetário e considera só produtos. |
| Especificação §9.2 e Q-7 | Valores pelos registrados no ciclo original, `ROUND_HALF_UP`. |
| Herdado da E08 | As caixas a invalidar estão em `ParcelaNoPedido.caixa`. |
| Cenários §16 | 13 (a invalidação da caixa inteira, sem realocação) e a parte do resultado de 14 e 15 |

## Escopo

**Dentro:**
- O registro `CaixaInvalidada`.
- O resultado na `ApuracaoFinal`: `resultado`, `valor_valido` e `minimo`.
- O cálculo, dentro da transação da apuração, depois da E11-02.

**Fora:** os efeitos do resultado (E11-04 e E11-05).

## Modelo

- **`ApuracaoFinal`** ganha:
  - `resultado`: `valida` ou `retorno_para_interesse`;
  - `valor_valido` (dinheiro);
  - `minimo` (dinheiro, o do ciclo).

  Como o registro só aceita inserção, ele passa a ser gravado depois do cálculo, com tudo preenchido. A migração da tabela nasce sem linhas fora dos testes.
- **`CaixaInvalidada`** (só inserção): `apuracao`, `produto`, `numero` (a caixa do produto no ciclo), única por (`apuracao`, `produto`, `numero`).

## Regras

- **Caixa:** para cada produto com múltiplo no pedido congelado, a caixa `n` do produto no ciclo é o conjunto das `ParcelaNoPedido` da abertura com `item.produto = produto` e `caixa = n`.
- **Caixa invalidada:** a que tem ao menos uma `ParcelaNoPedido` de pedido não pago. Ela é invalidada inteira. As unidades dos pagos nela não vão para outra caixa, e nenhuma caixa é refeita (§6.3, cenário 13).
- **Produto sem múltiplo:** não tem caixa. As unidades dos não pagos simplesmente saem, e as dos pagos continuam válidas.
- **Unidades invalidadas de um item pago:** a soma das quantidades das `ParcelaNoPedido` do item em caixas invalidadas.
- **Valor válido do item pago:** o subtotal registrado menos o valor de produtos que o reembolso parcial da E10-02 daria para as unidades invalidadas, num pedido sem reembolso anterior:
  - todas as unidades do item invalidadas: o subtotal inteiro;
  - senão: `arredondar_centavos(subtotal × invalidadas ÷ quantidade)`, com `ROUND_HALF_UP`.

  O cálculo é o mesmo da E10-02, sem gravar nada. A E11-04 grava o reembolso com o mesmo valor.
- **Valor válido da apuração:** a soma dos valores válidos dos itens dos pedidos pagos.
- **Mínimo:** `Ciclo.minimo`, o registrado no início do fechamento.
- **Resultado:**
  - `valida` quando `valor_valido ≥ minimo`;
  - `retorno_para_interesse` quando não.
- **Registro:** a `ApuracaoFinal` com o resultado, e uma `CaixaInvalidada` por caixa. A auditoria da apuração (E11-01) passa a ter:
  - as caixas invalidadas (produto e número);
  - o valor válido;
  - o mínimo;
  - o resultado.

## Invariantes

- Cada caixa invalidada tem ao menos uma parcela de pedido não pago.
- Nenhuma caixa só de pedidos pagos é invalidada.
- O valor válido nunca passa da soma dos produtos dos pedidos pagos.
- O resultado depende só dos registros congelados e das situações sob trava: repetir o cálculo dá o mesmo resultado.

## Casos-limite

- **Todos pagaram:** nenhuma caixa invalidada; o valor válido é a soma dos produtos dos pedidos.
- **Ninguém pagou:** o valor válido é zero, e o resultado é `retorno_para_interesse`, a menos que o mínimo seja zero.
- **Mínimo zero com nenhum pago:** `valida` com zero pedidos, pela regra. A E09-06 aceita lista vazia na apuração no livro.
- **Uma parcela que cruza duas caixas, uma válida e outra invalidada:** só a parte da caixa invalidada conta como invalidada.

## Dependências e decisões em aberto

Depende de E11-02. Nenhuma decisão em aberto.
