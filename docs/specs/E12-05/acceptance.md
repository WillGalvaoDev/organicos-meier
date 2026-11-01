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
