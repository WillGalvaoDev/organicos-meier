# E14-04 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_liberacao_da_retirada.py tests/aceitacao/test_cenario_22_liberacao.py` (arquivos inteiros, sem `-k`).

| Etapa | Resultado |
|---|---|
| Red | **28 failed**, todos por `ModuleNotFoundError: apps.pedidos.liberacao_da_retirada` |
| Green | **28 passed**; junto com as E14-01 e E14-02, **86 passed**; `ruff` e `mypy apps tests/apoio` limpos |

## O que foi feito
- `LiberacaoDaRetirada` (só inserção, migração `0019`, `CHECK` do prazo depois da liberação), `liberar_retirada`, `liberacao_da_rodada`, `LiberacaoRecusada` em `apps/pedidos/liberacao_da_retirada.py`.
- Travas pelo `_travar` da E11-01 e pelos compradores de `_compradores_envolvidos` da E12 (mesma ordem do cancelamento); o instante é lido depois das travas.
- As parcelas `em_pedido` passam a `removida`/`pendente` (regra 6 da E12-01), sem criar parcela nem mudar sequência; avisos `retirada_liberada` só a quem tem saldo (suspenso recebe, removido não); auditoria `rodada.liberar_retirada`.
- A recusa do cancelamento da rodada liberada (`rodada_encerrada`) já existia na E12; A-14 e A-21 a comprovam sem código novo.

## Decisão técnica registrada (tensão entre a regra 2 e o A-22)
- A regra 2 diz que a conferência prévia, sem trava, aplica "a etapa e as condições da regra 4". O critério A-22 exige que, com a ocorrência que completa o recebimento ainda não commitada, a liberação **espere** a trava e seja aceita. Uma conferência prévia de `recebimento_pendente` recusaria de imediato e o A-22 não passaria.
- Implementei a prévia só com a **etapa** (`ja_liberada`/`etapa`); o endereço e o recebimento são conferidos sob as travas. Os testes A-5, A-10 e A-22 cobrem os dois lados. Se o especificador quiser a prévia completa, o A-22 precisa mudar; deixo o ponto para o agente 3 confirmar.

## Outras notas
- A auditoria grava `liberada_em` e `prazo_final` como `datetime` (o serializador JSON os grava em UTC com `Z`).
- `tests/aceitacao/test_cenario_22_liberacao.py` foi escrito junto do Red (falhava pelo mesmo motivo).
