# E03-08 — Catálogo do comprador

Fatia 8 de 8 da milestone **E03 — Fornecedores, catálogo e condições da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O comprador consulta o catálogo por fornecedor, com medidas, incrementos, preços, disponibilidade e múltiplos. O comprador suspenso também consulta as listas.

Esta fatia entrega a consulta, só de leitura. Adicionar ao carrinho, o progresso do mínimo e as caixas são da E05, que acrescenta os controles a estas telas.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Comprador ativo consulta catálogo e regras. Comprador suspenso pode consultar listas. Fornecedor não compra. Restrições verificadas no servidor. |
| Especificação §4.2 | Medida de venda separada do múltiplo do fornecedor. |
| Especificação §4.3 | Fornecedores diferentes têm andamento independente. |
| Especificação §13 | Comprador: catálogo por fornecedor, medidas, incrementos, preços, disponibilidade e múltiplos. |
| Especificação §6.2 | Não exibir nomes ou pedidos de outros compradores. |
| Infraestrutura 4.11 | Rotas de compra exigem o papel de comprador (política da E02-10). |

## Escopo

**Dentro:**

- Rotas `/catalogo/` e `/catalogo/<fornecedor_id>/`, com a política `comprador` (E02-10). Comprador ativo e suspenso passam.
- Consulta `produtos_do_catalogo(fornecedor)`, em `apps/catalogo/consultas.py`.
- Links para o catálogo em `/inicio/` do comprador.

**Fora:**

- Adicionar interesse, carrinho, progresso e caixas (E05).
- Consulta do fornecedor aos próprios produtos (E13).
- Regras de funcionamento e endereço de retirada (etapa de retirada e comunicados).

## Regras

**Fornecedores listados em `/catalogo/`:**

- Entra o fornecedor que tem rodada ativa e pelo menos um produto incluído nela, disponível ou não.
- Para cada um: nome e etapa da rodada, com o nome funcional ("Interesse", "Fechamento" etc.).
- Ordem por nome.

**Produtos exibidos em `/catalogo/<fornecedor_id>/`:**

- Entram os produtos que estão no estoque da rodada ativa (E03-05), disponíveis ou não. Ordem por nome.
- **Produto indisponível** (D-1 da E03-03): aparece com a marcação "Produto indisponível" junto à descrição, em destaque. Ele continua aceitando interesses (E05); a marcação é só informativa.
- **Campos:**
  - nome e descrição;
  - unidade;
  - incremento ("vendido em múltiplos de 0,25 kg");
  - preço unitário ("R$ 7,99 / kg");
  - múltiplo, quando existir ("múltiplo de compra: 12");
  - disponibilidade: "Sem limite" quando o estoque não tem limite, "Esgotado" quando `estoque_livre` é zero, e "<quantidade> disponível" nos demais casos.
- **Exibição de quantidades e valores:** como na E03-03 (vírgula, sem zeros à direita), com dinheiro no formato `R$ 1.234,56`.
- **Fornecedor sem rodada ativa ou inexistente:** 404, sem diferenciar os casos.
- **Etapas fora de `interesse` e `fechamento`:** o catálogo ainda é exibido, com a etapa. As restrições de compra de cada etapa são da E05 em diante.

**Campos nunca exibidos:**

- e-mail do pedido formal, mínimo, prazo e informações de frete do fornecedor;
- quantidades reservadas e pendentes individuais;
- qualquer dado de outros compradores;
- contas vinculadas ao fornecedor.

O progresso agregado vem com a E05. O total reservado não é exibido, só o estoque livre.

**Acesso:**

- Política `comprador` (E02-10): comprador ativo e suspenso, 200.
- Conta de fornecedor e administrador: 403.
- Anônimo: redirecionamento para `/entrar/`.

**Consultas:** sem N+1. O número de consultas da página do fornecedor não cresce com o número de produtos. O teste fixa um teto, medido com 1 e com 20 produtos.

## Interfaces

- `apps/catalogo/consultas.py`: `fornecedores_no_catalogo()` e `produtos_do_catalogo(fornecedor)`, que devolve produto, estoque e estoque livre.
- `apps/catalogo/views.py`, templates e rotas, com política declarada.

## Invariantes

- O catálogo nunca mostra produto fora da rodada ativa.
- Todo produto indisponível exibido traz a marcação "Produto indisponível".
- O catálogo nunca expõe dados de compradores nem os campos internos do fornecedor listados acima.

## Casos-limite e concorrência

- **Produto incluído com estoque 0:** aparece como "Esgotado".
- **Limite 10 com 10 reservados:** "Esgotado". Limite 10 com 6 reservados: "4 disponível". Na unidade `kg`: "4 kg disponível".
- **Produto marcado indisponível depois de incluído:** continua no catálogo, com a marcação. Voltando a disponível, a marcação some.
- **Fornecedor com rodada ativa e só produtos indisponíveis:** aparece em `/catalogo/`, e todos os produtos dele trazem a marcação.
- **Fornecedor com rodada ativa sem nenhum produto incluído:** fora de `/catalogo/`; a página dele mostra a mensagem "Nenhum produto nesta rodada.".
- **Sem concorrência crítica:** só leitura.

## Dependências e decisões em aberto

- Depende de E02-10 (políticas), E03-02, E03-03 e E03-05.
- Sem decisões em aberto.
