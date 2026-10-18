# E05-04 — Progresso elegível e caixas

Fatia 4 de 7 da milestone **E05 — Interesses, reservas e progresso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O mínimo do fornecedor é monetário e só considera produtos. Em produto com múltiplo, só contam as unidades que formam caixas completas (§6.1).

Esta fatia entrega a consulta única que calcula:

- o progresso elegível da rodada;
- as caixas completas e os excedentes de cada produto;
- a participação de um comprador nas caixas.

Ela também mostra o progresso agregado ao administrador, na página de estoque da rodada. A tela do comprador usa a mesma consulta (E05-05). O fechamento (E06) e o portal do fornecedor (E13) a reaproveitam.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §6.1 | Mínimo monetário, só de produtos, sem frete nem taxa. Sem múltiplo, toda quantidade em interesse contribui. Com múltiplo `m`, só `floor(total / m) × m`. A regra é por produto, sem misturar produtos para completar caixa. Exemplo: 18 × R$ 10,00 com múltiplo 12 dá R$ 180,00 bruto e R$ 120,00 elegível, uma caixa completa e seis unidades aguardando. |
| Especificação §6.2 | Para produtos com múltiplo, o comprador vê: total agregado, caixas completas, unidades faltantes para a próxima caixa, quantas das suas unidades estão em caixas completas e quantas estão excedentes. Sem nomes nem pedidos de outros compradores. |
| Especificação §6.3 | A remoção dos excedentes no fim do fechamento respeita a prioridade por adição (E06). |
| Especificação §5.2 | Pendentes sem reserva não entram no mínimo. |
| Especificação §7 | Atingir o mínimo apenas habilita o administrador a iniciar o fechamento. |
| Especificação §9 | `T` é a soma dos subtotais elegíveis de todos os compradores. Cada subtotal é arredondado uma vez com `ROUND_HALF_UP`. |
| Especificação §13 | O administrador vê rodadas e mínimos. |
| Cenários §16 | 4, 6, 7, 77 e 104 (parte do progresso). |
| Infraestrutura 4.10 | O cálculo do mínimo e a formação de caixas só leem a quantidade reservada. |
| Infraestrutura 8 | T-47 (parte do progresso). |

## Escopo

**Dentro:**

- A consulta `progresso_da_rodada(rodada, comprador=None)` e os seus `dataclass`es.
- O bloco de progresso na página de estoque do administrador (`/administracao/rodadas/<id>/estoque/`).

**Fora:**

- A tela do comprador (E05-05).
- A verificação do mínimo para iniciar e encerrar o fechamento (E06), que usa esta consulta.
- A remoção dos excedentes e o congelamento das caixas (E06 e E08).
- A tela do fornecedor (E13), que usa esta consulta sem a participação de compradores.

## Decisões técnicas

- **Caixas por ordem de adição.**
  - As unidades reservadas de um produto entram nas caixas na ordem crescente de `sequencia` das parcelas, e uma parcela pode ficar dividida entre a última caixa completa e o excedente.
  - É a mesma prioridade que a §6.3 manda usar na remoção dos excedentes. O cenário 7 confirma: com 8 de A e 10 de B, a primeira caixa tem 8 de A e 4 de B.
  - A E06 usa essa mesma divisão para remover os excedentes.
- **Valor elegível igual ao `T` da cobrança.** O valor elegível da rodada é a soma, por comprador e por produto, de `calcular_subtotal(preco, unidades do comprador em caixas completas)`.
  - Cada subtotal é arredondado uma vez com `ROUND_HALF_UP` (E03-03), como no pedido (§9).
  - Assim, o progresso mostrado e o mínimo que a E06 verifica usam o mesmo número que a E08 usa como `T`, com o preço vigente.
- **Só reservado conta.** Entram só as parcelas `ativa` com `quantidade_reservada > 0`, e só a parte reservada. Pendentes nunca contam (R-6, cenários 77 e 104).
- **Preço vigente:** o preço do produto no momento da leitura. Nada é gravado. Uma alteração de preço muda o progresso na próxima leitura (§5.1, E05-06).
- **Mínimo:** `fornecedor.minimo` vigente. A partir do fechamento ele está congelado (E03-02) e coincide com o do ciclo.
- **Consultas em número fixo**, sem crescer com o número de produtos ou de parcelas.

## Regras

**Consulta** (`apps/interesses/progresso.py`):

```
progresso_da_rodada(rodada, comprador=None) -> ProgressoDaRodada
```

**`ProgressoDaRodada`** (`dataclass` imutável):

| Campo | Valor |
|---|---|
| `rodada` | a rodada |
| `minimo` | `fornecedor.minimo` |
| `valor_elegivel` | soma de `valor_elegivel` dos produtos |
| `atingido` | `valor_elegivel >= minimo` |
| `falta` | `max(minimo − valor_elegivel, 0)` |
| `percentual` | `int`. Com `minimo == 0`, vale 100. Nos demais casos, `valor_elegivel × 100 ÷ minimo` arredondado para baixo (`ROUND_FLOOR`), com teto 100. Só chega a 100 quando `atingido` é verdadeiro |
| `produtos` | lista de `ProgressoDoProduto`, um por estoque da rodada, por nome e id do produto |

**`ProgressoDoProduto`:**

