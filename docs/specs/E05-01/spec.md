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

  Assim, um duplo clique ou um reenvio do formulário não cria uma segunda parcela. Os serviços `adicionar_interesse` e `reduzir_interesse` continuam disponíveis para as etapas seguintes e para os testes.
  - **Revisto pela correção E05-R02:** o total sozinho não basta quando o comprador tem pendência própria no produto. O formulário passa a enviar também o estado que a página mostrou (`esperado`), e o zero passa a remover o item inteiro.
- **A conta é travada primeiro.** A situação do comprador é conferida com a linha da conta travada (`select_for_update(no_key=True)`, pela correção E05-R03). Assim, uma adição nunca é confirmada depois de uma suspensão já confirmada (E05-07), que também trava a conta primeiro. A ordem global de travas passa a ser: **conta do comprador → fornecedor → rodada → produto → estoque → parcelas (por sequência)**. As operações do administrador da E03 não travam conta, e continuam compatíveis porque seguem a ordem a partir do fornecedor.
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

**`definir_interesse`** (total desejado). A correção E05-R02 substitui as regras abaixo; elas ficam como histórico.

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

## Correção E05-R02 — total desejado com pendência própria (2026-10-18)

### Diagnóstico

- O revisor reproduziu o estado com estoque 6 e o comprador A com 6 reservados e 4 pendentes. Três chamadas seguidas de `definir_interesse(A, P, "4")` devolvem (6, 2), (6, 0) e (4, 0). Com `"0"`, o resultado é (4, 0), e não zero.
- O código cumpre as duas regras que eu escrevi:
  - a redução libera estoque;
  - a fila atende as pendentes primeiro, pela FIFO (§5.2, infraestrutura 4.10).
- A pendente mais antiga da fila é a do próprio A. Por isso, a fila devolve a ele o que ele acabou de liberar.
- O defeito está na minha especificação. Eu prometi duas coisas que não valem juntas quando o comprador tem pendência própria:
  - que o total desejado seria sempre atingido e que o zero zeraria o reservado;
  - que repetir o envio não mudaria nada.

### Decisão

O revisor deixou duas opções:

- manter a alocação obrigatória da base e rever a operação de total desejado;
- mudar as regras de negócio para garantir o total final.

Fica a primeira, porque ela é a única que não cria regra nova:

- A FIFO dos pendentes (§5.2, R-5) e a redução pelas parcelas mais recentes (§5) são regras dos documentos-base e não mudam. Nenhuma pendente é apagada sem pedido do comprador. A fila continua atendendo também as pendências do próprio comprador.
- O que muda é o contrato que eu criei para a tela: o "total desejado" e a idempotência do reenvio. Os documentos-base não falam dele.
- O zero passa a significar "remover o item": as pendências do comprador no produto são removidas e o reservado é zerado.
  - São duas ações que o comprador já pode fazer pelos documentos-base: remover pendentes (§5.2) e remover o item (§5).
  - A remoção das pendentes vem primeiro. Assim, o estoque liberado vai para a fila dos outros compradores.
- A idempotência do reenvio deixa de depender do total e passa a usar o estado que a página mostrou (`esperado`). Um envio feito sobre um estado que já mudou é recusado sem gravar.

A decisão é técnica e derivada das regras existentes. O responsável pelo projeto a confirmou em 2026-10-18. As provas `test_definir_com_pendencia_propria` do revisor, que esperam (4, 4) três vezes, não valem como contrato: ignorar a FIFO não é permitido. No lugar delas valem os critérios A-17 a A-20 desta fatia e A-21 a A-24 da E05-05. As provas do revisor `test_zero_remove_com_pendencia_propria` e `test_http_zero_remove_com_pendencia` continuam valendo.

### Regras

**Assinaturas:**

```
definir_interesse(comprador, produto, total, *, esperado: ResumoDoInteresse | None = None) -> ResumoDoInteresse
remover_pendente(comprador, produto, quantidade, *, esperado: ResumoDoInteresse | None = None) -> ResumoDoInteresse
```

- `esperado` é o `ResumoDoInteresse` do comprador no produto que a página mostrou.
- As telas da E05-05 sempre o enviam.
- Sem `esperado`, a chamada opera sobre o estado atual. Cada chamada é uma operação nova, e repetir pode mudar o estado (A-17, parte c).

**Exceção nova** (`apps/interesses/servicos.py`), subclasse de `InteresseRecusado`: `InteresseDesatualizado`, com a mensagem "Seu interesse neste produto mudou. Confira os valores atuais e envie de novo.".

**`definir_interesse`,** depois dos passos comuns 1 a 5 e da validação do `total`:

