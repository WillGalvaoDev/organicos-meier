# E01-04 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclos Red → Green → Refactor

| Ciclo | Teste | Red (resultado) | Green |
|---|---|---|---|
| 1 | `tests/tecnicos/test_nucleo_so_insercao.py` (A-1 a A-5, A-12 do modelo de apoio) | coleta falhou: `ModuleNotFoundError: No module named 'apps.nucleo.so_insercao'` | `apps/nucleo/so_insercao.py`, `ModeloSoInsercao` e migração `0003_so_insercao` (com a trigger) em `tests/apoio` |
| 2 | `tests/tecnicos/test_nucleo_auditoria.py` (A-6 a A-14) | coleta falhou: `ModuleNotFoundError: No module named 'apps.nucleo.auditoria'` | `apps/nucleo/auditoria.py`, `apps/nucleo/models.py` e migração `nucleo/0001_auditoria` (com constraints e trigger) |

Os dois ciclos Red foram observados na mesma execução (duas falhas de coleta). A suíte completa passou na primeira execução depois do Green (102 passed); a partir daí só houve refactor de lint (ver abaixo).

Refactor: `constraints` como tupla (RUF012), `noqa` desnecessário removido, teste A-11 reorganizado em função auxiliar (PT012); `null=True` em `autor_id` justificado com `noqa: DJ001`, porque a constraint do banco exige NULL para autor `sistema`.

## Verificações (final)

```
uv run pytest -q                                  → 102 passed
uv run ruff check .                               → All checks passed
uv run ruff format --check .                      → ok
uv run mypy .                                     → Success: no issues found in 36 source files
manage.py makemigrations --check --dry-run (test) → No changes detected
```

## Decisões técnicas

- Trigger `BEFORE UPDATE OR DELETE ... FOR EACH ROW` com `ERRCODE integrity_constraint_violation`; mensagem `tabela <nome> só aceita inserção`.
- Sem trigger de `TRUNCATE`: o spec pede só `UPDATE` e `DELETE`, e o `TRUNCATE` é o que o Django usa para limpar o banco nos testes `transaction=True` (E01-05).
- `objeto_tipo` usa `_meta.label_lower`; `objeto_id` é texto.
- `alteracoes` usa `DjangoJSONEncoder`, então `Decimal` e datas são gravados como texto.
- Erros de `registrar_auditoria` são `ValueError` (autor, ação, objeto não salvo, termo reservado a segredo).
- Operação de migração `instalar_protecao_so_insercao` valida o nome da tabela (`[a-z_][a-z0-9_]*`).
- Constraints de banco: tipo do autor em (`usuario`, `sistema`) e identificador conforme o tipo (A-13).

## Limitações

- Nenhuma revisão independente feita ainda.
- Sem teste de concorrência de auditoria (spec dispensa).
