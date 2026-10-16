# E03-01 — Cadastro e gestão de fornecedores

Fatia 1 de 8 da milestone **E03 — Fornecedores, catálogo e condições da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

A E02-01 criou o `Fornecedor` só com `nome`, para que o convite de fornecedor tivesse a que se vincular. Esta fatia acrescenta os dados funcionais do fornecedor e a tela do administrador para cadastrar, consultar e editar fornecedores.

O mínimo monetário é informado no cadastro. A alteração dele depois do cadastro depende da fase da rodada e entra na E03-02.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §1 | Cada fornecedor reúne sua rodada, sujeita a mínimo monetário. O administrador cadastra fornecedores. |
| Especificação §2 | Só o administrador cadastra. O fornecedor não altera o próprio cadastro. |
| Especificação §4.1 | Nome, e-mail para o pedido formal, mínimo monetário de produtos, prazo padrão de entrega, informações de frete e vínculo com a conta de consulta, quando existir. O prazo padrão é editável. O frete pode constar do cadastro, e o valor efetivo é informado na abertura do pagamento. |
| Especificação §6.1 | O mínimo é sempre monetário e considera só produtos. |
| Especificação §13 | Administrador: gestão de fornecedores. |
| Infraestrutura 4.12 | Dinheiro em `NUMERIC(12,2)`, entrada como texto decimal, sem ponto flutuante. |

## Escopo

**Dentro:**

- Campos novos em `apps.fornecedores.Fornecedor`.
- Serviços `criar_fornecedor` e `editar_fornecedor`, com auditoria.
- Telas do administrador: lista, cadastro, detalhe e edição.
- Exibição das contas de fornecedor vinculadas, no detalhe.
- Atualização de `FornecedorFactory`.

**Fora:**

- Alteração do mínimo depois do cadastro (E03-02).
- Rodadas (E03-02), produtos (E03-03) e estoque (E03-05).
- Consulta do fornecedor aos próprios dados (E13).
- Valor efetivo do frete (E08).
- Exclusão de fornecedor: não está prevista, e o histórico precisa ser preservado.

## Regras

**Campos:**

| Campo | Regra |
|---|---|
| `nome` | obrigatório; espaços das pontas removidos; de 1 a 150 caracteres |
| `email_pedido` | obrigatório; passa por `normalizar_email` (E02-01), que recusa endereço inválido |
| `minimo` | obrigatório; `CampoDinheiro` (E01-02); pelo menos R$ 0,01 |
| `prazo_entrega_dias` | obrigatório; inteiro de 1 a 365 |
| `informacoes_frete` | opcional; texto de até 1000 caracteres; vazio grava texto vazio |
| `criado_em` | gravado pelo servidor com `agora()` (E01-03) |

**Decisões técnicas:**

- **Mínimo de pelo menos R$ 0,01:** todo fornecedor está sujeito a mínimo monetário (especificação §1, §4.1, §6.1). Um mínimo zero não corresponde a nenhuma regra.
- **Prazo em dias inteiros:** a especificação fala em "prazo padrão de entrega" sem unidade. Dias inteiros bastam para exibir a previsão. O teto de 365 só protege contra erro de digitação.
- **E-mail normalizado:** o endereço do pedido formal não identifica conta, mas passar por `normalizar_email` mantém um único ponto de tratamento de e-mails, exigido pela varredura do T-37 (E02-10).

**Entrada de valores:** os formulários aceitam vírgula ou ponto como separador decimal, sem separador de milhar. Exemplos: `150,00` e `150.00`. A vírgula é trocada por ponto antes de `dinheiro()` (E01-02). Qualquer outro formato é recusado com mensagem no campo.

**Edição:**

- `nome`, `email_pedido`, `prazo_entrega_dias` e `informacoes_frete` são editáveis em qualquer momento. Não fazem parte das condições congeladas da especificação §4.4.
- `minimo` não aparece no formulário de edição desta fatia. Um `minimo` enviado por `POST` na edição é ignorado (teste A-9). A alteração vem na E03-02.

**Auditoria:**

