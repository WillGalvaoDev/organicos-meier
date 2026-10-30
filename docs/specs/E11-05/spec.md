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
