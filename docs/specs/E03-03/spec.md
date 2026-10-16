# E03-03 — Produtos: unidade, incremento, múltiplo e preço

Fatia 3 de 8 da milestone **E03 — Fornecedores, catálogo e condições da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Cada produto pertence a um fornecedor e tem:

- unidade de medida;
- incremento permitido, inteiro ou fracionário;
- preço unitário com duas casas;
- múltiplo de compra opcional, que precisa ser divisível exatamente pelo incremento.

Esta fatia entrega:

- o cadastro e a edição de produtos pelo administrador;
- as validações de incremento, múltiplo e quantidade;
- o cálculo do subtotal com um único arredondamento;
- a alteração do múltiplo, que só vale na fase de interesse;
- a alteração do preço, permitida em qualquer etapa.

A alteração do incremento tem validações próprias sobre as parcelas e fica na E03-06.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §4.2 | Produto de um fornecedor. Descrição, preço, medida, disponibilidade, estoque e múltiplo. Medidas: unidade, pacote, peso, volume, caixa. Incremento por produto, inteiro ou fracionário, maior que zero, até três casas. Quantidade múltipla exata do incremento. Múltiplo divisível pelo incremento. Sem ponto flutuante binário. Múltiplo alterável só na fase de interesse. Medida de venda separada do múltiplo do fornecedor. |
| Especificação §4.4 | Congelamento do múltiplo a partir do fechamento. O preço segue a §5.1, fora do congelamento. |
| Especificação §5.1 | Atualizações de preço atingem os interesses durante interesse e fechamento. Os compradores são notificados e os totais recalculados (E05). Os pedidos em pagamento preservam o preço congelado (E08). |
| Especificação §9 | Preço com duas casas. Subtotal = preço × quantidade, arredondado uma vez para duas casas com `ROUND_HALF_UP`. |
| Cenários §16 | 63, 66, 85, 86, 87 (cadastro e alteração do múltiplo), 109, 110, 111 e a parte de preço do 72. |
| Infraestrutura 4.12 | Quantidade e incremento em `NUMERIC(12,3)`, preço em `NUMERIC(12,2)`. Entrada como texto decimal; `float` recusado. `quantidade % incremento == 0`. `múltiplo % incremento == 0` no cadastro e nas alterações. |
| Testes técnicos | T-26, T-38, T-50 e a parte de múltiplo do T-23. |

## Escopo

**Dentro:**

- App `apps.catalogo`, com o modelo `Produto`.
- Funções de validação e cálculo em `apps/catalogo/quantidades.py`.
- Serviços `criar_produto`, `editar_produto` (dados gerais e preço) e `alterar_multiplo`.
- O sinal `preco_alterado`.
- Telas do administrador e a lista de produtos no detalhe do fornecedor.
- Restrições e triggers no banco.
- `ProdutoFactory`.

**Fora:**

- Alteração do incremento (E03-06).
- Estoque por rodada (E03-05).
- Validação de quantidade na adição de interesse (E05), que chama `validar_quantidade` desta fatia. "Inclusive pela API" nos cenários 63, 85 e 109 se cumpre ali, na rota de adição. Aqui a regra é provada no serviço.
- Notificação e recálculo dos interesses depois da mudança de preço (E05), conectados ao sinal `preco_alterado`.
- Snapshot do preço no pedido (E08).

## Regras

**Campos de `Produto`:**

| Campo | Regra | Editável depois |
|---|---|---|
| `fornecedor` | FK `PROTECT`; obrigatório | nunca |
| `nome` | 1 a 150 caracteres, sem espaços nas pontas | sempre |
| `descricao` | opcional, até 2000 caracteres | sempre |
| `unidade` | `unidade`, `pacote`, `caixa`, `kg` ou `litro` | nunca |
| `incremento` | `CampoQuantidade`; regra R-8 abaixo | só pela E03-06 |
| `preco` | `CampoDinheiro`; pelo menos R$ 0,01 | sempre |
| `multiplo` | `CampoQuantidade`, opcional (nulo = sem múltiplo); maior que zero e divisível pelo incremento | só na fase de interesse |
| `disponivel` | booleano, verdadeiro por padrão | sempre |
| `criado_em` | `agora()` | nunca |

