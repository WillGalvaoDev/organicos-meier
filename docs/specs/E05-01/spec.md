# E05-01 — Adição e redução de interesse com reserva de estoque

Fatia 1 de 7 da milestone **E05 — Interesses, reservas e progresso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

A E03 entregou rodadas, estoque por rodada e o modelo da parcela de interesse (E03-04), mas nenhum serviço que crie ou altere parcelas. Esta fatia entrega os serviços com que o comprador ativo adiciona, reduz e remove quantidades de um produto da rodada ativa. Cada adição:

- reserva estoque;
- recebe a própria posição FIFO;
- é recusada por inteiro quando passa do estoque livre.

As telas ficam na E05-05. A fila de pendentes entra na E05-02, sobre estes mesmos serviços.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Comprador ativo gerencia interesses nas etapas permitidas. Suspenso não adiciona interesses. Restrições verificadas no servidor. |
| Especificação §4.2 | O comprador só seleciona quantidades múltiplas do incremento. Aritmética decimal exata, validada no servidor. |
| Especificação §5 | Adicionar reserva estoque. Não permitir reservas acima do estoque limitado; o excedente é recusado claramente, sem sucesso falso. Cada acréscimo tem posição própria na fila. Ao reduzir, saem primeiro as parcelas mais recentes do comprador. Remoção e redução liberam a reserva. Concorrência sem sobrevenda, com desempate determinístico. Durante interesse e fechamento o comprador adiciona, reduz e remove. |
| Especificação §7 | Interesse aceita alterações e reserva estoque. Fechamento aceita alterações e novos compradores. |
| Cenários §16 | 3, 8, 63, 85 e 109 (pela API), 108. |
| Infraestrutura 4.10 e 4.12 | Parcela com sequência do banco; `quantidade % incremento == 0` em toda adição ou alteração; a adição trava a linha do produto, então adições e alterações de incremento se serializam. |
| Infraestrutura 5 | `select_for_update` em estoque e fila. Trava de linha no estoque por produto na reserva. |
| Infraestrutura 8 | T-26, T-49, T-50. |
| E02-10 | Política `comprador_ativo` e `Conta.pode_adicionar_interesse`. |
| E03-02, E03-05, E03-06 | `travar_condicoes`, `travar_estoque`, `calcular_livre`, `alterar_incremento`. Ordem global de travas: fornecedor, rodada, produto, estoque, parcelas. |
| E03-03 D-1 | Produto indisponível continua aceitando adições e mantém os interesses. |
| E03-04 | `ParcelaDeInteresse`, `SituacaoParcela`, `total_reservado` e as invariantes da parcela. |

## Escopo

**Dentro:**

- A primitiva `travar_rodada_para_interesses` e a exceção `InteressesBloqueados`.
- Os serviços `adicionar_interesse`, `reduzir_interesse` e `definir_interesse`, e a leitura `interesse_do_comprador`.
- A trava da conta do comprador como primeiro elo da ordem global de travas.

**Fora:**

- O atendimento da fila de pendentes, que é chamado antes de cada reserva nova e depois de cada liberação (E05-02).
- A remoção de pendentes (E05-03).
- O progresso e as caixas (E05-04).
- As telas e as rotas (E05-05).
- O bloqueio pelo prazo de fechamento encerrado (E06): a rodada ainda não tem prazo.

## Decisões técnicas

- **Excedente recusado por inteiro.** O cenário 76 admite que a adição seja "recusada ou limitada". Uma adição acima do estoque livre é recusada sem reservar nada, e a mensagem informa quanto está disponível. Aceitar só uma parte apresentaria como sucesso algo que o comprador não pediu, e a §5 manda recusar o excedente "sem sucesso falso".
- **Quantidade desejada como operação idempotente.** As telas (E05-05) enviam o **total reservado desejado** do produto, e não o acréscimo. `definir_interesse` calcula a diferença:
  - diferença positiva: acréscimo, que cria uma parcela nova com posição própria;
  - diferença negativa: redução.

  Assim, um duplo clique ou um reenvio do formulário não cria uma segunda parcela, sem precisar de token. Os serviços `adicionar_interesse` e `reduzir_interesse` continuam disponíveis para as etapas seguintes e para os testes.
- **A conta é travada primeiro.** A situação do comprador é conferida com a linha da conta travada (`select_for_update`). Assim, uma adição nunca é confirmada depois de uma suspensão já confirmada (E05-07), que também trava a conta primeiro. A ordem global de travas passa a ser: **conta do comprador → fornecedor → rodada → produto → estoque → parcelas (por sequência)**. As operações do administrador da E03 não travam conta, e continuam compatíveis porque seguem a ordem a partir do fornecedor.
- **Interesse por fornecedor serializado.** Como toda operação de interesse trava a linha do fornecedor, operações sobre produtos diferentes do mesmo fornecedor também se serializam. Para 100 compradores e 50 fornecedores, isso é aceitável e elimina deadlocks entre produtos.
- **Auditoria das operações do comprador.** Cada adição e cada redução gravam uma entrada de auditoria (`registrar_auditoria`, E01-04) com ids e quantidades, sem nome nem e-mail. A FIFO decide quem fica com caixas e estoque, e o registro permite reconstruir a ordem numa disputa.
- **Sem vínculo da parcela com a rodada.** A E03-04 permitiu acrescentar esse vínculo, mas ele não é necessário. Uma parcela `ativa` com reserva só existe para produto incluído na rodada ativa do fornecedor, e os serviços desta etapa garantem isso. As etapas que encerram ou reiniciam ciclos (E06, E08, E11 e E12) mantêm a regra.

