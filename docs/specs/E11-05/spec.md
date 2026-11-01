# E11-05 — Rodada que volta para interesse por pagamentos insuficientes

Fatia 5 de 8 da milestone **E11 — Apuração final e fila de pendentes**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E11-01.

## Contexto e objetivo

Quando o resultado da apuração é `retorno_para_interesse` (E11-03), a rodada volta na hora para a fase de interesse (§8.2, passo 3.7). Neste caso:
- as reservas de quem pagou ficam na própria rodada, com a ordem original;
- as dos inadimplentes já foram liberadas (E11-02);
- o estoque cadastrado não muda;
- todos os valores recebidos são apresentados ao administrador para autorização da devolução integral;
- não há frete efetivo, porque nenhuma compra ao fornecedor foi feita.

Esta fatia acrescenta esse ramo à transação da apuração. Ela reutiliza o serviço de retorno da E06-06 com um motivo novo.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §8.2, passo 3.7 | Mínimo não atendido: a rodada volta para interesse e apresenta ao administrador, para autorização, a devolução de todos os valores recebidos. Sem frete efetivo. |
| Especificação §8.2, "quando a rodada volta para interesse" | Interesses e reservas de quem pagou preservados ou restaurados, com a prioridade original. Pedidos de quem não pagou removidos, reservas liberadas. Estoque inalterado, sem reposição, redefinição ou duplicação. Reembolsos pendentes não impedem a rodada. Registros financeiros separados; novo fechamento permitido com estornos pendentes. Mínimo, múltiplos e estoque voltam a ser alteráveis. |
| Especificação §8.2, requisito derivado | Distinguir ciclos financeiros da mesma rodada. Um pagamento antigo não quita um pedido novo nem duplica reservas. |
| Especificação §5.2 e R-5 | A fila vale para rodada viável. No retorno ao interesse, as reservas dos adimplentes ficam na própria rodada (17.5). |
| 17.5 | Estoque inalterado, reservas de quem pagou preservadas, as dos inadimplentes liberadas. Estornos pendentes não bloqueiam. |
| Infraestrutura 4.10 | Retorno: o estoque não é tocado; as reservas de quem pagou são mantidas ou reativadas com a mesma sequência. A invariante "total reservado ≤ estoque" é verificada sob trava do estoque. |
| Infraestrutura 3.1 | Sem frete efetivo no retorno ao interesse. |
| Especificação §12 | "Retorno para interesse": motivo e situação de interesses e estornos. |
| Herdado da E06 | `voltar_para_interesse(rodada, *, motivo, destinatarios)`: a E11 acrescenta o motivo dos pagamentos insuficientes, o tratamento de pedidos e estornos e o próprio texto do aviso, com uma chave que não colida com a da E06-06. |
| Herdado da E08 | Ao devolver a rodada ao interesse, restaurar as reservas dos pedidos a partir de `ParcelaNoPedido` antes de atender a fila, inclusive das parcelas que ficaram `pendente` com a parte congelada (E08-02). |
| Herdado da E09 | Os pedidos não válidos e o retorno ao interesse devolvem pela custódia, com obrigação com comprador. No retorno, não chamar a apuração no livro. |
| Cenários §16 | 15, 16, 56, 57 e 103 |
| Testes técnicos | T-21 e T-22 |

## Escopo

**Dentro:**
- O motivo de retorno `pagamentos_insuficientes` e o retorno a partir de `pagamento`.
- A restauração das reservas dos pagantes.
- A conferência do estoque.
- A devolução integral de cada pedido pago.
- O aviso de retorno.

**Fora:**
- A autorização e a execução das devoluções (E10).
- O novo fechamento, que é o da E06 sem mudança.

## Regras

Com `resultado = retorno_para_interesse`, na transação da apuração, depois da E11-02 e da E11-03:

1. **Restauração das reservas dos pagantes:**
   - **quais parcelas:** as `ParcelaDeInteresse` que aparecem em `ParcelaNoPedido` de um pedido pago do ciclo;
   - **reserva:** `quantidade_reservada` passa a ser a soma das quantidades congeladas da parcela nesse ciclo;
   - **situação:** `ativa`;
   - **pendente:** não muda.

   Isso vale para as duas situações em que a parcela ficou na abertura:
   - `em_pedido`, em que a reserva já era a congelada;
   - `pendente`, com a parte congelada só no pedido (E08-02).

   A `sequencia` não muda, e nenhuma parcela é criada. As unidades de caixa invalidada também ficam reservadas, porque no retorno não há fila (§5.2, cenário 103).
