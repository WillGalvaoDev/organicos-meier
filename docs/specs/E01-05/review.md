# E01-05 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclo Red → Green → Refactor

| Teste | Red (resultado) | Green |
|---|---|---|
| `tests/tecnicos/test_apoio_concorrencia.py` (A-1 a A-7) | coleta falhou: `ModuleNotFoundError: No module named 'tests.apoio.concorrencia'` | `tests/apoio/concorrencia.py`, `ModeloContador` e migração `0004_modelo_contador`: 9 passed |

Refactor: remoção de `noqa` desnecessários e da fixture com `yield` sem teardown (lint). Suíte mantida verde.

## Verificações (final)

```
uv run pytest -q                                  → 111 passed
uv run pytest tests/tecnicos/test_apoio_concorrencia.py -q (5 execuções seguidas) → 9 passed em todas
uv run ruff check .                               → All checks passed
uv run ruff format --check .                      → ok
uv run mypy .                                     → Success: no issues found in 39 source files
manage.py makemigrations --check --dry-run (test) → No changes detected
```

## Decisões técnicas

- Cada thread abre a conexão (`ensure_connection`) antes da barreira de início, então as N conexões coexistem e têm pids distintos (A-2).
- Em tempo esgotado: as barreiras do utilitário são abortadas e as conexões das threads pendentes são fechadas pela thread chamadora (`inc_thread_sharing` + `close`), de modo que não sobram conexões (A-7). A thread pendente é `daemon` e pode continuar bloqueada em uma barreira do próprio teste, sem segurar conexão nem a suíte.
- Tempo limite padrão: 30 s, configurável por `tempo_limite`.
- `executar_em_paralelo` com zero operações devolve lista vazia.
- A-7 conta conexões do usuário no banco de testes via `pg_stat_activity` e compara antes e depois, com espera de até 3 s pelo encerramento no servidor.

## Limitações

- Nenhuma revisão independente feita ainda.
- Uma operação que bloqueia fora de barreira e de chamada ao banco (por exemplo, `time.sleep` longo) continua rodando em segundo plano depois do `TempoEsgotado`; o utilitário não consegue encerrar threads Python.
