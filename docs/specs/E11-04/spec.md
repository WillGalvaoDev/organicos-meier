# E11-04 — Rodada viável: estorno proporcional e restauração na fila de pendentes

Fatia 4 de 8 da milestone **E11 — Apuração final e fila de pendentes**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E11-01.

## Contexto e objetivo

Quando o resultado da apuração é `valida` (E11-03), cada comprador que pagou unidades em caixa invalidada recebe:
- **o estorno proporcional dessas unidades** (§8.2, passo 3.4; §9.2). Ele nasce como reembolso e obrigação com o comprador (E10-02) e espera a autorização do administrador para ser executado (E10-04);
- **a volta das unidades para a fila de pendentes do fornecedor,** com a prioridade original de cada parcela (§5.2, Q-1). As unidades não reservam de novo o estoque da rodada apurada e não esperam a conclusão do reembolso.

Esta fatia acrescenta esse passo à transação da apuração, depois do resultado, e o aviso a esses compradores.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §8.2, passo 3.4 | Estorno proporcional das unidades pagas em caixa invalidada. Com a rodada viável, as unidades vão para a fila de pendentes do fornecedor, com a prioridade original de cada parcela, sem reservar de novo o estoque desta rodada e sem esperar o reembolso. Os itens válidos do ciclo não mudam. Sem duplicar reservas, parcelas nem posições. |
| Especificação §5.2 e Q-1 | Fila de pendentes do mesmo fornecedor, FIFO original, reserva só quando houver estoque numa rodada seguinte. A restauração não modifica pedidos congelados e não depende do reembolso. Parcelas, reservas e restaurações não duplicadas, inclusive em execuções concorrentes. |
| Especificação §5 | Parcelas restauradas mantêm a posição original. A restauração não cria parcela, reserva ou posição nova. |
| Especificação §9.2 e Q-7 | Estorno de produtos, serviço e frete proporcionais, pelos valores registrados, com o acumulado por item e componente. |
| 17.4 | Unidades pagas em caixa invalidada voltam automaticamente, com a prioridade original. |
| Infraestrutura 4.10 | Restauração na apuração, na mesma transação que invalida a caixa, sem esperar o estorno. Na rodada viável, as unidades afetadas dos adimplentes passam a `pendente`, com a reserva zero na rodada apurada. Idempotência pela chave única (parcela, caixa invalidada). |
| Infraestrutura 3.2 | Devolução devida antes do repasse: obrigação financiada pela custódia da mesma rodada. |
| Especificação §12 | Evento "Cancelamento por inadimplência ou caixa incompleta", com os itens afetados, a consequência financeira e o retorno das unidades à fila. |
| Herdado da E04 | `itens_cancelados` com os itens afetados, a consequência financeira e o retorno das unidades à fila. |
| Herdado da E05 | A E11 cria as pendentes (restauração de caixa invalidada, com chave única parcela e caixa). |
| Cenários §16 | 13, 53, 55 (na apuração) e 74 |
| Testes técnicos | T-20 e T-32 |

## Escopo

**Dentro:**
- O registro `RestauracaoDeCaixa`.
- O estorno proporcional por item.
- A restauração das parcelas na fila.
- O aviso ao comprador afetado.

Tudo dentro da transação da apuração, só com o resultado `valida`.

**Fora:**
- A autorização e a execução da devolução (E10-04 a E10-06).
- O atendimento da fila na rodada seguinte (E05-02, de ponta a ponta na E11-08).
- O avanço (E11-06).

## Modelo

**`RestauracaoDeCaixa`** (só inserção):
- `apuracao`;
- `parcela_no_pedido` (um para um, **única**);
- `parcela` (a `ParcelaDeInteresse`);
- `quantidade`;
- `criada_em`.

A unicidade de `parcela_no_pedido` é a chave (parcela, caixa invalidada) da infraestrutura 4.10. A `ParcelaNoPedido` já é única por (item, parcela, caixa), e cada caixa é de um só ciclo.

## Regras

Com `resultado = valida`, para cada pedido pago com unidades em caixas invalidadas, na ordem de `pk` do pedido e do item:

1. **Estorno proporcional:** um `reembolso_parcial(item, quantidade, chave="caixa:<apuracao>:<item>", motivo="caixa_invalidada", autor=SISTEMA)` por item afetado.
   - A quantidade é a soma das unidades do item em caixas invalidadas (E11-03).
   - O cálculo e a obrigação são os da E10-02. Antes da apuração no livro, a obrigação é financiada pela custódia da mesma rodada (E09-06).
   - O valor de produtos é o que a E11-03 descontou do valor válido.
   - A execução fica pendente de autorização na lista de devoluções da E10-07 (grupo "Pendentes de autorização").