1. Calcula o `atual` (`ResumoDoInteresse`) do comprador no produto a partir das parcelas travadas.
2. Confere se não há nada a fazer:
   - com `total > 0` e `atual.reservado == total`;
   - com `total == 0` e `atual` igual a (0, 0).

   Nos dois casos, a função devolve `atual` sem gravar nem auditar. Isso vale mesmo com `esperado` diferente, porque o pedido já está cumprido.
3. Com `esperado` informado e diferente de `atual` (reservado ou pendente), levanta `InteresseDesatualizado`. Nada é gravado.
4. Aplica:
   - `total == 0`:
     - remove todas as pendências do comprador no produto, com as regras e a auditoria `interesse.remover_pendente` da E05-03;
     - depois reduz todo o reservado, com as regras e a auditoria `interesse.reduzir`;
     - por último, atende a fila (E05-02).
   - `total > atual.reservado`: atende a fila. Se o reservado ainda for menor que `total`, acrescenta a diferença, com as regras de `adicionar_interesse` e a mesma recusa por inteiro.
   - `0 < total < atual.reservado`: reduz a diferença e depois atende a fila.
5. Devolve o resumo final. Ele pode ficar diferente de `total` quando a fila atende pendências do próprio comprador. Isso é a FIFO funcionando, e não um erro.

**`remover_pendente`:** depois das travas e antes de remover, com `esperado` informado e diferente do estado atual, levanta `InteresseDesatualizado`. O resto da E05-03 não muda. Esta operação não tem caso de "já cumprido", porque remove uma quantidade e não fixa um total.

**Comparação:** `esperado` e `atual` são comparados como `Decimal` com três casas, sem `float`.

### Exemplo de referência

O estoque de `P` tem limite 6. A tem a parcela `a1`, `ativa`, com 6 reservados. A também tem a parcela `a2`, `pendente`, com 4 pendentes e sequência maior.

1. `definir_interesse(A, P, "4", esperado=(6, 4))`:
   - `a1` fica com 4;
   - a fila reserva as 2 liberadas em `a2`, que fica `ativa` com 2 reservados e 2 pendentes;
   - o resultado é (6, 2).
2. O mesmo envio de novo: `InteresseDesatualizado`, e o estado continua (6, 2).
3. `definir_interesse(A, P, "4", esperado=(6, 2))`:
   - `a2` perde os 2 reservados e fica `pendente` com 2;
   - a fila os devolve a `a2`, que é a pendência mais antiga da fila;
   - o resultado é (6, 0).
4. `definir_interesse(A, P, "4", esperado=(6, 0))`: o resultado é (4, 0).
5. Noutro cenário, a partir do estado inicial, `definir_interesse(A, P, "0", esperado=(6, 4))`: o resultado é (0, 0), com `a1` e `a2` `removida`.

## Correção E05-R03 — deadlock entre alteração de preço e operações do comprador (2026-10-18)

### Diagnóstico

- A edição de preço (E03-03 e E05-06) trava o produto e grava notificações com chave estrangeira para a conta de cada comprador afetado.
- No Postgres, a conferência dessa chave estrangeira pede `FOR KEY SHARE` na linha da conta. Como o Django cria as chaves `DEFERRABLE INITIALLY DEFERRED`, o pedido acontece no `COMMIT`.
- As operações do comprador (E05-01 e E05-03) e a moderação (E02-08 e E05-07) travam a conta com `FOR UPDATE` e depois esperam o produto.
- `FOR UPDATE` bloqueia `FOR KEY SHARE`, e o resultado é um ciclo: a edição de preço espera a conta e a outra transação espera o produto. O revisor reproduziu `deadlock detected` com preço × adição e com preço × suspensão.
- O defeito está na minha ordem global de travas. Ela só listava as travas explícitas e dizia que as operações do administrador eram compatíveis, sem contar a trava implícita da chave estrangeira.

### Regra

**Força da trava da conta.** Toda operação que trava a conta do comprador e depois adquire travas de fornecedor, rodada, produto, estoque ou parcelas usa `select_for_update(no_key=True)` (`FOR NO KEY UPDATE`):

- `_travar_conta` em `apps/interesses/servicos.py`, usada por `adicionar_interesse`, `reduzir_interesse`, `definir_interesse` e `remover_pendente`;
- `_travar` em `apps/contas/moderacao.py`, usada por `suspender`, `reativar` e `remover`.

**Por que funciona:**

- `FOR NO KEY UPDATE` não bloqueia `FOR KEY SHARE`, então a conferência da chave estrangeira da notificação não espera a conta.
- `FOR NO KEY UPDATE` continua bloqueando outro `FOR NO KEY UPDATE`. Assim, a suspensão e a adição seguem serializadas pela conta (E05-01 A-15 e E05-07 A-8 e A-14).
- O `UPDATE` da situação da conta na moderação também não pede trava de chave, porque não muda nenhuma coluna de índice único. O `UPDATE` grava só `situacao` (`update_fields`), e `email_normalizado` não muda.
  - Se alguma etapa futura precisar mudar `email_normalizado` ou a chave primária na mesma transação, ela precisa de nova análise de travas.

