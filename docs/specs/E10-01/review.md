# E10-01 — Revisão independente

## Evidências de TDD (preenchido pelo agente 2)

Red no commit `ff357ee`, comando
`uv run pytest tests/tecnicos/test_financeiro_conciliacao.py -q -p no:cacheprovider` (arquivo inteiro, sem `-k`): **9 failed, 20 passed**.
Green no commit seguinte (produção em `apps/financeiro/conciliacao.py`): **29 passed**.

| Critério | Teste | Red: falha observada | Green |
|---|---|---|---|
| A-1 | `test_ajuste_antigo_nao_repete_a_diferenca_nos_dias_seguintes` | `Decimal('10.00') == Decimal('0.00')` (diferença de D2) | passa |
| A-2 | `test_aporte_sem_deposito_nao_repete_a_diferenca_nos_dias_seguintes` | `Decimal('-100.00') == Decimal('0.00')` | passa |
| A-3 | `test_pagamento_sem_entrada_nao_repete_a_diferenca_nos_dias_seguintes` | `Decimal('125.00') == Decimal('0.00')` | passa |
| A-4 | `test_aporte_cujo_deposito_aparece_depois_e_resolvido` | o alerta `livro:sem-deposito` continua aberto | passa |
| A-5 | `test_so_a_parte_nova_do_dia_entra_na_diferenca_e_nos_alertas` | `Decimal('10.00') == Decimal('0.00')` | passa |
| A-6 | `test_diferenca_nova_alem_da_pendencia_antiga_abre_so_a_parte_nova` | `Decimal('15.00') == Decimal('5.00')` | passa |
| A-7 | `test_entrada_lancada_depois_de_t_de_d1_nao_entra_na_soma_de_d2` | **não houve Red**: já passava, é regressão (a entrada de 23:30 de D1 não gera alerta, porque a classificação do dia usa o livro na execução) | passa |
| A-8 | `test_movimento_na_lista_do_dia_seguinte_nao_entra_duas_vezes` | `Decimal('10.00') == Decimal('0.00')` | passa |
| A-9 | `test_alerta_sem_data_nao_entra_na_soma_e_nao_derruba_a_conciliacao` | o log `warning` não existia | passa |
| A-10 | `test_dias_pendentes_nao_abrem_alerta_de_saldo_pela_pendencia_antiga` | `'divergente' == 'ok'` em D2, com `saldo:*` abertos | passa |

Refactor: nenhum além do `ruff format`.

Decisões técnicas (derivadas da especificação, sem escalar):

- O alerta de pagamento sem conciliação não guarda `id_movimento`; a pendência é montada com a chave do alerta (`id_externo`) e comparada, no recorte do dia, apenas com movimentos do tipo `pagamento`.
- Um tipo de movimento desconhecido nos dados do alerta é tratado como `outro`: nunca tem par e nunca é resolvido.
- Os alertas lidos uma vez, antes da transação; a resolução ocorre na transação da conciliação, depois dos alertas do dia.
- No A-7, a entrada nasce às 23:30 de D1 e a conciliação de D1 só roda depois da meia-noite; por isso o alerta nem chega a abrir. A especificação fala em alerta "já resolvido pelo `registrar_entrada`": o resultado observável (diferença 0,00 e nenhum alerta aberto em D2) é o mesmo e é o que o teste afirma.

## Verificações executadas (preenchido pelo agente 2)

```
uv run pytest tests/tecnicos/test_financeiro_conciliacao.py -q -p no:cacheprovider   # 29 passed
uv run mypy apps/financeiro/conciliacao.py                                          # sem erros
uv run ruff check / ruff format --check nos dois arquivos                            # limpos
```

A suíte completa roda ao fim de cada fatia (ver o registro da E10 no último `review.md`).

## Revisão (agente 3)

| Achado | Classificação (bloqueador, importante, melhoria) | Evidência | Requisito |
|---|---|---|---|
| | | | |

**Decisão:** pendente

## Revalidação

—