**Unidades:** os valores correspondem às medidas da §4.2. `kg` é o peso, `litro` é o volume, e `unidade`, `pacote` e `caixa` são medidas indivisíveis ou de embalagem. Cada uma é exibida como "unidade", "pacote", "caixa", "kg" ou "L". Acrescentar unidades depois é uma mudança técnica sem efeito em regra.

**Decisões técnicas:**

- **Unidade e fornecedor imutáveis:** as quantidades de parcelas, pedidos e snapshots estão na unidade do produto. Trocar a unidade (por exemplo, de kg para unidade) mudaria o significado de quantidades já registradas. Trocar o fornecedor quebraria a rodada e o isolamento entre fornecedores. Para outra medida, o administrador cadastra outro produto. A regra é garantida por trigger, no mesmo estilo da E02-10.
- **Preço de pelo menos R$ 0,01:** a especificação não prevê produto gratuito.
- **Sem exclusão de produto:** o histórico de parcelas e pedidos precisa do produto. Não há forma de tirar um produto do catálogo da rodada; a marcação `disponivel = False` só o identifica como indisponível (D-1 abaixo).

**Incremento (R-8)** — `validar_incremento(entrada) -> Decimal`:

- Converte com `quantidade()` (E01-02), que recusa `float`, `int`, `bool`, mais de três casas e texto fora do formato decimal.
- Exige `> 0`.
- Recusa levanta `IncrementoInvalido`, com mensagem.
- Válidos: `1`, `2`, `0,25`, `0,5`, `0,001`. Inválidos: `0`, `-1`, `0,0001`.

**Múltiplo (R-2)** — `validar_multiplo(entrada, incremento) -> Decimal | None`:

- Vazio resulta em `None`.
- Exige `> 0` e `eh_multiplo(multiplo, incremento)` (E01-02).
- Recusa levanta `MultiploInvalido`, com mensagem.
- Válidos: múltiplo 1 com incremento 0,25; 12 com 2.
- Inválidos: 1 com 0,3; 5 com 2; 0,9 com 0,25.

**Quantidade** — `validar_quantidade(produto, entrada) -> Decimal`:

- Converte com `quantidade()`.
- Exige `> 0` e `eh_multiplo(quantidade, produto.incremento)`.
- Recusa levanta `QuantidadeInvalida`, com mensagem.
- É o ponto único de validação de quantidade contra o incremento. A E05 e as etapas seguintes o usam.

**Subtotal** — `calcular_subtotal(preco, quantidade) -> Decimal`:

- Resulta em `arredondar_centavos(preco * quantidade)` (E01-02), com um único arredondamento `ROUND_HALF_UP`.
- Aceita só `Decimal`.
- Exemplos:
  - `12,00 × 1,5 = 18,00`;
  - `12,99 × 0,35 = 4,5465`, arredondado para `4,55` (455 centavos);
  - `7,99 × 0,25 = 1,9975`, arredondado para `2,00`.

**Banco:**

- `CHECK incremento > 0`.
- `CHECK preco >= 0.01`.
- `CHECK multiplo IS NULL OR (multiplo > 0 AND multiplo % incremento = 0)`. O `%` de `numeric` no Postgres é exato.
- Trigger que recusa `UPDATE` de `fornecedor_id` e `unidade`.
- Trigger que recusa `DELETE`.

**Cadastro** (`criar_produto(autor, fornecedor, *, nome, descricao, unidade, incremento, preco, multiplo, disponivel=True)`):