2. **Conta que não pode ter interesses** (suspensa ou removida): a parcela não é restaurada, como na E11-04, regra 4. A auditoria registra a parcela e o motivo.
3. **Conferência do estoque:** para cada produto do estoque da rodada, com o estoque travado (E11-01), `total_reservado(produto) ≤ limite` quando há limite.
   - **Por que deve valer sempre:** as reservas restauradas couberam no estoque na abertura, e o estoque não pode ser alterado fora de interesse.
   - **Se falhar:** `RuntimeError` desfaz a apuração inteira, sem escrita, e o log registra o produto. Isso não deve ocorrer.
4. **Retorno:** `voltar_para_interesse(rodada, motivo="pagamentos_insuficientes", destinatarios=[])`. A função passa a aceitar a rodada em `pagamento` só com esse motivo; os motivos da E06 continuam exigindo `fechamento_encerrado`. Ela:
   - grava a etapa `interesse` e a auditoria do retorno;
   - atende a fila (`alocar_pendentes`), agora com o estoque liberado pelos inadimplentes (E11-02). Os pendentes antigos do fornecedor são atendidos antes de qualquer reserva nova (R-5);
   - não emite o aviso da E06-06, porque recebe `destinatarios=[]`. O aviso desta fatia é próprio.
5. **Devolução integral:** para cada pedido pago do ciclo, na ordem de `pk`, `reembolso_integral_do_pedido(pedido, chave="minimo:<apuracao>:<pedido>", motivo="minimo_nao_atingido", autor=SISTEMA)` (E10-02). Cada um gera a obrigação, financiada pela custódia do ciclo. A execução aguarda a autorização do administrador na lista de devoluções (E10-07).
6. **Sem apuração no livro:**
   - `registrar_apuracao_no_livro` não é chamado;
   - `frete_do_ciclo` continua `None`;
   - as tarifas da rodada ficam pendentes para o administrador (E09-06, infraestrutura 3.2).
7. **Ciclo:** o ciclo apurado fica como histórico. Os pedidos dele continuam como estão: pagos, com o reembolso integral, e cancelados. O próximo fechamento registra outro ciclo (E06-01), e o pagamento seguinte gera pedidos novos. Um pagamento antigo, pela referência do ciclo, só encontra os pedidos do ciclo antigo e vira devolução (E11-01).
8. **Aviso `retorno_para_interesse`** a cada comprador pagante (os inadimplentes recebem só o da E11-02):
   - **título:** "Rodada de volta ao interesse: {fornecedor}";
   - **corpo:**
     - "A rodada de {fornecedor} voltou para a fase de interesse porque os pagamentos confirmados não atingiram o mínimo do fornecedor";
     - "Seus interesses continuam reservados na rodada, na ordem original, e você pode alterá-los";
     - "O valor pago de {total} será devolvido integralmente depois da autorização do administrador".

     O mínimo do fornecedor não aparece, como na E06-06.
   - **link:** `/pedidos/<pk>/`;
   - **chave:** `retorno_para_interesse:apuracao:<apuracao>:<conta>`, que não colide com a `retorno_para_interesse:<ciclo>` da E06-06.
9. **Auditoria:** a da apuração passa a ter as parcelas restauradas (pk e reserva), as não restauradas com o motivo e os reembolsos integrais.

## Invariantes

- Depois do retorno, `total_reservado(produto) ≤ limite` para todo produto da rodada (cenário 57).
- Nenhuma reserva duplicada: cada parcela tem uma reserva só, e o valor dela é o congelado.
- O estoque cadastrado (`EstoqueDaRodada.limite`) não muda.
- A sequência de toda parcela é a de antes.
- A soma devolvida de cada pedido pago é exatamente o total pago.

## Casos-limite e concorrência

- **Adição de outro comprador em paralelo com o retorno** (T-21): a adição trava o fornecedor e espera a apuração. Depois, a rodada está em interesse, e a adição chama a fila antes de reservar para si (E05-02). O total reservado ≤ estoque, e a ordem segue a sequência.
- **Pendente antigo do fornecedor e estoque liberado pelo inadimplente:** o pendente recebe a reserva antes de qualquer interesse novo.
- **Novo fechamento com estorno pendente** (cenários 16 e 56): permitido. As devoluções do ciclo antigo continuam no fluxo delas, sem misturar cobranças.
- **Mínimo, múltiplo e estoque alteráveis** de novo, porque a rodada está em interesse (17.11).