2. **Restauração na fila,** para cada `ParcelaNoPedido` do item numa caixa invalidada:
   - uma `RestauracaoDeCaixa`, com a quantidade da `ParcelaNoPedido`;
   - a `ParcelaDeInteresse`: `quantidade_pendente += quantidade`, `situacao = pendente` e `quantidade_reservada = 0`.

   A `sequencia` não muda, e nenhuma parcela é criada.
3. **Reserva zero, inclusive da parte válida:** uma parcela que cruza uma caixa válida e uma invalidada passa a `pendente` com a reserva zero. A parte válida continua só no pedido congelado.
   - **Precedente:** é o mesmo da abertura do pagamento para a parcela com pendente (E08-02): durante o pagamento ninguém reserva nesta rodada, e a contagem de estoque não muda nada.
   - **Restrições:** a da tabela (pendente sem reserva) e a do total (reservado + pendente ≤ original) continuam valendo, porque a quantidade restaurada sai da parte congelada.
4. **Conta que não pode ter interesses:** se o comprador pagante está suspenso ou removido, a parcela não é restaurada, e o estorno é registrado do mesmo jeito.
   - **Motivo:** a suspensão e a remoção removem os interesses e impedem novos (§2, E05-07).
   - **Auditoria:** registra a parcela não restaurada e o motivo.
5. **Sem atender a fila agora:** a rodada continua em `pagamento`, e `alocar_pendentes` não reserva nada nela. As unidades esperam a próxima rodada do fornecedor em interesse (E05-02).
6. **Auditoria:** a da apuração passa a ter, por pedido, os reembolsos (chave, item, quantidade e valores) e as restaurações (`ParcelaNoPedido`, parcela e quantidade).
7. **Aviso `itens_cancelados`** a cada comprador pagante afetado:
   - **título:** "Itens em caixa incompleta: {fornecedor}";
   - **corpo:**
     - por produto: "{quantidade} {unidade} de {produto}";
     - "estavam em caixa que ficou incompleta por falta de pagamento de outro comprador";
     - o valor total do estorno (produtos, serviço e frete): "O estorno de {valor} foi registrado e será feito depois da autorização do administrador";
     - "Essas unidades voltaram para a fila de pendentes do fornecedor, na posição original, e serão reservadas quando houver estoque numa próxima rodada";
   - **link:** `/pedidos/<pk>/`;
   - **chave:** `itens_cancelados:caixa:<apuracao>:<conta>`;
   - na transação da apuração.

## Invariantes

- Para cada `ParcelaNoPedido` de pedido pago em caixa invalidada, há exatamente uma `RestauracaoDeCaixa`, salvo a conta sem interesses.
- A soma dos produtos dos reembolsos `caixa_invalidada` de um pedido é igual ao desconto de valor válido da E11-03.
- O pedido congelado e os itens válidos não mudam.
- Nenhuma reserva nasce na rodada apurada.
- Reservado + pendente ≤ original em toda parcela.

## Casos-limite e concorrência

- **Reexecução da restauração** (T-20, T-32): uma segunda execução do passo sobre a mesma apuração não cria restauração, não muda as quantidades e não cria reembolso. As chaves únicas impedem isso: `RestauracaoDeCaixa` por `ParcelaNoPedido`, e o reembolso por chave (E10-02). A segunda apuração do ciclo já é recusada (E11-01). Por isso a reexecução é provada chamando o passo interno duas vezes.
- **Duas apurações concorrentes:** uma só executa o passo (E11-01, A-14).
- **Comprador pagante suspenso em paralelo com a apuração:** serializados pela trava do fornecedor. Se a suspensão vem antes, a parcela não é restaurada (regra 4). Se vem depois, a parcela restaurada é removida pela suspensão (E05-07), e o reembolso continua.
- **Item inteiro invalidado:** o reembolso do item é o subtotal inteiro, com o serviço e o frete proporcionais.
- **Pedido inteiro invalidado:** os reembolsos dos itens completam o pedido. O último componente é o saldo exato (E10-02).

## Dependências e decisões em aberto

Depende de E11-03, E10-02 e E05. Nenhuma decisão em aberto.
