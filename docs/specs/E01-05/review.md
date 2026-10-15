# E01-05 — Revisão

Estado atual: **REPROVADO** (revisão independente ao final).

Abaixo, relato histórico do implementador, preservado como evidência declarada.

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

- Na data deste relato histórico, a revisão independente ainda não havia ocorrido. Resultado atual ao final.
- Uma operação que bloqueia fora de barreira e de chamada ao banco (por exemplo, `time.sleep` longo) continua rodando em segundo plano depois do `TempoEsgotado`; o utilitário não consegue encerrar threads Python.

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
| A-1, A-2 | Ordem dos resultados e conexões distintas passam. |
| A-3 | Corrida sem trava reproduz contador final 1. |
| A-4 | Com trava, 20 repetições produzem contador final 2. |
| A-5 | Exceção de uma operação e valor da outra preservados. |
| A-6 | Barreira incompleta gera TempoEsgotado; probe pg_sleep(2), limite 0,2 s, retornou em cerca de 0,203 s. |
| A-7 | Casos existentes passam; retomada tardia reabre conexão (R05). |

### R05 — Bloqueador: operação expirada reabre conexão

Origem: spec E01-05 (fechar conexões em timeout e não deixar conexões para testes seguintes), A-7, AGENTS.md §6.
Local: `tests/apoio/concorrencia.py:78-92`.

O chamador fecha o wrapper, mas retorna TempoEsgotado com a thread viva. Quando ela sai de espera externa e usa connection.cursor(), o Django abre outra conexão. Pode executar SQL depois de o teste chamador falhar e começar a limpeza ou outro teste. É mais grave que a limitação documentada de continuar dormindo.

Reproduzido: após timeout de 0,2 s, operação liberada por Event executou SELECT 42. Em outro probe abriu nova conexão e voltou a esperar; pg_stat_activity confirmou 1 conexão desse PID após TempoEsgotado, esperado 0. Eventos liberados no finally para terminar a operação de prova.

Devolução: garantir que operações expiradas não retomem acesso ao banco nem sobrevivam com conexão aberta à passagem ao teste seguinte. Cobrir retomada tardia, falhas de abertura/limpeza e consulta/trava real. A barreira abortada dos testes existentes finaliza a thread e não cobre este caso.

```python
import threading
import pytest
from django.db import connection
from tests.apoio.concorrencia import executar_em_paralelo, TempoEsgotado


@pytest.mark.django_db(transaction=True)
def test_conexao_reaberta_permanece_apos_timeout():
    liberar = threading.Event()
    abriu = threading.Event()
    encerrar = threading.Event()
    finalizou = threading.Event()
    pids = []

    def atrasada(_b):
        try:
            liberar.wait(3)
            with connection.cursor() as c:
                c.execute("SELECT pg_backend_pid()")
                pids.append(c.fetchone()[0])
            abriu.set()
            encerrar.wait(3)
        finally:
            finalizou.set()

    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(atrasada, tempo_limite=0.2)
        liberar.set()
        assert abriu.wait(2)
        with connection.cursor() as c:
            c.execute("SELECT count(*) FROM pg_stat_activity WHERE pid=%s", [pids[0]])
            total = c.fetchone()[0]
        assert total == 0
    finally:
        liberar.set()
        encerrar.set()
        finalizou.wait(3)
```

Probe: failed, assert 1 == 0. O probe separado de SELECT 42 também falhou: resultado [42], esperado [].

### Evidência TDD — importante (E01-TDD)

Os relatos anteriores são evidência declarada pelo implementador, preservada. Git contém testes e implementação juntos no commit de cada fatia; PRs #6 a #9 só apontam para a especificação. Não foram encontrados logs originais ou estados intermediários que confirmem independentemente a sequência temporal Red → Green por comportamento. Falhas de coleta por módulo ausente demonstram falta da interface, mas não exercitam as asserções individuais. Isso não prova ausência de TDD; limita o que se pode atestar (AGENTS.md §3 e §8).

Na devolução, vincular os registros originais disponíveis aos comandos e testes; apresentar Red → Green das regressões antes das correções. Remover artificialmente a implementação agora não comprova TDD histórico. A conferência dessa rastreabilidade permanece pendente para aprovação; não se exige commit por teste.

### Próximo gate

Correção com Red → Green, revalidação de R05/A-1 a A-7 e suíte completa. Provar limpeza antes de continuar a suíte, com revisão independente.

## Correção após a reprovação (implementador)

**R05 — operação expirada reabria a conexão.** Causa: depois do tempo limite o wrapper era fechado, mas a thread viva abria outra conexão no próximo `cursor()`. Correção em `tests/apoio/concorrencia.py`: ao expirar, a conexão da thread é fechada e o `connect` do wrapper dela é substituído por uma função que levanta `TempoEsgotado`, então a operação expirada não consegue abrir conexão nem executar SQL.

Testes novos (`tests/tecnicos/test_apoio_concorrencia.py`): `test_utilitario_operacao_expirada_nao_reabre_conexao` (a retomada tardia falha e o pid anterior não existe em `pg_stat_activity`) e `test_utilitario_timeout_libera_trava_de_linha` (`select_for_update` real; a linha volta a ser travável com `nowait`).

Atualização da limitação anterior: a operação expirada pode continuar viva e bloqueada fora do banco, mas não acessa mais o banco.

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