## Dependências e decisões em aberto

Depende de E11-03, E10-02 e E06-06. Nenhuma decisão em aberto.

## Correções da revisão: R01, R02 e R04 no retorno ao interesse (2026-11-01)

Origem: revisão independente sobre `1a36495` (`docs/specs/E11-05/review.md` e `docs/specs/E11-08/review.md`). Vale o resumo na E11-08 (`spec.md`, "Correções da revisão da E11").

### R01 — remover a sobra pendente não impede restaurar a reserva paga

A regra da correção E11-R01 da E11-04 vale também para a regra 1 desta fatia.
- **Quem impede é só a conta:** a restauração da reserva de um pagante depende só de a conta poder ter interesses na apuração, e nunca da situação atual da parcela. A parcela `removida` porque o comprador removeu toda a sobra pendente passa a `ativa`, com a reserva igual à parte congelada.
- **A pendência fica como está:** zero, porque a sobra removida não volta.
- **Fim do motivo `parcela_removida`.**

### R02 — a reserva de uma conta impedida não pode ocupar o estoque no retorno

**Diagnóstico.** A regra 2 mandava só não restaurar a parcela de um pagante suspenso ou removido. A parcela `em_pedido` dele continuava `em_pedido`, com a reserva congelada contada em `total_reservado`. A rodada de volta ao interesse ficava com estoque preso por uma conta que não pode ter interesses (§2, E05-07). O pedido congelado preserva a compra, mas não exige uma reserva operacional no novo ciclo.

**Regra 2, reescrita:**
- **O que muda na parcela:** no retorno, cada `ParcelaDeInteresse` de um pagante cuja conta não pode ter interesses (suspensa ou removida) e que ainda está `em_pedido`, `ativa` ou `pendente` em produto do fornecedor passa a `removida`, com reserva e pendência zero. É o efeito da suspensão sobre interesses (E05-07), aplicado agora à parte que estava congelada.
- **O que não muda:** a sequência e a quantidade original.
- **O pedido:** fica como está, pago, com a devolução integral da regra 5. Nenhum registro do pedido muda.
- **Antes da fila:** a remoção acontece antes da conferência do estoque (regra 3) e do atendimento da fila (regra 4). Assim, o estoque liberado atende os pendentes e novas reservas como qualquer outra liberação (R-5).
- **Auditoria:** registra, por parcela, o motivo (`conta_suspensa` ou `conta_removida`) e as quantidades que ela tinha.
- **Aviso:** o pagante com conta impedida não recebe o `retorno_para_interesse`, que fala de interesses reservados. A devolução integral é avisada pela E10 quando autorizada. A regra 8 vale só para pagantes com conta ativa.

O ramo viável (E11-04) não muda: a rodada não volta ao interesse e ninguém reserva nela. O fim das `em_pedido` no encerramento da rodada continua com a E14.

### R04 — o retorno não pode promover as travas da apuração

**Diagnóstico.** A apuração trava fornecedor, rodada, produtos, estoques e parcelas com `FOR NO KEY UPDATE` (decisão técnica da implementação, registrada na E11-01). Com isso, outras transações podem inserir registros com chave estrangeira para essas linhas: a conferência da chave pede `FOR KEY SHARE`, compatível com `FOR NO KEY UPDATE`.

O retorno reutiliza `voltar_para_interesse` e `alocar_pendentes` (com `travar_rodada_para_interesses`, `travar_estoque` e `travar_parcelas`), que travam as mesmas linhas com `FOR UPDATE`. A trava sobe de nível. Uma tarefa de tarifa tardia (`registrar_tarifas_pendentes_agora`) já segura contas do livro-razão e insere uma despesa com chave para a rodada. Ela espera a apuração, e a apuração espera as contas dela. O resultado é um impasse (`deadlock detected`).