## Regras

**Primitiva** (`apps/rodadas/condicoes.py`):

```
travar_rodada_para_interesses(fornecedor) -> Rodada
```

- Exige transação aberta. Fora dela, levanta `TransactionManagementError`, como `travar_condicoes`.
- Trava a linha do fornecedor e depois a da rodada ativa (`ETAPAS_ATIVAS`).
- Devolve a rodada quando a etapa é `interesse` ou `fechamento`.
- Nos demais casos, levanta `InteressesBloqueados(codigo)`:
  - `sem_rodada_ativa`;
  - `etapa_bloqueada`, quando a etapa é `fechamento_encerrado`, `pagamento` ou `aguardando_fornecedor`.
- A mensagem é sempre a mesma: "Os interesses deste fornecedor não podem ser alterados nesta etapa."
- A E06 acrescenta aqui a recusa do fechamento com prazo vencido, mesmo antes de a tarefa mudar a etapa (§15, "validar prazo também nas ações do usuário").
- `interesses_editaveis(fornecedor) -> bool` faz a leitura sem trava, só para a tela escolher se mostra formulários. Quem grava trava e confere de novo.

**Serviços** (`apps/interesses/servicos.py`):

```
adicionar_interesse(comprador, produto, quantidade) -> ResumoDoInteresse
reduzir_interesse(comprador, produto, quantidade) -> ResumoDoInteresse
definir_interesse(comprador, produto, total) -> ResumoDoInteresse
interesse_do_comprador(comprador, produto) -> ResumoDoInteresse
```

`ResumoDoInteresse` é um `dataclass` imutável. Ele tem `reservado` e `pendente` (`Decimal`, com três casas), com a soma das parcelas do comprador naquele produto:

- `reservado` soma as parcelas `ativa`;
- `pendente` soma as parcelas `ativa` e `pendente`.

**Passos comuns,** nesta ordem, numa única `transaction.atomic()`:

1. Trava a conta do comprador e confere `pode_adicionar_interesse` (comprador `ativa`). Se for falso, levanta `PermissionDenied`.
2. Executa `travar_rodada_para_interesses(produto.fornecedor)`.
3. Executa `travar_estoque(rodada, produto)` (E03-05), que trava o produto e o estoque. Produto sem estoque nesta rodada levanta `ProdutoForaDaRodada`, com a mensagem "Este produto não está disponível para interesse agora.".
4. Relê o produto já travado e valida a quantidade com `validar_quantidade(produto, quantidade)` (E03-03).
   - A validação usa o incremento vigente depois da trava. É isso que serializa a adição com `alterar_incremento` (cenário 108, T-49).
   - A quantidade chega como texto decimal ou `Decimal`. `float` é recusado (`QuantidadeInvalida`).
5. Trava as parcelas do produto com `travar_parcelas(produto)` e calcula o reservado do produto a partir da lista travada: a soma de `quantidade_reservada` das parcelas `ativa` e `em_pedido`, a mesma regra de `total_reservado`.
   - `travar_parcelas(produto) -> list[ParcelaDeInteresse]` fica em `apps/interesses/consultas.py`. Ela trava com `select_for_update`, em ordem de `sequencia`, todas as parcelas do produto que não estão `removida`.
   - Não use `total_reservado(produto, travar=True)` neste passo: essa função só trava as parcelas `ativa` e `em_pedido`, e as pendentes também são lidas e alteradas pela E05-02.
   - Na prática, quem serializa as operações de interesse é a trava do fornecedor, adquirida no passo 2 por todas elas (E05-01, E05-02, E05-03 e E05-07). A trava das parcelas é a segunda defesa e precisa cobrir toda parcela que a operação lê para decidir ou altera.

**`adicionar_interesse`** (acréscimo):

- Calcula `livre = calcular_livre(estoque.limite, reservado)`. Sem limite, `livre` é `None` e qualquer quantidade válida é aceita.
- Com `livre` diferente de `None` e `quantidade > livre`, levanta `EstoqueInsuficiente(disponivel=livre)` e não grava nada. A mensagem é:
  - "Este produto está esgotado nesta rodada.", quando `livre == 0`;
  - "Há apenas <livre> <unidade> disponível.", nos outros casos. A quantidade aparece no formato de `formatar_quantidade`, e a unidade é o rótulo de `Unidade`.
- Caso contrário, cria uma `ParcelaDeInteresse` com:
  - `quantidade_original = quantidade_reservada = quantidade`;
  - `quantidade_pendente = 0`;
  - `situacao = ativa`.

  A sequência vem do banco.