- `fornecedor.criar`, com alterações `{"fornecedor": <id>}`.
- `fornecedor.editar`, com alterações `{"fornecedor": <id>, "campos": [<nomes dos campos alterados>]}`.
- O autor é o administrador da requisição.
- Os valores dos campos não vão para a auditoria; o e-mail é dado de contato.
- Edição sem nenhuma mudança não grava auditoria.

**Telas** (todas com `somente_administrador`, E02-03):

| Rota | Conteúdo |
|---|---|
| `/administracao/fornecedores/` | lista ordenada por nome: nome, mínimo e prazo |
| `/administracao/fornecedores/novo/` | cadastro (`GET` e `POST`) |
| `/administracao/fornecedores/<id>/` | detalhe: campos, contas de fornecedor vinculadas (nome, e-mail e situação) e, a partir da E03-02, a rodada ativa |
| `/administracao/fornecedores/<id>/editar/` | edição (`GET` e `POST`) |

- Id inexistente devolve 404.
- Cadastro e edição válidos redirecionam para o detalhe.

**Migração:** os campos novos são obrigatórios. Não há dados de produção (fase 1). A migração pode usar valores provisórios com `preserve_default=False`. O `README` registra que bancos locais com fornecedores de teste devem ser recriados com `docker compose down -v`, como na E02-01.

## Interfaces

- `apps/fornecedores/models.py`: campos novos e `CHECK`s.
- `apps/fornecedores/servicos.py`: `criar_fornecedor(autor, *, nome, email_pedido, minimo, prazo_entrega_dias, informacoes_frete="") -> Fornecedor` e `editar_fornecedor(autor, fornecedor, **campos) -> Fornecedor`. Os dois levantam `PermissionDenied` se o autor não for o administrador, e `ValidationError` com mensagens por campo.
- `apps/fornecedores/forms.py`, `apps/fornecedores/views.py` e as rotas acima, com política declarada (E02-10).
- `apps/nucleo/valores.py`: uma função `ler_decimal_digitado(texto, casas)`, ou outra equivalente, que aplica a regra de entrada acima. Ela é reaproveitada pelas fatias seguintes.

## Invariantes

- `CHECK minimo >= 0.01` e `CHECK prazo_entrega_dias BETWEEN 1 AND 365` no banco.
- Só o administrador cria e edita fornecedores, também em chamada direta aos serviços.
- Nenhum `float` em mínimo ou em qualquer valor desta fatia.

## Casos-limite e concorrência

- **Mínimo:** `0,01` aceito. `0`, `-1`, `0,001` (três casas), `abc` e `1.000,00` (separador de milhar) recusados.
- **Prazo:** `1` e `365` aceitos; `0`, `366` e `2,5` recusados.
- **E-mail:** `  Pedidos@Fornecedor.COM ` é gravado `pedidos@fornecedor.com`.
- **Sem concorrência crítica:** a edição dos campos desta fatia não interage com estoque, rodada ou dinheiro. O mínimo, que interage, fica na E03-02, com as travas.

## Correção E03-R01 — revisão da especificação em 2026-10-16

Esta seção define a regra comum de capacidade decimal. As seções de mesmo título nas E03-02, E03-03, E03-05 e E03-06 aplicam a regra aos seus campos.

### Diagnóstico

- As conversões (`ler_decimal_digitado`, `dinheiro()`, `quantidade()`) verificam formato, casas e sinal, mas não o número de dígitos que a coluna comporta.
- `objects.create()` e `save()` não executam os validadores de campo do Django. Um valor com dígitos inteiros demais chega ao Postgres, que recusa com `numeric field overflow` (`DataError`), e a requisição termina em HTTP 500.
- O revisor reproduziu isso em oito caminhos: cadastro de fornecedor, alteração do mínimo, edição de preço, cadastro de produto, alteração de incremento, alteração de múltiplo, inclusão no estoque e alteração do estoque.
- Minha falha na especificação: as faixas `NUMERIC(12,2)` e `NUMERIC(12,3)` (infraestrutura 4.12, E01-02) estavam citadas, mas nenhuma fatia tratou o maior valor gravável como caso-limite.

