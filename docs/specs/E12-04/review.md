# E12-04 — Registro da implementação (agente 2, 2026-11-01)

Comando: `uv run pytest tests/tecnicos/test_pagamento_depois_do_cancelamento.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-8 | `d23dbd5` | **Red: 6 failed, 2 passed.** A-1, A-3, A-4, A-5, A-6: `ValueError: not enough values to unpack` (nenhum alerta `pagamento_depois_do_cancelamento`; o resto do A-1 já valia); A-2: `'pago' == 'cancelado'` (Y quita, o Red esperado). **Passaram de primeira (regressão):** A-7 e A-8 |
| Regra 1 em `_motivo_da_devolucao`, tipo de alerta crítico (migração financeiro 0016), `_alertar_o_pagamento_depois_do_cancelamento` na entrada para devolução | `94ce35d` | **8 passed**; suíte completa **2864 passed**; `ruff`, `mypy`, `makemigrations --check` limpos |

## Decisões técnicas
- A regra vale depois de `valor_divergente`, `iniciado_fora_do_prazo`, `aprovado_apos_a_margem` e `duplicidade`: com `CancelamentoDaRodada` na rodada, o motivo é `pedido_cancelado`.
- O alerta abre junto com a obrigação (`nova`), chave `id_externo`, ao lado dos alertas do motivo.
- O alerta não é resolvido sozinho quando a devolução conclui (a spec só manda o administrador resolver); a regra de resolução automática dos outros motivos não foi estendida. **Ponto para o especificador.**
