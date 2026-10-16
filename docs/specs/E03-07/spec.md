# E03-07 — Condições registradas por ciclo e congelamento consolidado

Fatia 7 de 8 da milestone **E03 — Fornecedores, catálogo e condições da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Cada ciclo registra os valores de mínimo, múltiplos, incremento e estoque vigentes no início do seu fechamento. Quando a rodada volta para interesse, as condições ficam editáveis de novo, e os registros dos ciclos anteriores continuam com os valores originais.

O início do fechamento é uma transição da E06. Esta fatia entrega:

1. o ciclo e o registro imutável das condições;
2. o serviço que a E06 chama na transição;
3. o teste consolidado do congelamento (T-23), que cobre as quatro condições e o preço em todas as etapas.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §4.4 | Requisito derivado: cada ciclo registra os valores de mínimo, múltiplos, incremento e estoque vigentes no início do seu fechamento. Na volta a interesse, as condições ficam editáveis de novo, sem modificar os registros dos ciclos anteriores. O preço fica fora do congelamento. |
| Especificação §14 | Rodada: mínimo, múltiplos e estoque congelados por ciclo a partir do fechamento. Estados de rodada e de ciclos anteriores são independentes. |
| Cenários §16 | 72 (consolidado) e 73. |
| Infraestrutura 4.10 | No início do fechamento, os valores vigentes são gravados no ciclo, e os ciclos anteriores nunca são reescritos. |
| Infraestrutura 4.12 | Os ciclos anteriores mantêm o incremento registrado no seu snapshot. |
| Infraestrutura 5 | Registros históricos só aceitam inserção. |
| Testes técnicos | T-23 (consolidado). |

## Escopo

**Dentro:**

- Modelos `Ciclo` e `CondicaoDoProdutoNoCiclo` em `apps.rodadas`, só de inserção (`RegistroSoInsercao` e a proteção no banco da E01-04).
- Serviço `registrar_condicoes_do_ciclo(rodada)`.
- Leitura `ciclo_vigente(rodada)`.
- Teste consolidado do T-23 e do cenário 72.

**Fora:**

- A transição para `fechamento` e a volta para `interesse` (E06). A E06 chama o serviço desta fatia na mesma transação em que grava `fechamento`.
- Pedidos, caixas e cobranças vinculados ao ciclo (E06 e E08).
- Tela de consulta de ciclos. Os registros aparecem nas telas das etapas que os usam.

## Regras

**Ciclo** (`Ciclo`):

| Campo | Regra |
|---|---|
| `rodada` | FK `PROTECT` |
| `numero` | inteiro de 1 em diante, em sequência por rodada; `UNIQUE (rodada, numero)` |
| `iniciado_em` | `agora()`, o instante do início do fechamento |
| `minimo` | `CampoDinheiro`, o mínimo do fornecedor naquele instante |

**Condição do produto no ciclo** (`CondicaoDoProdutoNoCiclo`):

| Campo | Regra |
|---|---|
| `ciclo` | FK `PROTECT` |
| `produto` | FK `PROTECT` |
| `incremento` | `CampoQuantidade` |
| `multiplo` | `CampoQuantidade`, nulo quando o produto não tem múltiplo |
| `limite_estoque` | `CampoQuantidade`, nulo quando o estoque não tem limite |

- `UNIQUE (ciclo, produto)`.
- As duas tabelas só aceitam inserção: `UPDATE` e `DELETE` são recusados no ORM e no banco, como na E01-04.

**Registro** (`registrar_condicoes_do_ciclo(rodada) -> Ciclo`):

1. Exige transação aberta.
2. Chama `travar_condicoes(rodada.fornecedor)` (E03-02). Exige que a rodada travada seja a recebida. Fora de `interesse`, levanta `CondicoesCongeladas`: o registro só acontece no instante da passagem de interesse para fechamento.
3. Trava os produtos da rodada e os estoques dela, na ordem global de travas.
4. Cria o `Ciclo` com `numero = maior número da rodada + 1` e o mínimo atual do fornecedor.
5. Cria uma `CondicaoDoProdutoNoCiclo` para cada `EstoqueDaRodada` da rodada, com incremento e múltiplo atuais do produto e o limite atual do estoque. Produtos do fornecedor fora da rodada não são registrados.
6. Grava a auditoria `ciclo.registrar_condicoes` com `{"rodada": <id>, "ciclo": <id>, "numero": <n>}`.
7. Devolve o ciclo.