**Ordem global, revista:** conta do comprador (`FOR NO KEY UPDATE`) → fornecedor → rodada → produto → estoque → parcelas (por sequência).

- Uma transação que segura uma trava dessa cadeia pode pedir `FOR KEY SHARE` em qualquer conta, porque esse pedido é compatível com a trava da conta. É o caso de quem grava notificação, envio, parcela ou auditoria com chave estrangeira para a conta.
- Ela não pode pedir `FOR UPDATE` nem `FOR NO KEY UPDATE` numa conta depois de travar fornecedor, rodada, produto, estoque ou parcelas.

**O que não muda:**

- Os avisos de preço continuam na mesma transação da alteração (E04-02 e E05-06). Mandá-los para `on_commit` quebraria a atomicidade exigida.
- A ordem e a força das demais travas.
- As outras travas de conta (perfil, passkeys, link de acesso, adaptador do allauth). Elas não adquirem travas de fornecedor, rodada, produto, estoque nem parcelas depois da conta, então não entram no ciclo.

**Sem retentativa:** a correção elimina o ciclo, e não trata o `deadlock detected` com nova tentativa.

### Como os testes fixam a intercalação

A pausa fica dentro da transação do próprio serviço, para que a trava segurada seja a do serviço e não uma escolhida pelo teste. Os testes usam `executar_em_paralelo` (E01-05) e o `monkeypatch` de uma função do serviço. A função substituta chama a original e depois espera a barreira, então a trava continua sendo a do código de produção:

- **adição, redução, definição e remoção de pendentes:** `_travar_conta`, em `apps.interesses.servicos`. A pausa acontece com a conta travada e antes da trava do fornecedor;
- **suspensão e remoção da conta:** `remover_interesses_do_comprador`, no namespace de `apps.interesses.receptores`. Aqui a substituta espera a barreira antes de chamar a original. Ela roda depois do `UPDATE` da conta, o que cobre também essa trava.

A edição de preço espera a barreira dentro de uma transação externa que já travou o produto com `select_for_update()`, a mesma trava de `editar_produto`. Depois disso, ela chama `editar_produto`.

As provas `test_preco_e_interesse_sem_deadlock` e `test_preco_e_suspensao_sem_deadlock` do revisor travam a conta com `select_for_update()` na transação externa, que é a trava forte que esta correção retira dos serviços. Depois da correção, essa trava externa não representa mais o serviço, e é por isso que os critérios A-21 desta fatia e A-15 e A-16 da E05-07 fazem a pausa dentro do serviço. A intenção das provas do revisor, a mesma intercalação com as primeiras travas reais dos serviços, é preservada.

## Correção E05-R04 — critérios de concorrência sem Red (2026-10-18)

### Diagnóstico

- Os registros do implementador declaram que os testes destes critérios foram escritos depois do Green, sem Red observado:
  - E05-01: A-13 a A-16;
  - E05-02: A-15 e A-16;
  - E05-03: A-9;
  - E05-07: A-8, A-9 e A-14.
- A justificativa foi que esses testes precisam do serviço real para segurar as travas. Ela não se enquadra na exceção de scaffolding do AGENTS.md: o comportamento concorrente é testável e tem critério próprio.
- Os testes passam, mas isso não comprova a sequência exigida. Uma evidência retroativa não pode ser fabricada.

### Causas

A análise usa os registros do implementador e o histórico do Git.

1. **Uma exceção que não existe.** O AGENTS.md só admite exceção ao Red para "scaffolding sem comportamento testável". O implementador classificou os testes de concorrência como exceção, com o argumento de que eles "dependem do serviço real para segurar as travas". O argumento não se sustenta:
   - antes das travas, o teste falharia, e essa falha é o Red esperado;
   - o andaime da E05-01 devolvia zero sem gravar, então o A-13 falharia por asserção;
   - um serviço sem travas venderia além do estoque no A-16;
   - no A-15, a adição não esperaria a suspensão.

   O teste só não consegue rodar quando a proteção ainda não existe se for escrito para depender dela, por exemplo esperando para sempre a outra operação aparecer em `pg_stat_activity`. Mesmo nesse caso, uma espera com prazo e uma asserção ("a segunda operação não esperou trava") produziriam um Red válido.
