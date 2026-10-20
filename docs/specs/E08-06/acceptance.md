# E08-06 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Valem as regras de prevenção das correções E05-R04 (E05-01) e E06-R05 (E06-05): Red com caminhos explícitos de arquivos inteiros, sem `-k`, e tabela de cobertura do Red antes do Green. Os testes que usam o simulador declaram os dois bancos (E07-R03).

**Arranjo comum, salvo indicação:**

- `T0` = 2026-11-02 13:00 UTC; relógio em 2026-11-02 16:00 UTC;
- o comprador A com dois pedidos, em fornecedores diferentes:
  - `X`, `aguardando_pagamento`, com uma tentativa criada e a cobrança `P` pendente;
  - `Z`, `pago`;
- fixture `simulador_pagamentos` ativa.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §2, herdado da E02 | positivo | — | `suspender(admin, A)` | `X` `cancelado`, com `cancelado_em` 16:00 e motivo `suspensao`; `Z` continua `pago`; uma chamada `cancelar_cobranca` com alvo `t<tentativa>:suspensao`; auditoria `pedido.cancelar`; a composição, as caixas e as parcelas de `X` não mudaram |
| A-2 | Spec §2 | positivo | o A-1 | `processar_chamadas()` | a cobrança `P` `cancelado`; o registro `cancelado`; `X` continua `cancelado`; nenhum destino |
| A-3 | Herdado da E05 | positivo | — | `remover(admin, A)` | `X` `cancelado`, com motivo `remocao_da_conta`; alvo `t<tentativa>:remocao_da_conta`; `Z` continua `pago` |
| A-4 | Spec §8.3, E08-04 | positivo | `P` aprovado no provedor às 15:30, sem aviso entregue | a suspensão às 16:00; depois, o aviso e o processamento às 16:05 | `X` `pago`; auditoria `pedido.quitar` com `cancelamento_sem_efeito` `suspensao`; um `pagamento_confirmado` |
| A-5 | Spec §8.3, E08-04 | negativo | — | a suspensão às 16:00; `aprovar(P, em=16:10)` antes de o cancelamento ser processado; o aviso e o processamento | destino `devolucao`, `pedido_cancelado`; `X` continua `cancelado` |
| A-6 | Spec da fatia | positivo | o A-1 | `reativar(admin, A)`; A abre `/pedidos/<X>/` e faz `POST /pedidos/<X>/pagar/` | `X` continua `cancelado`; a página mostra "Cancelado"; o `POST` recebe 409 com "Este pedido foi cancelado e não pode mais ser pago." |
| A-7 | Spec §2 | positivo | o A-1 | A (suspenso) abre `/pedidos/` | vê `X` como "Cancelado" e `Z` como "Pago", sem botão de pagar |
| A-8 | Spec da fatia | negativo | — | `cancelar_pedidos_nao_pagos` fora de transação; com motivo `"outro"`; com uma conta de fornecedor | `TransactionManagementError`; `ValueError`; 0, sem gravar nada |
| A-9 | Spec da fatia | negativo | um receptor de teste depois do de pedidos que levanta `RuntimeError` na suspensão | `suspender(admin, A)` | a exceção chega a quem chamou; a conta continua ativa; `X` continua `aguardando_pagamento`; nenhuma chamada nova |
| A-10 | Spec da fatia | positivo | A sem pedidos; B com um pedido `cancelado` | suspender A; suspender B de novo depois de reativar | 0 pedidos cancelados nos dois; nada muda |
| A-11 | Spec da fatia | concorrência | — | uma thread suspende A e outra faz `pedir_pagamento(A, X)` sem tentativa aberta (sem a tentativa do arranjo), nas duas ordens, com a primeira segurando a trava da situação até a segunda aparecer esperando | pagamento antes: a tentativa nasce e logo recebe o cancelamento com alvo `:suspensao`; suspensão antes: o pagamento recebe `PagamentoRecusado` (`pedido_cancelado` ou `conta_inativa`) e nenhuma tentativa nasce; nas duas, `X` termina `cancelado` |
| A-12 | Correção E07-R01 | concorrência | uma chamada `cancelar_cobranca` com alvo `t<tentativa>:prazo` em execução, parada no `executar` | a suspensão de A noutra thread | a suspensão termina sem esperar a chamada em andamento; nenhum impasse |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-10 | `tests/tecnicos/test_pedidos_moderacao.py` |
| A-1 | também marcado `acceptance`, com o comentário `cenário 19 (pedidos)` |
| A-11, A-12 | `tests/tecnicos/test_pedidos_concorrencia.py` (marcador `concorrencia`, `django_db(transaction=True)`) |
