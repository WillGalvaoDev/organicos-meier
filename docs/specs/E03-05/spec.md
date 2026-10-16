# E03-05 — Estoque por rodada

Fatia 5 de 8 da milestone **E03 — Fornecedores, catálogo e condições da rodada**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O estoque é definido por rodada, sem reaproveitamento automático da anterior. Pode ser limitado ou não. Só é alterável na fase de interesse e nunca pode ficar abaixo da quantidade já reservada.

Esta fatia entrega:

- a inclusão de produtos na rodada ativa, com o estoque de cada um;
- a alteração desse estoque;
- o sinal que a E05 usa para atender os pendentes quando o estoque aumenta.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §4.2 | Estoque limitado quando aplicável. |
| Especificação §4.3 | Estoque definido por rodada; não presumir reposição nem reaproveitamento automático da rodada anterior. |
| Especificação §4.4 | Estoque só alterável na fase de interesse. Não pode ficar abaixo da quantidade já reservada. Congelado a partir do fechamento. |
| Especificação §5 | Não permitir reservas acima do estoque limitado (E05). |
| Especificação §5.2 | Os pendentes são atendidos primeiro quando o estoque é aumentado (E05). |
| Cenários §16 | 71 (estoque) e 72 (estoque). |
| Infraestrutura 4.10 | Redução abaixo do total reservado recusada sob trava. `alocar_pendentes` roda quando o estoque é aumentado. |
| Infraestrutura 5 | Trava de linha no estoque por produto em reserva, restauração e alteração de estoque. |
| Testes técnicos | T-23 (estoque). |

## Escopo

**Dentro:**

- Modelo `EstoqueDaRodada` em `apps.rodadas`.
- Serviços `incluir_produto_na_rodada` e `alterar_estoque`.
- Sinal `estoque_alterado`.
- Função `estoque_livre(estoque)`.
- Tela de estoque da rodada.

**Fora:**

- Reserva de estoque pelos interesses e `alocar_pendentes` (E05). A E05 usa a trava da linha do estoque definida aqui.
- Retirada de produto da rodada: não está prevista. O administrador pode reduzir o estoque até o reservado. A marcação de indisponível (E03-03) não tira o produto da rodada.

## Regras

**Modelo** (`EstoqueDaRodada`):

| Campo | Regra |
|---|---|
| `rodada` | FK `PROTECT` |
| `produto` | FK `PROTECT` |
| `limite` | `CampoQuantidade`, nulo para "sem limite"; maior ou igual a zero |
| `incluido_em` | `agora()` |

- `UNIQUE (rodada, produto)`.
- `CHECK limite IS NULL OR limite >= 0`.
- Uma trigger recusa a inserção ou a atualização quando o fornecedor do produto é diferente do fornecedor da rodada. Isso é o isolamento entre fornecedores, especificação §4.3.
- Uma trigger recusa `UPDATE` de `rodada_id` e `produto_id`, e recusa `DELETE`.

**Participação na rodada:**

- Um produto participa da rodada se e somente se tem um `EstoqueDaRodada` nela.
- Uma nova rodada começa sem nenhum produto. Nada é copiado da rodada anterior (especificação §4.3).

**Limite e incremento:** o limite não precisa ser múltiplo do incremento. A especificação não exige isso. A E05 reserva sempre em múltiplos do incremento (infraestrutura 4.10), e o resto, se houver, fica sem uso.

**Estoque livre** (`estoque_livre(estoque) -> Decimal | None`):

- `None` quando `limite` é nulo, isto é, sem limite.
- Senão, `limite − total_reservado(produto)` (E03-04), com piso 0.
- O piso só protege a exibição. A invariante "reservado ≤ limite" é mantida pelas regras abaixo e pela E05.

**Inclusão** (`incluir_produto_na_rodada(autor, rodada, produto, limite) -> EstoqueDaRodada`):

1. Exige o administrador.
2. Em `transaction.atomic()`, chama `travar_condicoes(produto.fornecedor)` (E03-02). Exige que a rodada travada seja a rodada recebida; caso contrário, `CondicoesCongeladas` (`fora_de_interesse`).
3. Trava a linha do produto.
4. Produto de outro fornecedor: `ValidationError`.
5. Produto já incluído: `ValidationError` com "Este produto já está na rodada.".
6. Valida `limite` com `quantidade()` (E01-02): vazio significa sem limite, e valor negativo é recusado.
7. Cria o registro e grava a auditoria `estoque.incluir` com `{"rodada": <id>, "produto": <id>, "limite": "<valor>" | null}`.
8. Envia `estoque_alterado(estoque=..., anterior=Decimal("0"), novo=<limite ou None>)` dentro da transação.
9. **Inclusão de produto indisponível:** permitida. A disponibilidade não é condição da rodada.

**Alteração** (`alterar_estoque(autor, estoque, novo_limite) -> EstoqueDaRodada`):

