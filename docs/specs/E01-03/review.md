# E01-03 — Revisão

Estado atual: **APROVADO** no commit `e7eec3c` (revalidação independente ao final).

Abaixo, relato histórico do implementador, preservado como evidência declarada.

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

- Na data deste relato histórico, a revisão independente ainda não havia ocorrido. Resultado atual ao final.

## Revisão independente — 2026-10-15

Revisor: Codex (agente 3). Commit auditado: `72288d3dcc9d618940276d61f83d84110f5b0bb8`.
Fontes: funcional v1.6, infraestrutura v1.7, AGENTS.md, spec.md e acceptance.md. Versões compatíveis. Considerada a liberação da especificação por decisão registrada em 2026-10-15.

**Decisão: REPROVADO.** A revisão está concluída; a entrega tem bloqueador aberto e não atende ao Definition of Done. Nenhuma implementação foi corrigida pelo revisor.

### Verificações independentes

| Comando | Resultado |
|---|---|
| `uv sync --locked` | 50 pacotes resolvidos, 49 verificados; lockfile inalterado |
| `uv run pytest -q` | 111 passed em 5,51 s, Postgres 17.11 real |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 54 files already formatted |
| `uv run mypy .` | Success: no issues found in 39 source files |
| `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` | No changes detected |
| `uv run python manage.py check --settings=config.settings.test` | 0 issues |

O Postgres estava parado na primeira tentativa, que foi interrompida. Foi iniciado por `docker compose up -d db`, e a suíte acima passou. Uma tentativa com `pytest --noinput` foi recusada por opção inválida, sem executar testes. O serviço local ficou iniciado. Nenhum dado de produção foi acessado.

CI do mesmo commit consultado: [run 38732287853](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38732287853), 111 passed em 5,35 s, Postgres 17.11. Os probes adicionais, fora da suíte versionada, resultaram em **6 failed, 1 passed**; as falhas esperadas demonstram os defeitos descritos nos relatórios E01-02 a E01-05. Reprodução: salvar os trechos abaixo em arquivo temporário e executar `uv run pytest -c pyproject.toml <arquivo> -q` na raiz. Não foram incorporados testes ou correções à implementação auditada.

### Matriz de aceitação

| Critérios | Evidência |
|---|---|
| A-1 a A-3 | Relógio UTC e fixture passam. |
| A-4, A-5 | Fronteiras 24h/48h em UTC, milissegundos e microssegundos passam; instantes civis repetidos falham em R03. |
| A-6, A-7 | Soma e conversão São Paulo passam. O teste denominado horário de verão só usa UTC, sem transição civil. |
| A-8 | Recusa de naive em todos os argumentos passa. |
| A-9 | Persistência com microssegundos passa em Postgres. |
| A-10 | Ruff acusa now/utcnow sem fuso e aceita now(UTC). |

### R03 — Bloqueador: comparações não normalizam para UTC

Origem: infraestrutura 4.3 (comparação em UTC), funcional §15, spec E01-03 (instantes inequívocos e independência do fuso).
Local: `apps/nucleo/tempo.py:35` e `:40`.

Datetimes com a mesma instância ZoneInfo são comparados diretamente. Na repetição de uma hora civil, fold=0 e fold=1 podem representar instantes separados por uma hora, mas ser tratados como iguais. Exemplo histórico de America/Sao_Paulo: 2019-02-16 23:30 -02 e 23:30 -03. prazo_encerrado(primeiro, segundo) e ate_o_limite(segundo, primeiro) retornam True indevidamente. A API não restringe as entradas a UTC.

Devolução: comparar instantes absolutos em UTC, preservando precisão e recusa de naive. Testar ambas as direções e soma durante transição civil; os limites comerciais não mudam.

```python
from datetime import datetime, UTC
from zoneinfo import ZoneInfo
from apps.nucleo.tempo import prazo_encerrado, ate_o_limite


def test_comparacao_instantes_repetidos():
    z = ZoneInfo("America/Sao_Paulo")
    a = datetime(2019, 2, 16, 23, 30, tzinfo=z, fold=0)
    b = datetime(2019, 2, 16, 23, 30, tzinfo=z, fold=1)
    assert a.astimezone(UTC) < b.astimezone(UTC)
    assert not prazo_encerrado(a, b)
    assert not ate_o_limite(b, a)
```