- Exige o administrador.
- Valida tudo acima e grava, com a auditoria `produto.criar` e `{"produto": <id>, "fornecedor": <id>}`.
- **Permitido em qualquer etapa da rodada do fornecedor**, porque criar um produto não altera condições da rodada: um produto só participa de uma rodada quando é incluído no estoque dela, o que só acontece na fase de interesse (E03-05). Um produto criado com a rodada em `fechamento` fica fora dessa rodada.

**Edição geral** (`editar_produto(autor, produto, *, nome, descricao, preco, disponivel)`):

- Permitida em qualquer etapa.
- Em `transaction.atomic()`, trava a linha do produto.
- Grava só os campos recebidos que mudaram (`update_fields`).
- Auditoria `produto.editar` com `{"produto": <id>, "campos": [...]}`, sem os valores.
- **Mudança de preço:**
  - grava também a auditoria `produto.alterar_preco`, com `anterior` e `novo` em texto decimal;
  - envia `preco_alterado(produto=..., anterior=..., novo=...)` dentro da transação, e um receptor que falhe desfaz a edição.
  - A E05 conecta a esse sinal o recálculo e a notificação da §5.1. Os pedidos congelados nunca leem o preço do catálogo (E08).
- **Disponibilidade:** `disponivel` é registrado e exibido. Conforme a decisão D-1, o produto indisponível continua no catálogo, pode ser adicionado como interesse e os interesses existentes permanecem; a descrição exibida ao comprador mostra explicitamente que ele está indisponível (E03-08 e, no carrinho, E05). A marcação não altera nenhum interesse, reserva ou condição da rodada.

**Alteração do múltiplo** (`alterar_multiplo(autor, produto, novo) -> Produto`):

1. Exige o administrador.
2. Em `transaction.atomic()`, chama `travar_condicoes(produto.fornecedor)` (E03-02) e depois trava a linha do produto, seguindo a ordem de travas.
3. Valida com `validar_multiplo(novo, produto.incremento)`. Vazio remove o múltiplo.
4. Grava só `multiplo`, com a auditoria `produto.alterar_multiplo` e `anterior` e `novo` (texto decimal, ou `null`).
5. Valor igual ao atual: não grava nem audita.

**Telas** (`somente_administrador`, com política declarada):

| Rota | Conteúdo |
|---|---|
| Detalhe do fornecedor (E03-01) | lista de produtos: nome, unidade, incremento, preço, múltiplo e disponibilidade, com link para cada produto |
| `/administracao/fornecedores/<id>/produtos/novo/` | cadastro |
| `/administracao/produtos/<id>/` | edição geral (nome, descrição, preço e disponibilidade); unidade, fornecedor e incremento só para leitura |
| `/administracao/produtos/<id>/multiplo/` | alteração do múltiplo; 409 com a mensagem única de `CondicoesCongeladas` fora da fase de interesse, como na E03-02 |

- Campos `fornecedor`, `unidade` ou `incremento` enviados por `POST` na edição geral são ignorados.
- A entrada decimal segue a regra da E03-01: vírgula ou ponto, sem separador de milhar.
- Quantidades e preços são exibidos com vírgula, sem zeros à direita nas quantidades: `0,25`, `1`, `1,5`.

## Interfaces

- `apps/catalogo/models.py`: `Unidade` e `Produto`.
- `apps/catalogo/quantidades.py`:
  - `validar_incremento`, `validar_multiplo`, `validar_quantidade` e `calcular_subtotal`;
  - as exceções `IncrementoInvalido`, `MultiploInvalido` e `QuantidadeInvalida`, todas subclasses de uma `QuantidadeRecusada`;
  - um formatador de quantidade para exibição.
- `apps/catalogo/servicos.py`: `criar_produto`, `editar_produto` e `alterar_multiplo`.
- `apps/catalogo/sinais.py`: `preco_alterado`.
- Migrações com `CHECK`s e triggers.
- Views, formulários e rotas acima.
- `tests/fabricas.py`: `ProdutoFactory`.

## Invariantes

