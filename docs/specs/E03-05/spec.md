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
- **Recusa de redução:** `EstoqueAbaixoDoReservado` mostra a mensagem no formulário, com status 200.
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

## Dependências e decisões em aberto

- Depende de E03-02, E03-03 e E03-04.
- Sem decisões em aberto.