Probe: falha na primeira comparação. A segunda também foi executada separadamente: True, esperado False.

### Evidência TDD — importante (E01-TDD)

Os relatos anteriores são evidência declarada pelo implementador, preservada. Git contém testes e implementação juntos no commit de cada fatia; PRs #6 a #9 só apontam para a especificação. Não foram encontrados logs originais ou estados intermediários que confirmem independentemente a sequência temporal Red → Green por comportamento. Falhas de coleta por módulo ausente demonstram falta da interface, mas não exercitam as asserções individuais. Isso não prova ausência de TDD; limita o que se pode atestar (AGENTS.md §3 e §8).

Na devolução, vincular os registros originais disponíveis aos comandos e testes; apresentar Red → Green das regressões antes das correções. Remover artificialmente a implementação agora não comprova TDD histórico. A conferência dessa rastreabilidade permanece pendente para aprovação; não se exige commit por teste.

### Próximo gate

Correção com TDD e revalidação de R03, fronteiras, fusos, persistência e DTZ.

## Correção após a reprovação (implementador)

**R03 — comparações não normalizavam para UTC.** Causa: datetimes com a mesma instância `ZoneInfo` são comparados pelos campos locais, ignorando `fold`. Correção em `apps/nucleo/tempo.py`: `prazo_encerrado`, `ate_o_limite` e `somar_horas` passam por `_em_utc`, que recusa naive e converte para UTC.

Testes novos (`tests/tecnicos/test_nucleo_tempo.py`): `test_fronteira_instantes_civis_repetidos_comparam_em_utc` (as duas direções, fim do horário de verão de 2019 em São Paulo) e `test_fuso_somar_horas_atravessa_transicao_civil_com_24h_exatas`.

Rastreabilidade TDD (E01-TDD): os resultados Red originais da fatia estão transcritos nas tabelas "Ciclos" acima, copiados das saídas dos comandos executados na ordem teste → falha → código. Não foram salvos logs brutos nem commits intermediários (cada fatia entrou em um commit), e isso não pode ser reconstruído agora; fica registrado como limitação. As regressões abaixo seguem Red → Green com a saída do Red anotada antes da correção.
Red das regressões, antes de qualquer correção (`uv run pytest -q`, baseline 111 passed):

```
11 failed, 116 passed
FAILED test_nucleo_valores.py::test_conversao_recusa_excesso_de_casas_alem_da_precisao_do_contexto[x4]
FAILED test_nucleo_tempo.py::test_fronteira_instantes_civis_repetidos_comparam_em_utc
FAILED test_nucleo_auditoria.py::test_auditoria_banco_recusa_usuario_com_identificador_vazio_por_sql[x3]
FAILED test_nucleo_auditoria.py::test_auditoria_banco_recusa_usuario_com_identificador_vazio_pelo_modelo[x2]
FAILED test_apoio_concorrencia.py::test_utilitario_operacao_expirada_nao_reabre_conexao
```

Verificação após as correções (todas as fatias, mesma execução):

```
uv run pytest -q                 -> 127 passed (111 anteriores + 16 regressões)
uv run ruff check .              -> All checks passed
uv run ruff format --check .     -> ok
uv run mypy .                    -> Success: no issues found in 40 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
```

## Revalidação independente — commit 6b7b9ab — 2026-10-15

Revisor: Codex (agente 3). Base exata: `6b7b9ab4282cc87b8f211385ebeb8be264b864da`, inicialmente sem alterações locais. Fontes e critérios de aceitação relidos; funcional v1.6, infraestrutura v1.7 e specs não mudaram desde a revisão anterior. A decisão desta seção substitui a decisão anterior para este commit, sem apagar o histórico.

### Comandos e resultados desta reexecução

| Comando | Resultado independente |
|---|---|
| `uv sync --locked` | 50 pacotes resolvidos, 49 verificados, lockfile inalterado |
| `uv run pytest -q -rA` | **127 passed em 6,68 s**; cada teste da matriz abaixo consta no relatório de execução |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 54 files already formatted |
| `uv run mypy .` | Success: no issues found in 40 source files |
| `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` | No changes detected |
| `uv run python manage.py check --settings=config.settings.test` | 0 issues |
| `uv run pytest -c pyproject.toml "$env:TEMP/om_e01_6b7b9ab_probes.py" -q` | **10 passed, 1 failed em 3,56 s**; única falha: timeout durante abertura de conexão (E01-05/R05) |

