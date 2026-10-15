# E01-03 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclos Red → Green → Refactor

| Ciclo | Teste | Red (resultado) | Green |
|---|---|---|---|
| 1 | `tests/tecnicos/test_nucleo_tempo.py` (A-1 a A-8) | coleta falhou: `ModuleNotFoundError: No module named 'apps.nucleo.tempo'` | `apps/nucleo/tempo.py` e fixture `relogio` em `tests/conftest.py` |
| 2 | `tests/tecnicos/test_nucleo_tempo_persistencia.py` (A-9) | coleta falhou: `ImportError: cannot import name 'ModeloInstante' from 'tests.apoio.models'` | `ModeloInstante` e migração `0002_modelo_instante` em `tests/apoio` |
| 3 | `tests/tecnicos/test_regras_estaticas.py` (A-10) | `uv run pytest tests/tecnicos/test_regras_estaticas.py` → 2 failed (`assert 0 != 0`: ruff sem a regra `DTZ` aprovava `datetime.now()` e `utcnow()`), 1 passed (caso com fuso) | `DTZ` acrescentado a `[tool.ruff.lint] select` no `pyproject.toml`: 3 passed |

Refactor: remoção de `noqa` desnecessário; suíte completa mantida verde.

## Verificações (final)

```
uv run pytest -q             → 71 passed
uv run ruff check .          → All checks passed
uv run ruff format --check . → files already formatted
uv run mypy .                → Success: no issues found
```

## Decisões técnicas

- Fixture `relogio` usa `time-machine` (dependência de desenvolvimento já travada), com `tick=False`.
- `congelar` recusa instante sem fuso (`InstanteSemFuso`).
- `somar_horas` normaliza para UTC antes de somar.
- `agora()` usa `datetime.now(UTC)`, patcheado pelo `time-machine`; nada consulta `now()` do Postgres.
- A-10 verificado por teste automatizado que roda o ruff com a configuração do projeto sobre trechos temporários.

## Limitações

- Nenhuma revisão independente feita ainda.
