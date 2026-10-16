# E03-06 — Alteração do incremento

Fatia 6 de 8 da milestone **E03 — Fornecedores, catálogo e condições da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O administrador pode alterar o incremento de um produto só na fase de interesse, e só se, ao mesmo tempo:

- o novo valor é válido;
- todas as quantidades reservadas e pendentes do produto continuam múltiplas dele;
- o múltiplo continua divisível por ele.

Se qualquer condição falhar, a alteração é rejeitada inteira, sem escrita.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §4.2 | Alteração do incremento só na fase de interesse, com as três condições acima e rejeição integral. |
| Especificação §4.4 | Incremento congelado a partir do fechamento, inclusive para o administrador e pela API. |
| Cenários §16 | 105, 106 e 107. O 108 fica para a E05 (ver Fora). |
| Infraestrutura 4.12 | `alterar_incremento(produto, novo)` numa transação com trava do produto e das parcelas, com as quatro recusas na ordem. A adição de interesse também trava o produto. |
| Testes técnicos | T-48. O T-49 fica para a E05. |

## Escopo

**Dentro:**

- Serviço `alterar_incremento` em `apps/catalogo/servicos.py`.
- Rota `/administracao/produtos/<id>/incremento/` (`GET` e `POST`, `somente_administrador`).

**Fora:**

- **Cenário 108 e T-49** (alteração concorrente com adição de interesse): a adição só existe na E05, que precisa travar a linha do produto antes de validar a quantidade com `validar_quantidade`. Ficam registrados como "Herdado da E03" na milestone E05.

## Regras

`alterar_incremento(autor, produto, novo) -> Produto`:

1. Exige o administrador; caso contrário, `PermissionDenied`.
2. Em `transaction.atomic()`, chama `travar_condicoes(produto.fornecedor)` (E03-02). Fora da fase de interesse, levanta `CondicoesCongeladas` (cenário 107).
3. Trava a linha do produto e relê o produto.
4. Valida `novo` com `validar_incremento` (E03-03, R-8). Se for inválido, levanta `IncrementoInvalido`.
5. Trava as parcelas do produto em ordem de sequência e lê `quantidades_em_uso(produto)` (E03-04). Se alguma não for múltipla de `novo` (`eh_multiplo`), levanta `IncrementoIncompativel` com o código `quantidade`. A leitura inclui as pendentes da fila do fornecedor.
6. Se o produto tem múltiplo e `multiplo % novo != 0`, levanta `IncrementoIncompativel` com o código `multiplo`.
7. Grava só `incremento`, com a auditoria `produto.alterar_incremento` e `{"produto": <id>, "anterior": "<valor>", "novo": "<valor>"}`.
8. Se o valor for igual ao atual, não grava nem audita.

Qualquer recusa reverte a transação inteira: nenhuma parcela, produto ou auditoria é alterado.

**Mensagens:**

- "O novo incremento não é compatível com quantidades já registradas deste produto."
- "O múltiplo do produto não é divisível pelo novo incremento."

A mensagem não identifica compradores.

**Tela:**

- Mostra o incremento atual e o formulário, só na fase de interesse.
- Fora dela, mostra a mensagem única de `CondicoesCongeladas` com status 200 no `GET`; o `POST` responde 409.
- `IncrementoInvalido` e `IncrementoIncompativel` aparecem no formulário, com status 200.

## Interfaces

- `apps/catalogo/servicos.py`: `alterar_incremento` e a exceção `IncrementoIncompativel` (com o atributo `codigo`).
- View, formulário e rota, com política declarada (E02-10).

## Invariantes

- Depois de qualquer alteração aceita, toda quantidade reservada ou pendente do produto é múltipla do incremento vigente, e o múltiplo é divisível por ele.
- O incremento nunca muda fora da fase de interesse da rodada ativa.

## Casos-limite e concorrência

- **Cenário 105:** incremento 0,5, reservadas 1,0 e 1,5, pendente 2,0 e múltiplo 3. A mudança para 0,25 é aceita, e nenhuma parcela muda.
- **Cenário 106:**
  - No mesmo produto, a mudança para 1 é recusada com o código `quantidade`, porque 1,5 deixa de ser múltiplo.
  - A mudança para 2 também é recusada. Pela ordem dos passos (infraestrutura 4.12), o código é `quantidade`, porque 1,0 e 1,5 não são múltiplos de 2. O cenário 106 só exige a recusa sem nenhuma alteração, e isso se cumpre.
  - O código `multiplo` é provado à parte: com só a pendente de 2,0, a mudança para 2 passa pelas quantidades e é recusada porque 3 não é divisível por 2.
  - Ajuste E03-R02 (2026-10-16): a versão anterior desta linha dava o código `multiplo` para o cenário completo, o que contrariava a ordem dos passos. A ordem não muda.
- **Parcelas removidas não contam:** uma parcela `removida` com quantidades zero não impede a mudança.
- **Mudança de etapa concorrente:** recusada se a mudança confirmar primeiro. Teste com `pg_stat_activity`, como na E03-02.
- **Duas alterações simultâneas:** são serializadas. Cada auditoria registra o `anterior` correto.
- **Parcela criada por outra conexão antes da trava:** a thread de teste trava produto e parcelas e insere uma parcela de 1,5. A mudança para 1, que espera a trava, é recusada depois.

## Correção E03-R01 — revisão da especificação em 2026-10-16

A regra comum está na seção de mesmo título da E03-01.

### Regra

- `alterar_incremento` usa `validar_incremento` no passo 4, então recebe a regra de capacidade de quantidade da E03-03.
- A recusa levanta `IncrementoInvalido` com "O valor máximo aceito é 999999999,999.", antes da leitura das parcelas e da comparação com o múltiplo. Um valor acima da capacidade nunca gera `IncrementoIncompativel`.
- Na recusa, o incremento anterior é mantido e não há auditoria. A tela responde 200 com o erro no formulário.

### Testes obrigatórios

- Critério A-15, com Red observado antes do código.

## Dependências e decisões em aberto

- Depende de E03-02, E03-03 e E03-04.
- Sem decisões em aberto.