**Regras:**
- **Nenhuma trava mais forte que `FOR NO KEY UPDATE`.** Durante toda a transação da apuração (E11-01 a E11-05), nenhuma linha de fornecedor, rodada, produto, estoque, parcela ou conta de comprador é travada com `FOR UPDATE` ou `FOR SHARE`. Isso vale também dentro dos serviços reutilizados (`voltar_para_interesse`, `alocar_pendentes`, `_alocar_produto` e as funções de trava que eles chamam). A gravação da etapa (`UPDATE` de campo que não é chave) já usa o nível compatível.
- **A forma é escolha do implementador,** registrada no `review.md`. Dois caminhos aceitos:
  - **(a)** os serviços reutilizados recebem a indicação de que as travas já foram tomadas pela apuração, ou de travar com `FOR NO KEY UPDATE`;
  - **(b)** as funções de trava de interesse passam a usar `FOR NO KEY UPDATE` em todo o sistema.

  O caminho (b) mantém a exclusão mútua entre as operações de interesse, porque `FOR NO KEY UPDATE` conflita consigo mesmo. Mesmo assim, a suíte de concorrência existente (E05, E06, E08) tem de continuar verde.
- **A ordem das travas não muda:** contas dos compradores, fornecedor, rodada, produtos por `pk`, estoques, parcelas, situações dos pedidos e, por último, as contas do livro-razão (regra única da E09).
- **A aprovação (E11-06)** já trava com `FOR NO KEY UPDATE` e não muda. O critério novo também a cobre.

### A-3 — texto do critério

O A-3 desta fatia afirmava a parcela de A com reservado 6 e **pendente 2** depois da apuração inteira. Isso contradiz a regra 4: o estoque liberado por B atende o pendente de A, que é o mais antigo (R-5). Como observou o implementador e confirmou o revisor, o critério passa a afirmar os dois momentos:
- logo depois da restauração (regra 1), reservado 6 e pendente 2;
- depois do retorno inteiro, com a fila atendida, reservado 8 e pendente 0, desde que haja estoque livre.

O A-3 original fica substituído pelo abaixo.

## Correção da revalidação: R02 residual (2026-11-01)

Origem: revalidação independente sobre `0af24ad` (`docs/specs/E11-08/review.md`, "R02 residual — importante"). Nenhuma regra comercial muda: a regra 2 reescrita já determina o comportamento. O defeito está na fonte do registro.

**Diagnóstico.** A identificação do pagante com conta impedida saía da lista das parcelas efetivamente removidas no retorno. Quando a suspensão (ou a remoção da conta) já tinha removido todas as parcelas do pagante antes da apuração (E05-07), essa lista ficava vazia. O pagante passava por conta ativa: recebia o `retorno_para_interesse`, que promete interesses reservados, e a tela do pedido afirmava o mesmo. Não ter parcela a remover não significa que a conta esteja ativa.

**Regra 2-A — a situação da conta registrada na apuração:**
- **O registro:** na transação da apuração, depois das travas, a apuração registra, para cada comprador com pedido pago, se a conta dele pode ter interesses naquele momento. A auditoria `rodada.apuracao_final`, em `retorno`, ganha `contas_impedidas`: uma entrada por pagante com conta suspensa ou removida, com o comprador e o motivo (`conta_suspensa` ou `conta_removida`). A entrada existe mesmo sem nenhuma parcela removível.
- **As remoções efetivas continuam:** `removidas_por_conta_impedida` fica como está, só com as parcelas que a regra 2 removeu agora e as quantidades que elas tinham. As parcelas que já estavam `removida` não entram nela e não mudam.
- **As não restauradas:** as parcelas de pedidos pagos que a regra 1 deixou de restaurar por conta impedida passam a constar em `retorno.nao_restauradas`, com a parcela e o motivo. Hoje elas são descartadas.
- **Uma fonte só:** a situação da conta é lida uma vez, com a conta travada pela apuração (`_travar`). O mesmo resultado decide a remoção da regra 2, a não restauração da regra 1, os destinatários da regra 8 e o registro acima. Não há segunda leitura da situação no mesmo ato.
- **Destinatários do aviso (regra 8):** os pagantes fora de `contas_impedidas`. O pagante com conta impedida não recebe o `retorno_para_interesse`, tenha ou não parcela removida agora.
- **Depois da apuração:** o registro é histórico. Reativar ou suspender a conta depois não muda o registro, o aviso já emitido nem o que a tela mostra do efeito da apuração (E11-07).

**Rodada viável (E11-04):** já usa a situação da conta, independente da parcela, e registra `nao_restauradas` por pedido; não muda. O critério E11-04 A-19 só confirma o caso da parcela já removida.

**Dados anteriores:** não há dado de produção (Fase 1). Nenhuma migração de dados nem leitura de compatibilidade para auditorias antigas.