Banco local: Postgres 17.11 real, serviço saudável. A execução de push do commit auditado foi consultada: [CI 38734822451](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38734822451), 127 passed em 6,28 s, Postgres 17.11. Os probes independentes ficaram em arquivo temporário; o cenário ainda falho está preservado integralmente no review da E01-05. Nenhum código de produção ou teste versionado foi alterado nesta revalidação.

### Matriz completa reexecutada

| Critério | Resultado | Evidência |
|---|---|---|
| A-1 | PASSOU | test_agora_devolve_utc_com_fuso |
| A-2 | PASSOU | test_agora_reflete_relogio_congelado |
| A-3 | PASSOU | test_agora_avanca_com_o_relogio_controlado |
| A-4 | PASSOU | test_fronteira_prazo_encerrado_exclusivo |
| A-5 | PASSOU | test_fronteira_ate_o_limite_inclusivo |
| A-6 | PASSOU | test_fuso_somar_24h_atravessa_meia_noite_em_sao_paulo + transição civil de R03 |
| A-7 | PASSOU | test_fuso_exibicao_em_sao_paulo_preserva_o_instante |
| A-8 | PASSOU | test_fuso_recusa_instante_sem_fuso [6 chamadas] e congelar sem fuso |
| A-9 | PASSOU | test_persistencia_instante_com_microssegundos_volta_igual |
| A-10 | PASSOU | test_dtz_ruff_acusa_datetime_now_sem_fuso; utcnow recusado e now(UTC) aceito |

### R03 — ENCERRADO; decisão da fatia: APROVADO

As comparações agora convertem ambos os argumentos para UTC por _em_utc. Probe independente com America/Sao_Paulo em 2019-02-16 23:30, fold 0/1, passou nas quatro direções de comparação. Regressão de soma durante transição civil passou, com 24h absolutas e exibição local correta. Fronteiras originais e rejeição de naive preservadas. Referências: infraestrutura 4.3 e funcional §15.

Matriz executada em `test_nucleo_tempo.py`, `test_nucleo_tempo_persistencia.py` e `test_regras_estaticas.py`. Nenhum achado funcional aberto nesta fatia.

### Reavaliação de E01-TDD

Conferido o complemento do implementador: comando `uv run pytest -q`, baseline 111, Red declarado de 11 failed/116 passed, nomes das regressões, causas e Green de 127 passed. O diff mantém os testes anteriores e acrescenta 16 casos; não houve remoção ou afrouxamento para esconder defeitos. Os registros transcritos são aceitos como evidência documental prevista no AGENTS.md, que não exige logs brutos ou um commit por ciclo. A ordem histórica não foi observada diretamente pelo revisor e não pode ser reconstruída a partir do commit único: essa limitação permanece explícita. E01-TDD fica encerrado como ressalva documental, não como bloqueador adicional. Os testes executados agora comprovam o estado atual, não o passado.

Próximo gate desta fatia: encerrado. A E01 global continua reprovada pelo bloqueador de E01-05.

## Revalidação independente — e7eec3c — 2026-10-15

Revisor: Codex, agente 3. Commit exato: `e7eec3c81b9455af94cb23acb0adc2886a4f97f5`. **Decisão desta fatia: APROVADO, mantida.** A E01 global continua REPROVADA por R05/A-7 da E01-05, conforme relatório atualizado daquela fatia.

O diff desde 6b7b9ab altera apenas o utilitário/testes de concorrência e relatórios. Não modifica código de produção, configurações, workflow, dependências, documentos-base ou critérios de aceitação. Reexecutados `uv run pytest -q` (130 passed em 6,89 s, Postgres 17.11 real), `uv run ruff check .` (limpo), `uv run ruff format --check .` (54 arquivos), `uv run mypy .` (40 arquivos, sem erros), `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` (sem mudanças) e `uv run python manage.py check --settings=config.settings.test` (0 issues). Os critérios automatizados das matrizes anteriores permanecem verdes.

Os 11 probes independentes da revalidação anterior foram repetidos sem alteração e passaram (3,78 s), incluindo R02, R03, R04 e o cenário anterior de R05. A aprovação das quatro primeiras fatias permanece; o novo cenário falho de conexão em abertura está documentado na E01-05. CI do SHA auditado: [run 38739955114](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38739955114), 130 passed em 6,64 s.