### Regra

**Capacidade das colunas** (consequência técnica das faixas aprovadas, não um teto comercial):

| Tipo | Coluna | Maior valor gravável |
|---|---|---|
| Dinheiro | `CampoDinheiro`, `NUMERIC(12,2)` | `9999999999.99` (dez dígitos inteiros) |
| Quantidade | `CampoQuantidade`, `NUMERIC(12,3)` | `999999999.999` (nove dígitos inteiros) |

**Primitivas novas em `apps/nucleo/valores.py`** (as existentes não mudam):

- Constantes `MAIOR_DINHEIRO` e `MAIOR_QUANTIDADE`, calculadas a partir de `max_digits` e `decimal_places` de `CampoDinheiro` e `CampoQuantidade`, para que as constantes e as colunas não possam divergir.
- `cabe_em_dinheiro(valor) -> bool` e `cabe_em_quantidade(valor) -> bool`:
  - aceitam só `Decimal` finito; qualquer outro tipo levanta `ValorInvalido`;
  - devolvem `True` quando `valor <= MAIOR_*`;
  - não arredondam, não truncam e não alteram o valor.

**Mensagens de capacidade** (no campo do formulário, ou no formulário de estoque):

- Dinheiro: "O valor máximo aceito é R$ 9.999.999.999,99."
- Quantidade: "O valor máximo aceito é 999999999,999."

**Onde a regra vale:** no serviço, no mesmo ponto em que o valor já é validado, para que a chamada direta ao serviço também seja protegida. A ordem é:

1. formato e casas (regra existente);
2. sinal e valor mínimo (regra existente);
3. capacidade (esta regra);
4. compatibilidade com outros dados, como múltiplo, incremento ou reservado (regras existentes).

**Efeito da recusa:**

- nada é gravado e o valor anterior é mantido;
- nenhuma auditoria é registrada e nenhum sinal é enviado;
- a rota responde 200, com o erro no campo e o valor digitado de volta no formulário. Nas rotas de condição da rodada (mínimo, múltiplo, incremento e estoque), isso vale só quando a rodada está em `interesse`. Fora dela, a fase prevalece e a resposta é 409 (correção E03-R03 da E03-02).

**Valores muito grandes:** um texto com mais dígitos do que a precisão do contexto decimal (por exemplo, 30 dígitos) já é recusado pela conversão com a mensagem de formato. Isso é aceito: a exigência é ter um erro de campo, nunca um 500.

**Nesta fatia:** o `minimo` de `criar_fornecedor` passa pela regra de dinheiro. A alteração do mínimo usa a mesma limpeza e está na correção da E03-02.

### Testes obrigatórios

- O script de probes do revisor (`docs/specs/E03-08/review.md`, seção "Script reproduzível dos probes adicionais") entra literal na suíte, em `tests/tecnicos/test_capacidade_decimal.py`, com o marcador `tecnico`. Os 16 casos devem passar: os 8 que excedem a capacidade respondem 200, e os 8 controles no limite respondem 302.
- Testes unitários das primitivas e testes de serviço com `Decimal`, conforme os critérios A-18 a A-20.
- Todos com Red observado antes do código.

### O que não fazer

- Não capturar `DataError` (nem `DatabaseError`) para transformá-lo em erro de validação. A recusa precisa acontecer antes da escrita.
- Não arredondar, truncar nem limitar silenciosamente o valor digitado.
- Não alterar `dinheiro()`, `quantidade()`, `ler_decimal_digitado()`, `arredondar_centavos()`, `eh_multiplo()` nem `calcular_subtotal()`. Essas funções também são usadas em cálculos intermediários que não são gravados nessas colunas.
- Não validar só no formulário: o serviço é a autoridade (AGENTS.md §6).
- Não criar um teto comercial diferente da capacidade da coluna.

## Dependências e decisões em aberto

- Depende de E01-02 (valores), E01-04 (auditoria), E02-01 (`normalizar_email`, `Fornecedor`) e E02-03 (área administrativa).
- Sem decisões em aberto.
