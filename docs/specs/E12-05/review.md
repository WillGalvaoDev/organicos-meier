# E12-05 — Registro da implementação (agente 2, 2026-11-01)

Comando: `uv run pytest tests/tecnicos/test_cancelamento_aviso.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-7 (e o arranjo CI movido para `tests/apoio/cancelamento.py`, sem mudar comportamento) | `478a51b` | **Red: 7 failed** (`Notificacao.DoesNotExist`; `_emitir_o_aviso` inexistente) |
| `_avisar_os_compradores`, `_corpo_do_aviso`, `_emitir_o_aviso` na transação do cancelamento | `f95a3ce` | **7 passed**; suíte completa **2871 passed**; `ruff` e `mypy` limpos |

## Decisões técnicas
- A-5: o teste reemite o mesmo conteúdo; o sistema recusa a mesma chave com conteúdo diferente (`ChaveDeEventoReutilizada`), o que é a proteção desejada. Corrigido antes do Green.
- Link de quem tem pedido pago sem saldo novo (A-4): o pedido pago (a spec não define esse caso).
