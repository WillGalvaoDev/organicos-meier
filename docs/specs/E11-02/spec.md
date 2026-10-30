# E11-02 — Perda dos itens do fornecedor pelos inadimplentes

Fatia 2 de 8 da milestone **E11 — Apuração final e fila de pendentes**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E11-01.

## Contexto e objetivo

Na apuração, o comprador que não pagou perde todos os itens daquele fornecedor no carrinho, inclusive as reservas e as posições na fila de pendentes (§8.2, passo 3.2). Itens dele de outros fornecedores não mudam.

Esta fatia acrescenta esse passo à transação da `iniciar_apuracao` (E11-01) e o aviso de cancelamento ao inadimplente.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §8.2, passo 3.2 | Compradores inadimplentes perdem todos os itens daquele fornecedor no carrinho, inclusive as reservas e as posições na fila. |
| Especificação §5 e §5.2 | A perda de itens por inadimplência libera a reserva quando a rodada continuar utilizável. Inadimplentes não entram na fila de pendentes. |
| 17.4 | Inadimplentes perdem os itens daquele fornecedor. |
| Infraestrutura 4.10 | Inadimplentes perdem todas as parcelas daquele fornecedor (situação `removida`), inclusive as pendentes, com a liberação das reservas na mesma transação. A liberação aciona `alocar_pendentes` quando a rodada está em interesse. |
| Especificação §12 | Evento "Cancelamento por inadimplência ou caixa incompleta": itens afetados e consequência financeira. |
| Herdado da E04 | `itens_cancelados` com `emitir_evento`, na transação do fato, com chave derivada do fato. |
| Herdado da E05 | A E11 libera as reservas dos inadimplentes chamando `_alocar_produto` quando a rodada aceita reservas. |
| Cenários §16 | 54 e 79 |

## Escopo

**Dentro:**
- A remoção das parcelas dos inadimplentes, dentro da transação da apuração.
- O aviso `itens_cancelados` ao inadimplente cancelado pela apuração.

**Fora:**
- A liberação para a fila quando a rodada volta para interesse: ela acontece pela `alocar_pendentes` do retorno (E11-05), depois desta remoção.
- O comprador que pagou.

## Regras

- **Inadimplente:** o comprador de um pedido não pago da apuração (E11-01), qualquer que seja a situação anterior do pedido (`aguardando_pagamento`, ou cancelado por suspensão ou remoção).
- **Parcelas removidas:**
  - **quais:** todas as `ParcelaDeInteresse` do inadimplente em produtos **do fornecedor da rodada**, nas situações `ativa`, `em_pedido` e `pendente`;
  - **produtos:** inclusive os de fora do estoque da rodada, como pendentes antigos de um produto que esta rodada não inclui;
  - **efeito:** cada uma passa a `removida`, com `quantidade_reservada` e `quantidade_pendente` zeradas;
  - **o que não muda:** a sequência e a quantidade original;
  - **outros fornecedores:** as parcelas não mudam.
- **Travas:** os produtos do fornecedor e as parcelas de cada um, inclusive os de fora do estoque da rodada, já estão travados pela E11-01, por `pk` e antes das `SituacaoDoPedido`. Esta fatia não trava mais nada. Toda operação de interesse trava o fornecedor antes dos produtos, por isso a ordem entre produtos não cria impasse.
- **Reserva liberada:**
  - com a rodada em `pagamento`, ninguém reserva, e a fila não é atendida agora (`alocar_pendentes` não faz nada fora de interesse e fechamento);
  - no retorno ao interesse (E11-05), a `alocar_pendentes` do retorno atende a fila com o estoque liberado.
- **Composição do pedido:** `ParcelaNoPedido` e os itens do pedido não mudam (§7.1). As unidades do inadimplente continuam registradas no pedido cancelado, e é por elas que a E11-03 identifica as caixas incompletas.
- **Auditoria:** a da apuração (E11-01) passa a listar, por inadimplente, os `pk` das parcelas removidas e as quantidades que cada uma tinha.
- **Aviso `itens_cancelados`:**
  - **quem recebe:** cada comprador cujo pedido foi cancelado **por esta apuração** (motivo `inadimplencia`). Quem já tinha o pedido cancelado por suspensão ou remoção não recebe, porque a moderação já tratou a conta (E08-06);
  - **título:** "Pedido cancelado: {fornecedor}";
  - **corpo:** "Seu pedido {pk} da rodada de {fornecedor} foi cancelado porque o pagamento não foi identificado até o fim do prazo. Os itens desse fornecedor saíram do seu carrinho, inclusive reservas e quantidades pendentes. Nada foi cobrado neste pedido.";
  - **link:** `/pedidos/<pk>/`;
  - **chave:** `itens_cancelados:inadimplencia:<pedido>:<conta>`;
  - na transação da apuração.

## Invariantes

- Depois da apuração, nenhum inadimplente tem parcela `ativa`, `em_pedido` ou `pendente` em produto do fornecedor.
- A sequência das parcelas restantes de outros compradores não muda.
- Nenhuma parcela é criada nem apagada.

## Casos-limite

- **Inadimplente com pendente antigo do fornecedor**, de uma rodada anterior: removido também (cenário 54, "inclusive posições na fila").
- **Inadimplente com parcelas em outro fornecedor:** intocadas (cenário 54).
- **Remoção de pendentes pelo comprador em paralelo com a apuração:** a remoção trava o fornecedor do produto antes das parcelas (E05). As duas se serializam. O resultado final é o mesmo em qualquer ordem: a parcela termina `removida`, com quantidades zero.

## Dependências e decisões em aberto

Depende de E11-01 e de E05. Nenhuma decisão em aberto.