1. Exige o administrador.
2. Em `transaction.atomic()`, chama `travar_condicoes(estoque.produto.fornecedor)`. Exige que a rodada travada seja `estoque.rodada`; caso contrário, levanta `CondicoesCongeladas`, porque o estoque de uma rodada antiga nunca é alterado.
3. Trava o produto, depois a linha do estoque (relida sob trava) e depois as parcelas do produto, em ordem de sequência (E03-04). Segue a ordem global de travas.
4. Se `novo_limite` não é nulo e é menor que `total_reservado(produto)`, levanta `EstoqueAbaixoDoReservado` com "O estoque não pode ficar abaixo da quantidade já reservada (<reservado formatado>).". Nada é gravado.
5. Grava só `limite`, com a auditoria `estoque.alterar` e `anterior` e `novo`.
6. Envia `estoque_alterado(estoque=..., anterior=..., novo=...)` dentro da transação, para que a E05 atenda os pendentes no aumento. Um receptor que falhe desfaz a alteração.
7. Valor igual ao atual: não grava, não audita e não envia sinal.

**Aumento e redução:**

- **Aumento:** de sem limite para limitado é uma redução. De limitado para sem limite é um aumento.
- **Redução até o reservado:** reduzir exatamente até o total reservado é aceito.
- **Quem decide:** os receptores do sinal decidem o que fazer com base em `anterior` e `novo`. O sinal é enviado em toda alteração gravada.

**Tela** (`/administracao/rodadas/<id>/estoque/`, `somente_administrador`):

- Lista os produtos do fornecedor, separados em "na rodada" e "fora da rodada". Para cada produto na rodada, mostra limite (ou "sem limite"), reservado e livre.
- **Fase de interesse:** oferece incluir e alterar, com `POST` em `/administracao/rodadas/<id>/estoque/incluir/` e `/administracao/estoque/<id>/alterar/`.
- **Fora da fase de interesse e em rodada não ativa:** a tela é só de leitura, e os `POST` respondem 409 com a mensagem única de `CondicoesCongeladas`.
- **Recusa de redução:** `EstoqueAbaixoDoReservado` mostra a mensagem no formulário, com status 200. O formulário mantém o valor digitado (correção E03-R04).
- **Detalhe do fornecedor (E03-01):** passa a ter link para o estoque da rodada ativa.

## Interfaces

- `apps/rodadas/models.py`: `EstoqueDaRodada`.
- `apps/rodadas/estoque.py`:
  - `incluir_produto_na_rodada`, `alterar_estoque` e `estoque_livre`;
  - a exceção `EstoqueAbaixoDoReservado`;
  - uma função `travar_estoque(rodada, produto)`, que a E05 usa para reservar na ordem de travas.
- `apps/rodadas/sinais.py`: `estoque_alterado`.
- Migração, views, formulários e rotas.
- `tests/fabricas.py`: `EstoqueDaRodadaFactory`.

## Invariantes

- Nenhum produto de um fornecedor entra na rodada de outro.
- O limite nunca é gravado abaixo do total reservado por uma alteração desta fatia.
- O estoque só muda na fase de interesse da rodada ativa.
- Nenhum estoque é copiado entre rodadas.

## Casos-limite e concorrência

- **Cenário 71:**
  - limite 10 com 6 reservados: reduzir para 6 é aceito; para 5 é recusado.
  - Com limite nulo e 6 reservados, mudar para 4 é recusado.
- **Cenário 72 e T-23:** em `fechamento`, `fechamento_encerrado`, `pagamento` e `aguardando_fornecedor`, incluir e alterar são recusados.
- **Rodada antiga:** uma rodada `disponivel_para_retirada`, com o fornecedor já em outra rodada em interesse, tem o estoque recusado.
- **Alteração concorrendo com uma mudança de etapa** que respeita o contrato da E03-02: recusada se a mudança confirmar primeiro. Teste com `pg_stat_activity`, como na E03-02.
- **Alteração concorrendo com uma reserva:** a reserva é da E05, que trava a mesma linha do estoque. Nesta fatia, o teste simula a reserva com uma thread que trava fornecedor, rodada, produto e estoque, nessa ordem, e aumenta a quantidade reservada de uma parcela. Com reserva concluída antes, a redução abaixo do novo total é recusada. Com a redução antes, a reserva vê o novo limite.
- **Duas inclusões simultâneas do mesmo produto:** uma inclusão; a outra é recusada. A trava do produto e o `UNIQUE` garantem isso.

## Correção E03-R01 — revisão da especificação em 2026-10-16

A regra comum está na seção de mesmo título da E03-01.

### Regra

- **Inclusão e alteração** (`incluir_produto_na_rodada` e `alterar_estoque`): o `limite` passa pela regra de capacidade de quantidade, depois de "não negativo". Vazio continua significando "sem limite".
- Na recusa, nada é gravado:
  - na inclusão, nenhum `EstoqueDaRodada` é criado;
  - na alteração, o limite anterior é mantido;
  - não há auditoria `estoque.incluir` nem `estoque.alterar`, e o sinal `estoque_alterado` não é enviado.
