# E13-04 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_pedido_formal_telas.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `918e29e` | **17 failed, 1 passed** (404: página e rota inexistentes). O A-15 já passava: o 404 sem pedido formal vale também para a rota ainda inexistente; a prova do 404 da rota existente veio no Green |
| Green | `5521462` | **18 passed**; regressão `test_apuracao_telas.py` e `test_cancelamento_telas.py`: 29 passed |

## O que foi feito
- Página `administracao/rodadas/<pk>/pedido-formal/` (`rodadas_pedido_formal`), rota `.../reenviar/` (`rodadas_pedido_formal_reenviar`) e o bloco "Pedido formal" na página da rodada. Contexto em `apps/pedidos/pedido_formal_tela.py`; token novo (`uuid4`) a cada carregamento.
- Um token de outro pedido formal (`token_invalido` do serviço) responde 400 "Recarregue a página e tente de novo.", como o token ausente ou malformado.