- Todo produto gravado tem incremento maior que zero, com até três casas.
- Todo múltiplo gravado é maior que zero e divisível exatamente pelo incremento.
- O preço tem duas casas e é de pelo menos R$ 0,01.
- `fornecedor` e `unidade` nunca mudam.
- Nenhum `float` em quantidade, incremento, múltiplo ou preço.

## Casos-limite e concorrência

- **Tabela da §4.2 e cenário 109:**

  | Produto | Incremento | Aceito | Recusado |
  |---|---|---|---|
  | Ovos (unidade) | 1 | 12 | 12,5 |
  | Maçãs (unidade) | 2 | 4 | 3 |
  | Banana (kg) | 0,25 | 1,25 | — |
  | Leite (litro) | 0,5 | 2,5 | — |
  | Caixa | 1 | 3 | 1,5 |

- **Cenários 63 e 85:**
  - kg a R$ 12,00 com incremento 0,5: 1,5 aceito (subtotal R$ 18,00); 1,2 recusado.
  - L com incremento 0,5: 1,5 aceito; 1,2 recusado.
  - unidade com incremento 1: 2 aceito; 2,5 recusado.
  - kg com incremento 0,25: 0,75 aceito.
- **Quantidade zero ou negativa:** recusada.
- **Quantidade com quatro casas** (`0,2500` é aceito porque o excedente é zero, conforme a E01-02; `0,2501` é recusado).
- **`float` em qualquer função** (T-50): recusado.
- **Preço alterado durante `fechamento` e `pagamento`:** aceito. Cenário 72, parte de preço. O efeito sobre os pedidos é das etapas E05 e E08.
- **Múltiplo alterado em `fechamento`:** recusado (cenário 87, T-23).
- **Duas edições de preço simultâneas:** serializadas pela trava do produto. Cada auditoria registra o `anterior` correto.

## Correção E03-R01 — revisão da especificação em 2026-10-16

A regra comum está na seção de mesmo título da E03-01.

### Regra

- **Preço** (`criar_produto` e `editar_produto`): regra de capacidade de dinheiro, depois do preço mínimo de R$ 0,01. Na edição recusada:
  - o preço anterior é mantido;
  - os outros campos enviados também não são gravados, porque a edição é uma única operação;
  - não há auditoria e o sinal `preco_alterado` não é enviado.
- **Incremento** (`validar_incremento`): regra de capacidade de quantidade, depois de "maior que zero". A recusa levanta `IncrementoInvalido` com a mensagem de capacidade.
- **Múltiplo** (`validar_multiplo`): regra de capacidade de quantidade, depois de "maior que zero" e antes da divisibilidade pelo incremento. A recusa levanta `MultiploInvalido` com a mensagem de capacidade.
- **Quantidade** (`validar_quantidade`): regra de capacidade de quantidade, depois de "maior que zero" e antes da divisibilidade. A recusa levanta `QuantidadeInvalida` com a mensagem de capacidade. Isso protege a adição de interesse da E05, que grava a quantidade em `CampoQuantidade`.
- As exceções continuam as mesmas, então as views que já mostram `IncrementoInvalido` e `MultiploInvalido` no formulário mostram a nova mensagem sem mudança de fluxo.
- `alterar_multiplo` usa `validar_multiplo`, então recebe a regra. Na recusa, o múltiplo anterior é mantido, sem auditoria.
- `CampoDecimalDigitado` (`apps/catalogo/forms.py`) pode continuar só convertendo o texto. Se ele também verificar a capacidade, deve usar as primitivas e a mensagem da E03-01, nunca outra.

### Testes obrigatórios

- Critérios A-24 a A-28, com Red observado antes do código.

## Dependências e decisões em aberto

- Depende de E03-01 e E03-02.
- **D-1 (resolvida pelo responsável em 2026-10-16):** "O produto indisponível pode ser adicionado e permanecer como interesse, mas fica explícito na sua descrição que está indisponível." A marcação não bloqueia adições, não remove interesses e não muda reservas; só aparece ao comprador junto à descrição do produto.
