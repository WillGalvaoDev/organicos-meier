# E11-02 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação. Arranjo AP como na E11-01 (`acceptance.md`).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | §8.2 3.2, cenário 54 | positivo | AP-viável; X pago, Y sem pagamento | `iniciar_apuracao` | as três parcelas de B no fornecedor (P1 5, P2 6, P2 2), que estavam `em_pedido`, passam a `removida`, com reservado e pendente zero, sequência e quantidade original iguais. **Red esperado:** as parcelas de B continuam `em_pedido` |
| A-2 | Cenário 54, 79 | positivo | o A-1, com B tendo também uma parcela `pendente` de 3 unidades de um produto P3 do mesmo fornecedor, fora do estoque da rodada, de sequência anterior | `iniciar_apuracao` | a parcela de P3 `removida`, com pendente zero; nenhuma parcela de B na fila do fornecedor (cenário 79) |
| A-3 | Cenário 54 | positivo | o A-1, com B tendo uma parcela `ativa` de 2 unidades num produto de outro fornecedor G, cuja rodada está em interesse | `iniciar_apuracao` | a parcela de G intacta (situação, quantidades e sequência) |
| A-4 | §8.2 3.2 | positivo | o A-1 | inspecionar as parcelas de A | iguais às de antes da apuração (`em_pedido`, com as mesmas quantidades) |
| A-5 | §7.1 | positivo | o A-1 | comparar `ParcelaNoPedido` e itens do pedido Y | iguais, e nenhuma linha nova |
| A-6 | §12, E04 | positivo | o A-1 | inspecionar as notificações | B recebe um `itens_cancelados` com o título "Pedido cancelado: F", o corpo com o número de Y e "Nada foi cobrado neste pedido", o link `/pedidos/<Y>/` e a chave `itens_cancelados:inadimplencia:<Y>:<B>`; A não recebe `itens_cancelados` por inadimplência. **Red esperado:** nenhuma notificação |
| A-7 | Herdado E08 | positivo | AP-viável; Y cancelado por suspensão de B antes da apuração | `iniciar_apuracao` | as parcelas de B `em_pedido` passam a `removida`; B não recebe `itens_cancelados` da apuração |
| A-8 | Auditoria | positivo | o A-2 | ler a auditoria `rodada.apuracao_final` | por B: os `pk` das quatro parcelas removidas, com as quantidades reservadas e pendentes que tinham |
| A-9 | Idempotência | negativo | o A-1 | `iniciar_apuracao` de novo | `ja_apurada`; nenhuma notificação nova |
| A-10 | Concorrência, §5.2 | concorrência | o A-2 | `remover_pendente(B, P3, 1)` em paralelo com a apuração, com a apuração pausada depois de remover as parcelas e antes do commit | a remoção espera a apuração; depois, recebe a recusa de quem não tem pendente (`RemocaoAcimaDoPendente`), ou nada a remover; a parcela termina `removida`, com quantidades zero |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-9 | `tests/tecnicos/test_apuracao_inadimplentes.py` |
| A-10 | `tests/tecnicos/test_apuracao_inadimplentes.py`, com transações PostgreSQL reais |

## Ajuste de redação: A-4 e A-6 diante das fatias seguintes (2026-11-01)

Origem: ponto do implementador, "Conflito entre critérios de fatias" (`docs/specs/E11-04/review.md`).

O A-4 e o A-6 foram escritos para o estado da E11-02. As fatias seguintes mudam parcelas e avisos de A. Os ajustes que o implementador fez nos testes ficam **aceitos**, sem afrouxar asserção:
- **A-4:** passa a conferir a parcela de A em P1, que nenhuma fatia seguinte toca. A de P2 passa a `pendente` na E11-04 e a `ativa` na E11-05.
- **A-6:** "A não recebe `itens_cancelados` por inadimplência" é conferido pela chave `itens_cancelados:inadimplencia:`. A recebe, na E11-04, o `itens_cancelados` de caixa incompleta, com outra chave.
