# E13-03 — Registro da implementação (agente 2, 2026-11-04)

Comando: `uv run pytest tests/tecnicos/test_pedido_formal_reenvio.py` (arquivo inteiro, sem `-k`).

| Etapa | Commit | Resultado |
|---|---|---|
| Red | `590cfbc` | **19 failed**: o módulo `apps.pedidos.reenvio_do_pedido_formal` não existe |
| Green | `9ab5fed` | **19 passed** (inclui A-15 a A-17 com transações reais) |

## Ponto para o especificador
- **Chave da auditoria.** O critério A-14 pede a auditoria com "o token". O filtro de segredos da auditoria (`registrar_auditoria`) recusa qualquer chave com o termo `token` (`ValueError: chave com termo reservado a segredo`). O valor (o UUID do acionamento) é gravado sob a chave `acionamento`. O token do reenvio não é segredo (é só um identificador de idempotência), mas mudar o filtro seria alterar a regra da E01. O teste A-14 confere `{"pedido_formal", "numero", "resultado", "acionamento"}`.

## Decisões técnicas
- `pode_reenviar` e a conferência prévia leem o estado gravado sem trava; a conferência sob as trava repete a leitura. Durante o ciclo automático o reenvio é recusado sem esperar, e entre reenvios a trava do envio é esperada (`select_for_update(of=("self",))`).
- `IntegrityError` no token: a transação é desfeita e a tentativa existente é relida (regra 11).