| Campo | Valor |
|---|---|
| `produto` | o produto |
| `total_reservado` | soma das reservas das parcelas `ativa` do produto |
| `quantidade_elegivel` | `total_reservado` sem múltiplo; com múltiplo `m`, `(total_reservado // m) × m` |
| `caixas_completas` | `int(total_reservado // m)`; `None` sem múltiplo |
| `faltam_para_proxima_caixa` | `m − (total_reservado % m)`; `None` sem múltiplo. Com total múltiplo de `m`, inclusive zero, vale `m` |
| `excedente` | `total_reservado − quantidade_elegivel` |
| `valor_bruto` | `calcular_subtotal(preco, total_reservado)` |
| `valor_elegivel` | soma, por comprador, de `calcular_subtotal(preco, em_caixas do comprador)` |
| `do_comprador` | `ParticipacaoDoComprador` do comprador informado, com zeros quando ele não tem parcela no produto; `None` quando nenhum comprador é informado |

**`ParticipacaoDoComprador`:**

| Campo | Valor |
|---|---|
| `reservado` | reservas do comprador no produto (parcelas `ativa`) |
| `pendente` | pendências do comprador no produto (parcelas `ativa` e `pendente`) |
| `em_caixas` | unidades do comprador dentro da `quantidade_elegivel`, pela ordem de sequência; igual a `reservado` sem múltiplo |
| `excedente` | `reservado − em_caixas` |
| `subtotal` | `calcular_subtotal(preco, reservado)` |

**Distribuição pelas caixas:**

1. Percorra as parcelas `ativa` do produto, em ordem crescente de `sequencia`, acumulando `quantidade_reservada`.
2. Uma parcela está toda em caixas se o acumulado depois dela for menor ou igual a `quantidade_elegivel`.
3. Senão, só a parte até `quantidade_elegivel` está em caixas, e o resto é excedente. As parcelas seguintes são excedente inteiro.

Toda a aritmética é em `Decimal`, sem `float`.

**Privacidade:**

- A consulta nunca devolve contas, ids de parcela nem quantidades de outros compradores identificáveis. A `ParticipacaoDoComprador` só existe para o comprador informado.
- `minimo`, `valor_elegivel`, `falta`, `valor_bruto` e o `valor_elegivel` dos produtos são para o administrador, o fechamento e o fornecedor (E13).
- As telas do comprador usam só `percentual`, `atingido`, as quantidades e caixas agregadas de produtos com múltiplo e a própria participação (E05-05).
- O mínimo do fornecedor é um campo nunca exibido ao comprador (E03-08), e o valor elegível junto com o percentual permitiria calculá-lo.

**Formato dos textos:** nesta fatia e nas seguintes, `R$ <valor>` indica o resultado do filtro `reais`, que já inclui o prefixo `R$ `. O prefixo não é repetido.

**Bloco do administrador** (página de estoque da E03-05):

- Linha de resumo:
  - "Progresso elegível: R$ <valor_elegivel> de R$ <minimo>";
  - em seguida, "Mínimo atingido." ou "Faltam R$ <falta>.".
- Tabela por produto, com as colunas:
  - nome;
  - total em interesse;
  - elegível;
  - valor bruto;
  - valor elegível;
  - caixas completas;
  - faltam para a próxima caixa;
  - excedente.

  Produto sem múltiplo mostra "—" nas colunas de caixa. Valores no formato do filtro `reais`, quantidades no de `quantidade_br`.
- Nenhuma identidade de comprador.
- O bloco aparece em qualquer etapa e não oferece ação de fechamento, que é da E06.

## Interfaces

- `apps/interesses/progresso.py`: `progresso_da_rodada`, `ProgressoDaRodada`, `ProgressoDoProduto` e `ParticipacaoDoComprador`.
- `templates/rodadas/estoque.html` e a view `estoque`: o bloco de progresso.

## Invariantes

- `valor_elegivel` não depende da ordem de leitura e é igual a `T` calculado com o preço vigente.
- Pendentes nunca entram em `total_reservado`, `quantidade_elegivel` nem nos valores.
- A soma de `em_caixas` de todos os compradores de um produto é igual a `quantidade_elegivel`.
- Nenhuma escrita: a consulta não muda etapa nem grava nada (cenário 4).

## Casos-limite e concorrência

- **Cenário 6:** 18 unidades de R$ 10,00, com múltiplo 12, dão valor bruto R$ 180,00, valor elegível R$ 120,00, 1 caixa, 6 de excedente e faltam 6.
- **Cenário 7:** A adiciona 8 e B adiciona 10, com múltiplo 12. A tem 8 em caixas e 0 excedente; B tem 4 em caixas e 6 excedentes.
- **Cenário 104:** R$ 10,00, mínimo R$ 100,00, A com 8 reservados e C com 5 pendentes. O valor elegível é R$ 80,00, `atingido` é falso e falta R$ 20,00. A participação de C mostra reservado 0 e pendente 5.
- **Cenário 4:** com o valor elegível acima do mínimo, a etapa continua `interesse`.
- **Arredondamento por comprador:** produto de R$ 2,50 por kg, incremento 0,25, sem múltiplo, com A e B com 0,25 kg cada. O valor elegível é R$ 1,26 (0,63 + 0,63), e não R$ 1,25 (cenário 89).
- **Múltiplo fracionário:** múltiplo 1 kg, incremento 0,25 e total 2,75 kg dão 2 caixas, 0,75 de excedente e faltam 0,25.
- **Rodada sem produtos:** valor elegível 0. `atingido` é verdadeiro só se o mínimo for 0.
- **Total zero com múltiplo:** 0 caixas, faltam `m` e excedente 0.

## Dependências e decisões em aberto

- Depende de E03-03, E03-05 e E05-01.
- Sem decisões em aberto.
