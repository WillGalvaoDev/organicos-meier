# E01-02 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclos Red → Green → Refactor

| Ciclo | Teste | Red (comando e resultado) | Green | Refactor |
|---|---|---|---|---|
| 1 | `tests/tecnicos/test_nucleo_valores.py` (A-1 a A-15, A-18) | `uv run pytest tests/tecnicos/test_nucleo_valores.py -q` → `ModuleNotFoundError: No module named 'apps.nucleo'`, 1 error na coleta | `apps/nucleo/valores.py`: 41 passed | import de `localcontext` no topo; `InvalidOperation` tratado em `eh_multiplo`; 41 passed |
| 2 | `tests/tecnicos/test_nucleo_campos_decimais.py` (A-16, A-17, A-19, A-20) | `uv run pytest tests/tecnicos/test_nucleo_campos_decimais.py -q` → `ImportError: cannot import name 'CampoDinheiro' from 'apps.nucleo.valores'` | `CampoDinheiro`, `CampoQuantidade`, app `tests/apoio`, migração `0001_initial`: suíte 50 passed | `ruff` limpo; migrações excluídas do lint; 50 passed |

Os testes de apoio (`tests/apoio/models.py`) foram escritos junto do teste do ciclo 2, antes dos campos.

## Verificações (final)

```
uv run pytest -q          → 50 passed
uv run ruff check .       → All checks passed
uv run ruff format --check . → 39 files already formatted
uv run mypy .             → Success: no issues found in 23 source files
```

## Decisões técnicas

- Texto aceito pela regex `[+-]?\d+(\.\d+)?`, sem espaços. Espaços ao redor são recusados (spec: "texto não numérico").
- `Decimal` com mais casas do que o limite, mas só com zeros à direita (`7.990`), é aceito, porque o valor é exato.
- Valor fora da faixa de precisão do contexto `Decimal` (ex.: `1E+100`) levanta `ValorInvalido`.
- Campos: a recusa de `float` ocorre em `to_python`, portanto também no `save()`, não só em `full_clean`.
- Migrações (`**/migrations/*.py`) excluídas do ruff por serem geradas.

## Limitações

- Nenhuma revisão independente feita ainda.
