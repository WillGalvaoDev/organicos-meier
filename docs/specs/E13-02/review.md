# E13-02 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_pedido_formal_envio.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `594fcaf` | **17 failed**: o módulo `apps.pedidos.envio_do_pedido_formal` não existe |
| Green | `4568f45` | **17 passed** (inclui A-11 e A-12 com transações reais) |
| Refactor | `002c386` | `__all__` do módulo (o mypy recusava `modulo.enviar_email` nos testes) e tipo de `estado_do_envio`; suíte do arquivo verde |

## O que foi feito
- `TentativaDeEnvioDoPedidoFormal` (só inserção, com as restrições do `spec.md`), `processar_pedidos_formais()` e a tarefa periódica por minuto (`enviar_pedidos_formais`, com `queueing_lock`).
- Travas: o `EnvioDoPedidoFormal` com `select_for_update(skip_locked=True, of=("self",))` e a `Rodada` com `no_key=True`. O `of=("self",)` evita travar o pedido formal e o fornecedor junto.
- A consulta ao provedor vem antes, fora de transação; falha dela reagenda em 5 minutos sem tentativa. A rodada cancelada é conferida antes da consulta (sem consulta inútil) e de novo sob a trava.

## Decisões técnicas
- O aviso `falha_no_pedido_formal` junta as frases das tentativas num só texto, separadas por espaço; o link é uma string (a página só nasce na E13-04).
- A-17 (log): a captura do teste inclui uma falha de consulta no meio do ciclo e confere que nenhum registro leva o destino, o assunto ou o corpo.
