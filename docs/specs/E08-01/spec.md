# E08-01 — Cálculo dos valores da cobrança

Fatia 1 de 7 da milestone **E08 — Cobrança: abertura, congelamento e prazos**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Na abertura do pagamento, cada comprador recebe um pedido com valores congelados:

- produtos;
- serviço de 5%;
- uma parte do frete;
- o total.

Esta fatia entrega só a conta, como uma função pura, sem banco nem tela. Ela é usada pela abertura (E08-02). Fica separada para que as tabelas de arredondamento sejam testadas sozinhas e não dependam de nenhum fluxo.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §9 | Para cada comprador: `P` = subtotal de produtos elegíveis; `T` = soma dos `P` da rodada; `F` = frete total informado; serviço = `5% × P`; frete do comprador = `F × P / T`; total = produtos + serviço + frete. "A soma das parcelas de frete deve ser exatamente o frete informado, inclusive quando houver centavos residuais." Subtotal do item arredondado uma única vez, com `ROUND_HALF_UP`; `P` é a soma dos subtotais arredondados. |
| Especificação §6.1 | O mínimo considera só produtos, sem frete nem serviço. |
| Infraestrutura 4.12 (R-1) | `subtotal = (preço × quantidade).quantize(0.01, ROUND_HALF_UP)`, calculado uma vez. Sem `float` em dinheiro ou quantidade, com verificação estática. |
| Cenários §16 | 10, 64, 88, 89. |
| Testes técnicos | T-39. |
| E01-03, E03-04 | `CampoDinheiro`, `arredondar_centavos`, `calcular_subtotal` (catálogo). |

## Escopo

**Dentro:**

- `apps/pedidos/calculo.py`, com os tipos de entrada e saída e a função `calcular_cobranca`.
- O novo app `apps.pedidos`, sem modelos nesta fatia.
- A varredura estática de `float` exigida pelo T-39, que o projeto ainda não tem. Ela fica nos testes, e não em produção. Cobre os módulos de dinheiro e quantidade e acusa literal `float`, chamada a `float` e `FloatField`. `apps/contas` fica fora, porque usa `float` em instantes de autenticação, sem dinheiro.

**Fora:**

- Quais parcelas entram no pedido, que é a abertura (E08-02).
- Reembolsos (E10).

## Decisões técnicas

- **Item = comprador e produto.** O subtotal é calculado sobre a quantidade total do comprador naquele produto, e não parcela por parcela. É a mesma unidade de arredondamento do progresso elegível (E05-04), então o `T` da cobrança é igual ao valor elegível mostrado no fechamento, com os mesmos preços.
- **Serviço:** `arredondar_centavos(P × 0,05)`, com `ROUND_HALF_UP`.
- **Rateio do frete pelo maior resto.**
  1. Cada comprador recebe `F × P / T` truncado para centavos (`ROUND_DOWN`).
  2. Os centavos que faltam para chegar a `F` vão, um a um, aos compradores de maior resto (a parte descartada no truncamento).
  3. No empate de resto, recebe primeiro o comprador de menor `comprador_id`.

  A soma é sempre exatamente `F`, e o resultado só depende das entradas. A especificação pede regra determinística, sem fixar qual. O maior resto é a que mais se aproxima da proporção exata.
- **Frete zero** é aceito: cada comprador paga frete zero.

## Regras

```
@dataclass(frozen=True)
class ItemACobrar:
    produto_id: int
    preco_unitario: Decimal   # duas casas
    quantidade: Decimal       # até três casas, > 0

@dataclass(frozen=True)
class CompradorACobrar:
    comprador_id: int
    itens: tuple[ItemACobrar, ...]

@dataclass(frozen=True)
class ItemCobrado:
    produto_id: int
    preco_unitario: Decimal
    quantidade: Decimal
    subtotal: Decimal

@dataclass(frozen=True)
class CobrancaDoComprador:
    comprador_id: int
    itens: tuple[ItemCobrado, ...]
    produtos: Decimal   # P
    servico: Decimal
    frete: Decimal
    total: Decimal

calcular_cobranca(compradores: Sequence[CompradorACobrar], frete: Decimal) -> list[CobrancaDoComprador]
```

1. **Validação** (`ValueError`, sem resultado parcial):
   - `frete` é `Decimal` com no máximo duas casas e maior ou igual a zero;
   - cada preço é `Decimal` com no máximo duas casas e maior ou igual a zero;
   - cada quantidade é `Decimal` maior que zero, com no máximo três casas;
   - não há `float`, e cada comprador tem pelo menos um item;
   - não há comprador repetido nem produto repetido dentro de um comprador;
   - a lista não é vazia, e `T` é maior que zero.
2. **Itens:** `subtotal = calcular_subtotal(preco_unitario, quantidade)`. Os itens saem em ordem de `produto_id`.
3. **Valores por comprador:** `P` = soma dos subtotais; serviço = `arredondar_centavos(P × Decimal("0.05"))`; `T` = soma dos `P`.
4. **Frete:** maior resto, como nas Decisões técnicas. Com `F = 0`, todos ficam com zero.
5. **Total:** `produtos + servico + frete`, sem novo arredondamento, porque as três parcelas já têm duas casas.
6. **Saída:** os compradores em ordem de `comprador_id`. Todos os valores são `Decimal` com exatamente duas casas.

## Interfaces

- `apps/pedidos/calculo.py`: os quatro tipos, `calcular_cobranca` e a constante `TAXA_DE_SERVICO = Decimal("0.05")`.
- `apps.pedidos` em `INSTALLED_APPS`.

## Invariantes

- A soma dos fretes é exatamente `F`.
- `P` é a soma dos subtotais já arredondados.
- `total = produtos + servico + frete` em todo comprador.
- A função não lê o banco e não depende da ordem de entrada.

## Casos-limite

- **Um comprador só:** ele paga todo o frete.
- **Frete que não se divide em centavos:** por exemplo, R$ 10,00 entre três compradores com `P` iguais. Cada um recebe R$ 3,33, e o centavo que sobra vai ao de menor `comprador_id`.
- **`P` muito diferentes:** um comprador com `P` pequeno pode ter frete zero depois do truncamento e ainda receber um centavo pelo resto.

## Dependências e decisões em aberto

- Depende de E01-03 e E03-04.
- Sem decisões em aberto.