**Contrato com a E06:** a E06 chama `registrar_condicoes_do_ciclo` e grava `etapa = fechamento` na mesma transação, com as mesmas travas. Assim, nenhuma alteração de condição cabe entre o registro e o congelamento. Uma segunda chamada no mesmo ciclo é recusada, porque a rodada já não está em `interesse`.

**Leitura:** `ciclo_vigente(rodada) -> Ciclo | None` devolve o ciclo de maior número, ou `None` se a rodada nunca entrou em fechamento.

**Teste consolidado (T-23 e cenário 72):**

Para cada condição (mínimo, múltiplo, incremento, inclusão de estoque e alteração de estoque) e para cada situação abaixo, o teste chama a rota e o serviço:

- `fechamento`;
- `fechamento_encerrado`;
- `pagamento`;
- `aguardando_fornecedor`;
- sem rodada ativa, depois de `disponivel_para_retirada` e depois de `cancelada`.

Em todos os casos, o resultado é 409 ou `CondicoesCongeladas`, sem escrita nem auditoria. Na mesma matriz, a alteração de preço é aceita nas quatro etapas ativas.

- **Margem e aptidão para apuração:** não são etapas próprias, e sim intervalos de tempo contados de `T0` dentro de `pagamento` (E03-02). Ficam cobertas pela linha `pagamento`.
- **Variação "pela API":** a matriz inclui `POST` com o cabeçalho `HX-Request: true`, como na E02-10.

## Interfaces

- `apps/rodadas/models.py`: `Ciclo` e `CondicaoDoProdutoNoCiclo`.
- `apps/rodadas/ciclos.py`: `registrar_condicoes_do_ciclo` e `ciclo_vigente`.
- Migração com as proteções de só inserção.
- `tests/apoio/`: um auxiliar de teste `simular_inicio_do_fechamento(rodada)` e outro `simular_volta_para_interesse(rodada)`.
  - O primeiro faz o que a E06 fará: trava, chama o serviço e grava `fechamento`.
  - O segundo trava e grava `interesse`.
  - Os dois ficam só nos testes e são substituídos pelas transições reais da E06, que devem passar nos mesmos testes.

## Invariantes

- Nenhum registro de ciclo é alterado ou apagado.
- Os registros de um ciclo refletem exatamente as condições do instante em que a rodada saiu de `interesse`.
- Os números de ciclo de uma rodada são 1, 2, 3, em sequência, sem repetição.

## Casos-limite e concorrência

- **Cenário 73:**
  1. A rodada em `interesse` tem mínimo 150, um produto com incremento 0,5 e múltiplo 3, e estoque 10.
  2. Começa o fechamento: o ciclo 1 registra 150, 0,5, 3 e 10.
  3. A rodada volta para interesse. O administrador muda o mínimo para 200, o múltiplo para 6 e o estoque para 20.
  4. O ciclo 1 continua com 150, 3 e 10.
  5. Um novo fechamento gera o ciclo 2, com 200, 6 e 20.
- **Produto incluído na rodada depois do ciclo 1, durante a volta a interesse:** aparece só no ciclo 2.
- **Rodada sem produtos:** o ciclo é registrado sem condições de produto. Se isso pode ocorrer ou não é regra do início do fechamento (E06), que exige o mínimo atendido.
- **Alteração de condição concorrendo com o início do fechamento:** coberta pelos testes de travas da E03-02, da E03-05 e da E03-06. Aqui, um teste confirma que, com o fechamento iniciado primeiro, o ciclo registra os valores anteriores à alteração recusada.

## Dependências e decisões em aberto

- Depende de E03-02, E03-03, E03-05 e E03-06.
- Sem decisões em aberto.