2. **Green maior que o mínimo.** No mesmo passo de Green, o implementador escreveu os serviços e todas as travas, que são o código de produção dos critérios de concorrência. Nenhum teste em falha exigia essas travas. O AGENTS.md manda implementar "apenas o necessário" para passar o teste em falha.
3. **A exceção virou padrão sem ser escalada.** A E05-02, a E05-03 e a E05-07 repetem "pelo mesmo motivo da E05-01". O AGENTS.md §2 manda parar e pedir decisão diante de uma lacuna. O implementador registrou a exceção depois de feita e seguiu adiante.
4. **Contribuição da especificação.** Os critérios de concorrência descreviam o arranjo do teste ("a primeira segura as travas até a segunda aparecer esperando"), mas não diziam como obter o Red. Além disso, os passos comuns da E05-01 traziam as travas junto com o comportamento funcional, o que facilitou implementar tudo de uma vez.
5. **Revisão só no fim.** Cada fatia foi entregue num único commit, com produção e testes juntos (`423420e`, `95853c7`, `8892e8f` e `bb713ae`). As sete fatias foram integradas à `main` (PRs #59 a #65) em cerca de 40 minutos, antes da revisão independente. Por isso, o desvio da E05-01 só foi apontado depois de repetido em mais três fatias.

### Prevenção

Estas regras valem para os critérios de concorrência desta correção e das próximas etapas:

- **Ordem do ciclo:**
  1. o comportamento funcional fica verde sem a proteção (sem trava, ou com a trava ainda ausente);
  2. o teste de concorrência é escrito, roda e falha (Red);
  3. só então a trava é implementada (Green).

  A trava é código de produção do critério de concorrência e não entra no Green funcional.
- **Falha observável:** toda espera de sincronização tem prazo. Quando a outra operação não aparece esperando trava, o resultado é uma falha de asserção com mensagem, e não um travamento do teste.
- **Exceção ao Red:** só a de scaffolding do AGENTS.md. Qualquer outra situação em que o Red pareça impossível é registrada como dúvida e escalada antes do código de produção (AGENTS.md §2 e §9), nunca declarada depois.
- **Evidência:** o registro de Red e Green é feito por critério, inclusive nos de concorrência, com o comando e o motivo da falha.

### Tratamento

**Decidido pelo responsável pelo projeto em 2026-10-18: opção (a)**, registro da não conformidade e prova de sensibilidade por mutação. Os passos são:

1. **Registro da não conformidade.** No `review.md` de cada fatia afetada, o implementador registra, numa seção "Não conformidade de TDD":
   - os critérios;
   - o que aconteceu ("teste escrito depois do código de produção; sem Red observado");
   - o tratamento aplicado.

   Nenhum texto pode dar a entender que houve Red nesses critérios.
2. **Prova de sensibilidade por mutação,** para cada critério da lista:
   - aplicar temporariamente uma mutação que retira a proteção que o critério descreve;
   - rodar o teste e registrar a falha por asserção. Uma falha por tempo esgotado ou por erro de infraestrutura não serve;
   - desfazer a mutação e registrar o teste verde;
   - registrar, para cada critério, o trecho mudado, o comando e as duas saídas, com o título "sensibilidade (mutação), não Red".

   Exemplos de mutação:
   - em E05-01 A-15, ler a conta com `get` em vez de travá-la;
   - em E05-01 A-14, validar a quantidade com a instância recebida, sem reler o produto travado;
   - em E05-01 A-13 e A-16, retirar todas as travas depois da conta;
   - em E05-02 A-15 e A-16 e em E05-03 A-9, retirar a trava do fornecedor e a das parcelas em `alocar_pendentes` e no serviço concorrente;
   - em E05-07 A-8, A-9 e A-14, ler a conta sem trava em `_travar` da moderação.

   Se uma mutação razoável não fizer o teste falhar, o implementador registra isso como limite do teste e propõe o reforço. O caso já registrado é o das travas de fornecedor e rodada, que não quebram nenhum teste quando retiradas.
3. **Novos critérios com Red real.** Todos os critérios desta correção, inclusive os de concorrência, seguem Red → Green → Refactor completo:
   - E05-01: A-17 a A-21;
   - E05-02: A-17;
   - E05-05: A-21 a A-24;
   - E05-07: A-15 e A-16.

   O Red de um teste de concorrência é o resultado errado observado no código atual: `deadlock detected`, `TypeError` ou o estado errado. Não pode ser um teste que nunca falhou.

Os passos 1 e 2 são o tratamento definitivo dos critérios antigos. Refazer esses testes não recriaria um Red histórico. No registro da não conformidade (passo 1), o implementador também confirma ou corrige as causas acima.

## Dependências e decisões em aberto

- Depende de E02-08, E02-10, E03-02, E03-03, E03-04, E03-05 e E03-06.
- Sem decisões em aberto. Em 2026-10-18, o responsável pelo projeto:
  - escolheu a opção (a) para a correção E05-R04;
  - confirmou as decisões das correções E05-R02 (reenvio recusado quando o estado mudou e "Remover" que inclui as pendências) e E05-R03.
