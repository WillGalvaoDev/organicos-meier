# E12-05 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação. Arranjos CI (E12-01) e AP (E12-02). O cancelamento é feito pelo serviço, fora de transação.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §12, cenário 43 | positivo | AP; X pago; Y sem pagamento | cancelar com reembolso e a mensagem "Fornecedor sem colheita" | A recebe um `rodada_cancelada` com o título "Rodada cancelada: F", o corpo com "foi cancelada pelo administrador", "94,35", "devolvido integralmente" e "Mensagem do administrador: Fornecedor sem colheita", o link `/pedidos/<X>/` e a chave `rodada_cancelada:<cancelamento>:<A>`; B recebe "Seu pedido foi cancelado e nada foi cobrado." e "Reembolso integral para quem pagou.". **Red esperado:** nenhuma notificação |
| A-2 | §12, cenário 44 | positivo | AP; X pago | cancelar sem reembolso, sem mensagem | A recebe "O cancelamento não inicia novas devoluções. As devoluções já devidas continuam em andamento."; sem "devolvido integralmente"; sem a frase da mensagem; B recebe "Sem novas devoluções." |
| A-3 | Regra 2 | positivo | CI | cancelar sem reembolso | A, B e D recebem o aviso, com "Seus interesses nesta rodada foram removidos." e o link `/carrinho/`; D também com a frase da fila de pendentes; C (só pendente) não recebe |
| A-4 | Regra 4 | positivo | o arranjo do E12-03 A-8 (X sem saldo novo) | cancelar com reembolso | A recebe "As devoluções já devidas do seu pedido continuam em andamento." e nenhum valor de devolução |
| A-5 | Idempotência | negativo | o A-1 | emitir o aviso de novo pela função interna, com a mesma chave | um aviso por comprador |
| A-6 | Privacidade | negativo | o A-1 | ler os corpos de A e de B | nenhum com o nome do outro, o mínimo ou o total do outro pedido |
| A-7 | E04 | positivo | o A-1 com o envio de e-mail falhando | processar a fila de notificações | o cancelamento e os reembolsos intactos; o aviso no site presente; a falha registrada pela E04 |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-7 | `tests/tecnicos/test_cancelamento_aviso.py` |

## Correção da revisão: R02 (2026-11-01)

Arranjo AP-R: o da E12-02 (correção R03). X é o pedido pago de A no ciclo 1, com a devolução de mínimo pendente. Depois do retorno, A tem as parcelas restauradas (E11-05).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-8 | R02, regras 2-A e 4 | positivo | AP-R | `cancelar_rodada(..., com_reembolso=False)` | A recebe um `rodada_cancelada` com "O cancelamento não inicia novas devoluções. As devoluções já devidas continuam em andamento."; sem "Seus interesses nesta rodada foram removidos." nem "Sem novas devoluções."; o link `/pedidos/<X>/`; nenhum `Reembolso`, `ObrigacaoComComprador` ou `MovimentoFinanceiro` novo. **Red esperado:** a prova `test_aviso_sem_reembolso_reconhece_pedido_pago_de_ciclo_anterior` do parecer falhando no corpo |
| A-9 | R02, regras 2-A e 4 | positivo | AP-R | `cancelar_rodada(..., com_reembolso=True)` | A recebe "As devoluções já devidas do seu pedido continuam em andamento.", sem valor de devolução; o link `/pedidos/<X>/` |
| A-10 | R02, regra 2 | positivo | AP-R com A suspensa depois de pagar X e antes da apuração: no retorno, as reservas de A não são restauradas (conta impedida, E11-05 regra 2) e nenhuma parcela de A é alterada pelo cancelamento | `cancelar_rodada(..., com_reembolso=False)` | A recebe o aviso como no A-8 (destinatário por ter pedido pago na rodada); um comprador com só pendente na fila do fornecedor, sem pedido, continua sem aviso |
| A-11 | R02, regra 4 | positivo | AP-R; no ciclo 2, a rodada levada ao pagamento com um pedido de A `aguardando_pagamento` | `cancelar_rodada(..., com_reembolso=False)` | A recebe, nesta ordem, "Seu pedido do ciclo atual foi cancelado e nada foi cobrado nele." e "O cancelamento não inicia novas devoluções. As devoluções já devidas continuam em andamento."; o link do pedido do ciclo 2 |

A prova `test_aviso_sem_reembolso_reconhece_pedido_pago_de_ciclo_anterior` do parecer tem de passar como está.

| Critério | Arquivo de teste |
|---|---|
| A-8 a A-11 | `tests/tecnicos/test_cancelamento_aviso.py` |
