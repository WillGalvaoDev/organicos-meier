# E03-04 — Parcela de interesse: modelo e invariantes

Fatia 4 de 8 da milestone **E03 — Fornecedores, catálogo e condições da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Duas regras de condição da E03 dependem das quantidades em interesse:

- o estoque não pode ficar abaixo do total reservado (E03-05);
- o incremento só muda se todas as quantidades reservadas e pendentes continuarem múltiplas dele (E03-06).

As operações sobre interesses (adicionar, reduzir, alocar pendentes, remover pendentes) são da E05. Esta fatia entrega só o **modelo da parcela**, com os campos e as invariantes definidos na infraestrutura 4.10, para que as regras de condição leiam dados reais e possam ser testadas. É o mesmo caminho da E02-01, que criou o `Fornecedor` mínimo antes da E03.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §5 | Cada acréscimo tem posição própria na fila, que preserva a ordem de adição. Restauração não cria parcela nem posição nova. |
| Especificação §5.2 | Pendente não é reserva. Reservado e pendente são separados. |
| Especificação §14 | Parcela: comprador, produto, quantidade decimal exata, posição de adição, situação (ativa, em pedido, pendente, removida), quantidade reservada e quantidade pendente. Restauração e reserva a partir da fila mantêm parcela e posição. |
| Infraestrutura 4.10 | Identificador e sequência imutáveis, por sequência do banco, que definem a FIFO. Restaurar ou reservar muda só situação, reservada e pendente. Reservado + pendente ≤ original. Parcela pendente sem estoque fica com reserva zero. |
| Infraestrutura 4.12 | Quantidades em `NUMERIC(12,3)`. |
| Infraestrutura 5 | `UNIQUE` na sequência das parcelas. |

## Escopo

**Dentro:**

- App `apps.interesses`, com o modelo `ParcelaDeInteresse` e o enum `SituacaoParcela`.
- Sequência do banco, restrições e triggers.
- Funções de leitura `total_reservado(produto)` e `quantidades_em_uso(produto)`.
- `ParcelaFactory`, para os testes.

**Fora:**

- Todo serviço que cria ou altera parcelas: adição, redução, remoção, alocação de pendentes e remoção de pendentes (E05); restauração e inadimplência (E10 ou etapa da apuração).
- Vínculo da parcela com pedido, caixa ou ciclo (E06 e E08).
- Telas.

A E05 pode acrescentar campos e serviços. Não pode remover nem afrouxar as invariantes desta fatia.

## Regras

**Campos:**

| Campo | Regra |
|---|---|
| `sequencia` | `BIGINT`, `UNIQUE`, preenchido pelo banco com `nextval` de uma sequência própria (`interesses_parcela_sequencia`); define a posição FIFO; nunca muda |
| `comprador` | FK para `Conta`, `PROTECT`; nunca muda |
| `produto` | FK para `Produto`, `PROTECT`; nunca muda. O fornecedor da parcela é o do produto |
| `quantidade_original` | `CampoQuantidade`, maior que zero; nunca muda |
| `quantidade_reservada` | `CampoQuantidade`, maior ou igual a zero |
| `quantidade_pendente` | `CampoQuantidade`, maior ou igual a zero |
| `situacao` | `ativa`, `em_pedido`, `pendente` ou `removida` |
| `criada_em` | `agora()` |

**Invariantes no banco:**

- `CHECK quantidade_original > 0`.
- `CHECK quantidade_reservada >= 0 AND quantidade_pendente >= 0`.
- `CHECK quantidade_reservada + quantidade_pendente <= quantidade_original`.
- `CHECK situacao <> 'removida' OR (quantidade_reservada = 0 AND quantidade_pendente = 0)`.
- `CHECK situacao <> 'pendente' OR quantidade_reservada = 0`: uma parcela marcada como pendente não tem reserva, porque não há reserva fictícia (infraestrutura 4.10). Uma parcela atendida em parte pela fila (reservada e pendente ao mesmo tempo, como C no cenário 75) volta a `ativa`, com as duas quantidades.
- Trigger que recusa `UPDATE` de `sequencia`, `comprador_id`, `produto_id` e `quantidade_original`.
- Trigger que recusa `DELETE`: parcelas removidas ficam como histórico.

**Sequência:**

- O valor vem do banco na inserção, não do Python. Duas inserções concorrentes recebem valores distintos e crescentes na ordem de obtenção.
- O modelo não deixa a aplicação escolher a sequência: um valor informado na criação é ignorado ou recusado. O implementador registra qual dos dois e testa.

**Leituras:**

- `total_reservado(produto) -> Decimal`: soma de `quantidade_reservada` das parcelas do produto em situação `ativa` ou `em_pedido`, com `Decimal("0.000")` quando não há nenhuma.
  - É a quantidade que o estoque da rodada ativa precisa cobrir.
  - Durante a fase de interesse, só as parcelas da rodada ativa podem estar nessas situações. A E05 e a E06 mantêm isso ao encerrar ou reiniciar ciclos. Se a E05 acrescentar o vínculo da parcela com a rodada, esta função passa a filtrar também pela rodada ativa, sem mudar a assinatura.
- `quantidades_em_uso(produto) -> list[Decimal]`: todas as quantidades reservadas e pendentes maiores que zero das parcelas do produto que não estão `removida`, inclusive as pendentes da fila do fornecedor. É a entrada da validação de incremento (E03-06, infraestrutura 4.12).
- As duas aceitam um `QuerySet` já travado pelo chamador, ou recebem um parâmetro para travar as linhas lidas com `select_for_update`, em ordem de `sequencia`. A forma é escolha do implementador; a E03-05 e a E03-06 dependem dela.

**Comprador:** a parcela é de uma conta de papel `comprador`. A verificação fica nos serviços da E05, que usam a política `comprador_ativo` (E02-10). Esta fatia não acrescenta restrição no banco para isso.

## Interfaces

- `apps/interesses/models.py`: `SituacaoParcela` e `ParcelaDeInteresse`.
- `apps/interesses/consultas.py`: `total_reservado` e `quantidades_em_uso`.
- Migração com a sequência, os `CHECK`s e as triggers.
- `tests/fabricas.py`: `ParcelaFactory`, que aceita situação e quantidades.

## Invariantes

- A sequência de uma parcela nunca muda e nunca se repete.
- Reservado + pendente nunca passa da quantidade original.
- Parcela removida não tem reserva nem pendência.
- Nenhuma parcela é apagada.

## Casos-limite e concorrência

- **Parcela atendida em parte pela fila** (8 originais, 4 reservadas, 4 pendentes, `ativa`): aceita.
- **Parcela `pendente` com reserva maior que zero:** recusada.
- **Inserções concorrentes:** 20 inserções em paralelo recebem 20 sequências distintas.

## Dependências e decisões em aberto

- Depende de E02-01 (`Conta`) e E03-03 (`Produto`).
- Sem decisões em aberto.
