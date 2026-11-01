# E12-05 — Registro da implementação (agente 2, 2026-11-01)

Comando: `uv run pytest tests/tecnicos/test_cancelamento_aviso.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Testes A-1 a A-7 (e o arranjo CI movido para `tests/apoio/cancelamento.py`, sem mudar comportamento) | `478a51b` | **Red: 7 failed** (`Notificacao.DoesNotExist`; `_emitir_o_aviso` inexistente) |
| `_avisar_os_compradores`, `_corpo_do_aviso`, `_emitir_o_aviso` na transação do cancelamento | `f95a3ce` | **7 passed**; suíte completa **2871 passed**; `ruff` e `mypy` limpos |

## Decisões técnicas
- A-5: o teste reemite o mesmo conteúdo; o sistema recusa a mesma chave com conteúdo diferente (`ChaveDeEventoReutilizada`), o que é a proteção desejada. Corrigido antes do Green.
- Link de quem tem pedido pago sem saldo novo (A-4): o pedido pago (a spec não define esse caso).


## Parecer independente — agente 3 — 2026-11-01

Base auditada: `8e236e5`, branch `e12-implementacao`, comparada à E11 integrada em `d098654`. Funcional v1.7, infraestrutura v1.8, especificações e critérios das sete fatias lidos antes da avaliação da implementação. Conteúdo anterior preservado integralmente. Evidências, veredito da etapa e reproduções no [parecer consolidado E12-07](../E12-07/review.md).

**REPROVADO — R02 (importante).** A-1 a A-7 passam, mas não cobrem cancelamento sem reembolso após retorno ao interesse. Um comprador com pedido pago anterior e devolução de mínimo pendente recebe o texto de quem não tinha pedido pago. `pagos` e `pedidos` só contemplam a abertura vigente; `sem_reembolso` só é preenchido no ramo com reembolso. Referência: regra 4 (texto para pagante sem reembolso), funcional §7.2/§12. Corrigir a classificação histórica dos destinatários já afetados pelo cancelamento, sem criar obrigação nova nem autorizar a anterior. Prova no consolidado.