- Audita `interesse.adicionar` com `objeto` igual à parcela criada e `{"parcela", "produto", "rodada", "quantidade"}`.

**`reduzir_interesse`:**

- Recusa, com `ReducaoAcimaDoReservado(reservado)` e a mensagem "A redução passa da quantidade reservada (<reservado>).", quando `quantidade` é maior que o `reservado` do comprador no produto.
- Reduz as parcelas `ativa` do comprador com `quantidade_reservada > 0`, da **maior sequência para a menor**, até completar a quantidade. Para cada parcela tocada:
  - `quantidade_reservada` diminui;
  - se ficar zero e `quantidade_pendente > 0`, a situação passa a `pendente`;
  - se as duas ficarem zero, a situação passa a `removida`.
- `quantidade_original` e `sequencia` nunca mudam.
- Audita `interesse.reduzir` com `objeto` igual ao produto e `{"produto", "rodada", "quantidade", "parcelas": [ids]}`.
- A redução não toca a quantidade pendente. A remoção de pendentes é a E05-03.

**`definir_interesse`** (total desejado):

- `total` é validado como quantidade maior ou igual a zero, múltipla do incremento e dentro da capacidade. Zero é aceito e significa remover todo o reservado.
  - A validação acontece no passo 4, depois da trava.
  - `validar_quantidade` recusa zero. Para `total == 0`, aplique a mesma conversão e capacidade, e aceite o zero explicitamente.
- O serviço compara `total` com o `reservado` atual:
  - maior: aplica o acréscimo da diferença, com as regras de `adicionar_interesse`;
  - menor: aplica a redução da diferença, com as regras de `reduzir_interesse`;
  - igual: não grava nem audita nada.
- Tudo acontece numa única transação e numa única aquisição das travas.

**Produto indisponível** (E03-03 D-1): `disponivel = False` não recusa adição nem redução.

**Preço:** nenhuma operação desta fatia grava preço. Os totais são calculados na leitura com o preço vigente (E05-04 e E05-06).

## Interfaces

- `apps/rodadas/condicoes.py`: `travar_rodada_para_interesses`, `interesses_editaveis` e `InteressesBloqueados`.
- `apps/interesses/consultas.py`: `travar_parcelas`.
- `apps/interesses/servicos.py`:
  - os serviços `adicionar_interesse`, `reduzir_interesse`, `definir_interesse` e `interesse_do_comprador`;
  - o `dataclass` `ResumoDoInteresse`;
  - as exceções `ProdutoForaDaRodada`, `EstoqueInsuficiente` e `ReducaoAcimaDoReservado`, todas com `mensagem`.
- Nenhuma migração é esperada. Se for necessária, ela não afrouxa nenhuma restrição da E03-04.

## Invariantes

- O total reservado de um produto nunca passa do limite do estoque da rodada.
- Toda parcela criada tem quantidade múltipla do incremento vigente no momento da criação.
- Nenhuma parcela é criada, reduzida ou removida para comprador que não esteja `ativa` no momento da trava.
- Uma recusa não grava nada: nem parcela, nem auditoria.

## Casos-limite e concorrência

- **Última unidade disputada** (cenário 3): duas adições simultâneas de 1 unidade com `livre = 1`. Uma é aceita, e a outra recebe `EstoqueInsuficiente` com "esgotado".
- **Acréscimo posterior** (cenário 8): A adiciona 8, B adiciona 10 e depois A adiciona mais 2. A parcela nova de A tem sequência maior que a de B. Se A reduzir 2, a redução sai dessa parcela nova.
- **Redução que atravessa parcelas:** A tem parcelas de 2, 3 e 4, nessa ordem. Ao reduzir 5, a de 4 vira `removida` e a de 3 fica com 2.
- **Incremento alterado em paralelo** (cenário 108, T-49): a adição e `alterar_incremento` se serializam pela trava do produto.
  - Se a alteração confirma antes, a adição é validada contra o novo incremento.
  - Se a adição confirma antes, a alteração vê a parcela nova e é recusada quando incompatível.
  - Nunca fica parcela fora do incremento vigente.
- **Suspensão em paralelo:** com a conta travada primeiro, a adição espera a suspensão confirmar e então é recusada com `PermissionDenied`.
- **Rodada em `fechamento`:** adição, redução e definição são aceitas (§7).
- **Rodada em `fechamento_encerrado`, `pagamento` ou sem rodada ativa:** `InteressesBloqueados`.
- **Estoque com limite 0:** "esgotado".
- **Limite não múltiplo do incremento** (por exemplo, limite 10 com incremento 4): o livre é 10 e uma adição de 8 é aceita. Depois, uma de 4 é recusada com "Há apenas 2 unidade disponível."
- **`definir_interesse` repetido com o mesmo total:** a segunda chamada não grava nada.

## Dependências e decisões em aberto

- Depende de E02-08, E02-10, E03-02, E03-03, E03-04, E03-05 e E03-06.
- Sem decisões em aberto.
