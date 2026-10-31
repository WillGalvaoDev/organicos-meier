# E11-08 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

Esta fatia é de testes de ponta a ponta (spec: "Verde de primeira" e "Correção"). Arquivo: `tests/tecnicos/test_fila_ponta_a_ponta.py`. Arranjo FP montado pelos serviços reais (fechamento, abertura do pagamento, pagamentos pelo simulador, apuração, aprovação; R2 aberta pelo serviço, múltiplo de P retirado e P incluído com o limite do cenário).

| Etapa | Commit | Resultado |
|---|---|---|
| Primeira execução do arquivo inteiro | `ARQUIVO` | **4 failed** na montagem do arranjo: `OrdemDeTravasViolada: a conta 6 foi pedida depois da 11` em `iniciar_apuracao` → `_estornar_e_restaurar` → `reembolso_parcial`. **Achado real das E11-04 e E11-05**: com dois pagantes com estorno (A e C) na mesma apuração, cada reembolso travava as contas do livro-razão separadamente, e a segunda chamada pedia contas de `pk` menor depois da maior. Os testes dessas fatias só tinham um pagante com estorno |
| Testes do defeito nos arquivos da E11-04 e da E11-05 (`test_dois_pagantes_com_estorno_na_mesma_apuracao`, `test_dois_pagantes_recebem_a_devolucao_integral_na_mesma_apuracao`) | `3066566` | **Red: 2 failed** (`OrdemDeTravasViolada`) |
| `contas_das_obrigacoes` (livro-razão) e `_travar_as_contas_das_devolucoes` (apuração): o conjunto das contas de todos os pagantes é travado de uma vez antes do primeiro estorno | commit da fatia | **47 passed** (E11-04, E11-05 e E11-08) |

Execução final do arquivo da E11-08 (`uv run pytest tests/tecnicos/test_fila_ponta_a_ponta.py`): **14 passed**. Depois do conserto acima, todos os critérios A-1 a A-13 passaram **sem mudança de produção específica da fila**: são regressões da E05 (verde de primeira), não Red. Ajustes que fiz nos próprios testes, sem afrouxar asserções: o campo `devido` (propriedade) trocado pelos componentes da obrigação; o ponto de pausa das corridas A-4 e A-10 passou a ser `receptores._alocar_produto` (o receptor importa a função pelo nome); `QuantidadeRecusada` no lugar de `Exception` no A-8.

## Decisões técnicas

- **Adição sem estoque é recusada** (`EstoqueInsuficiente`), como já faz a E05: A-2, A-4 e A-11 afirmam a recusa de D e de E (a spec aceita "recusada ou limitada").
- **A-9:** a rota recebe o `pk` de um produto; um `pk` de `ItemDoPedido` não corresponde a produto (404/recusa) e Q só tem parcela `em_pedido` (nada a remover). Afirmo que os pedidos, os reembolsos e a parcela de A em Q ficam iguais.
- A-4, A-10 e A-11 usam a `Corrida` pausando A depois do atendimento da fila e verificam que B esperou a trava (`b_esperou`).

## Riscos remanescentes e limites de verificação

- A parte do pedido formal do T-47 fica para a E13 (spec). O encerramento da rodada que tira as parcelas `em_pedido` da contagem de `total_reservado` é da E14 (registro herdado).