- A tela de estoque responde 200 e mostra a mensagem de capacidade no formulário correspondente.
- A recusa por capacidade vem antes da comparação com o total reservado. Um valor acima da capacidade nunca chega a `EstoqueAbaixoDoReservado`.

### Testes obrigatórios

- Critérios A-20 e A-21, com Red observado antes do código.

## Correção E03-R03 — revisão da especificação em 2026-10-16

A regra geral está na seção de mesmo título da E03-02.

### Regra

**Serviços:**

- `incluir_produto_na_rodada` passa a validar o `limite` só depois de:
  1. exigir o administrador;
  2. conferir que o produto é do fornecedor da rodada (`ValidationError`, como hoje: é identidade, não valor);
  3. `travar_condicoes` e conferir que a rodada travada é a rodada recebida;
  4. travar o produto.

  Os passos 4 a 6 da seção Regras já previam essa ordem; o código a inverteu.
- `alterar_estoque` passa a validar `novo_limite` só depois de `travar_condicoes`, da conferência da rodada e de `travar_estoque`. Em seguida vêm a comparação com o valor atual (o no-op) e a comparação com o reservado.
- Assim, um limite mal formado, negativo ou acima da capacidade numa fase congelada, ou numa rodada antiga, levanta `CondicoesCongeladas`, nunca `ValidationError`.

**Views:**

- `estoque_incluir` e `estoque_alterar` verificam `rodada.etapa == Etapa.INTERESSE` antes de validar o formulário.
- Fora de interesse, inclusive numa rodada que não é mais a ativa, respondem 409 pela página só de leitura, com a mensagem única. Isso vale para qualquer valor enviado.

### Testes obrigatórios

- Cobertos pelo critério A-12 da E03-07 (rotas) e pelo A-22 desta fatia (serviços), com Red observado antes do código.

## Correção E03-R04 — revisão da especificação em 2026-10-16

### Diagnóstico

- `_pagina_do_estoque` (`apps/rodadas/views.py`) recebe só a mensagem de erro, e o template `rodadas/estoque.html` monta cada campo a partir do estado gravado:
  - na inclusão recusada, o campo de limite do produto volta vazio;
  - na alteração recusada, volta com o limite gravado, por exemplo 10.
- A mensagem aparece, mas o administrador perde o que digitou. Isso contraria a regra comum da E03-01 ("o valor digitado de volta no formulário").
- Minha falha na especificação: a E03-05 dizia só "mostra a mensagem no formulário" e não fixava a preservação do valor. Os critérios A-20 e A-21 não a verificavam.

### Regra

**O formulário submetido volta como foi enviado, na linha correspondente:**

- `_pagina_do_estoque` recebe, além da mensagem, o formulário submetido: a ação (`incluir` ou `alterar`), o id do produto (na inclusão) ou do estoque (na alteração) e o texto bruto do limite, exatamente como veio no `POST`.
- **A linha do formulário submetido** mostra:
  - no campo `limite`, o texto bruto enviado (por exemplo, `1000000000,000`), sem conversão nem formatação, com o escape automático do template;
  - a mensagem de erro dentro do próprio `<form>`, com `role="alert"`.
- **As demais linhas** continuam com os valores gravados, sem mensagem. As colunas de limite, reservado e livre mostram sempre o estado gravado, inclusive na linha com erro.
- **Recusas cobertas,** todas com status 200 na fase de interesse:
  - formato inválido (formulário inválido);
  - limite negativo;
  - capacidade excedida;
  - `EstoqueAbaixoDoReservado`.
- **Erros sem linha correspondente** continuam no aviso do topo da página, sem valor preservado:
  - produto inexistente ("Produto inválido.");
  - produto de outro fornecedor;
  - produto que já está na rodada (ele já aparece entre os "na rodada", com o valor gravado);
  - `CondicoesCongeladas`, com 409 e a página só de leitura.
- **Sem efeitos:** a recusa não grava nada, não registra auditoria nem envia `estoque_alterado`. Isso já valia e continua valendo.
- **Esquema:** não muda o banco, os serviços nem as mensagens.

### Testes obrigatórios

- O probe `test_estoque_preserva_entrada_rejeitada` do revisor entra literal em `tests/tecnicos/test_rodadas_estoque.py`.
- Critérios A-23 e A-24, com Red observado antes do código. A verificação é feita dentro do `<form>` cuja `action` é a da linha, e não só na página inteira. Para isso, o teste pode usar o `html.parser` da biblioteca padrão ou `assertContains`/`assertInHTML`, sem dependência nova.

### O que não fazer

- Não preservar o valor reescrevendo o estado gravado nem gravando um rascunho.
- Não formatar o texto rejeitado: ele volta como foi digitado.
- Não desligar o escape automático para mostrar o valor.
- Não mover para o topo da página a mensagem das recusas que têm linha correspondente.

## Dependências e decisões em aberto

- Depende de E03-02, E03-03 e E03-04.
- Sem decisões em aberto.
