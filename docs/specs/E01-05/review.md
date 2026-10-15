# E01-05 — Revisão

Estado atual: **REPROVADO** no commit `6b7b9ab` (revalidação independente ao final).

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
| A-1 | PASSOU | test_utilitario_devolve_resultados_na_ordem_das_operacoes |
| A-2 | PASSOU | test_utilitario_cada_operacao_tem_conexao_propria |
| A-3 | PASSOU | test_demonstracao_corrida_sem_trava_perde_atualizacao: contador 1 |
| A-4 | PASSOU | test_demonstracao_select_for_update_nao_perde_atualizacao: 20 repetições, contador 2 |
| A-5 | PASSOU | test_utilitario_devolve_excecao_de_uma_operacao_e_valor_da_outra |
| A-6 | PASSOU | test_utilitario_tempo_esgotado_identifica_operacao_pendente; probe SQL pg_sleep com timeout também passou |
| A-7 | FALHOU | Casos existentes passam, inclusive retomada e trava de linha; probe de abertura lenta deixa 1 conexão após TempoEsgotado (R05 abaixo). |

### R05 — PARCIALMENTE CORRIGIDO; decisão da fatia: REPROVADO

A retomada original foi corrigida: após timeout, cursor() não reabre o wrapper já registrado e levanta TempoEsgotado. Probe independente de retomada passou, sem SELECT 42 executado e sem o PID anterior em pg_stat_activity. O teste versionado de liberação de trava com select_for_update(nowait=True) também passou.

**Bloqueador remanescente R05/A-7 — conexão ainda não registrada durante abertura.** Em `tests/apoio/concorrencia.py:74`, ensure_connection() é executado antes da publicação em conexoes[indice] (linha 75). Se o timeout ocorre nessa janela, a linha 103 encontra None e ignora a limpeza. O wrapper já pode ter conexão real aberta enquanto inicializa ou aguarda retorno. Após TempoEsgotado, o chamador pode prosseguir com uma conexão da thread ainda aberta.

O probe injeta uma espera controlada na abertura após obter conexão real. Não simula pg_stat_activity: consulta o Postgres real e observa **1 conexão**, esperado **0**, após timeout de 0,3 s. Reproduzido duas vezes: na bateria (1 failed, 10 passed) e isoladamente (`-k timeout_durante_abertura`: 1 failed, 10 deselected). O finally libera a espera e faz join para não deixar a própria prova contaminando os testes seguintes.

Origem: spec E01-05, fechamento com sucesso/erro/timeout, A-7 e devolução anterior que já solicitava cobertura de abertura/limpeza. É lacuna técnica da mesma garantia; não requer decisão comercial.

### Reprodução independente completa do bloqueador

Salvar o trecho em arquivo temporário e executar `uv run pytest -c pyproject.toml <arquivo> -q` a partir da raiz:

```python
import threading
import pytest
from django.db import connection
from django.db.backends.postgresql.base import DatabaseWrapper
from tests.apoio.concorrencia import executar_em_paralelo, TempoEsgotado


@pytest.mark.django_db(transaction=True)
def test_r05_timeout_durante_abertura(monkeypatch):
    liberar = threading.Event()
    entrou = threading.Event()
    registro = {}
    original = DatabaseWrapper.ensure_connection

    def abertura_lenta(self):
        original(self)
        if threading.current_thread().name.startswith("concorrencia-") and not entrou.is_set():
            registro["thread"] = threading.current_thread()
            registro["pid"] = self.connection.info.backend_pid
            entrou.set()
            liberar.wait(5)

    with connection.cursor() as c:
        c.execute("SELECT 1")
    monkeypatch.setattr(DatabaseWrapper, "ensure_connection", abertura_lenta)
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(lambda _b: None, tempo_limite=0.3)
        assert entrou.is_set()
        with connection.cursor() as c:
            c.execute("SELECT count(*) FROM pg_stat_activity WHERE pid=%s", [registro["pid"]])
            total = c.fetchone()[0]
        assert total == 0
    finally:
        liberar.set()
        if "thread" in registro:
            registro["thread"].join(3)
```

### Devolução e próximo gate

Garantir limpeza e impedimento de acesso também quando o prazo termina antes de concluir a abertura/publicação do wrapper, inclusive abertura que retorne tarde ou falhe. Não resolver apenas acrescentando uma espera sem limite ao chamador. Implementador deve acrescentar a regressão, registrar Red antes da correção e Green depois, reexecutar A-1 a A-7 e a suíte relevante; agente 3 revalida. Nenhuma correção foi feita nesta revisão.

### Reavaliação de E01-TDD

Conferido o complemento do implementador: comando `uv run pytest -q`, baseline 111, Red declarado de 11 failed/116 passed, nomes das regressões, causas e Green de 127 passed. O diff mantém os testes anteriores e acrescenta 16 casos; não houve remoção ou afrouxamento para esconder defeitos. Os registros transcritos são aceitos como evidência documental prevista no AGENTS.md, que não exige logs brutos ou um commit por ciclo. A ordem histórica não foi observada diretamente pelo revisor e não pode ser reconstruída a partir do commit único: essa limitação permanece explícita. E01-TDD fica encerrado como ressalva documental, não como bloqueador adicional. Os testes executados agora comprovam o estado atual, não o passado.

## Correção da revalidação 6b7b9ab — R05 remanescente (implementador)

**Causa.** A conexão era registrada em `conexoes[indice]` só depois de `ensure_connection()`. Um timeout durante a abertura não encontrava o wrapper e deixava a conexão aberta pela thread.

**Correção** (`tests/apoio/concorrencia.py`): o wrapper é registrado antes de abrir; um `Event` `expirado` é definido no timeout; se a abertura retornar depois dele, a thread levanta `TempoEsgotado` sem executar a operação. O `connect` do wrapper expirado continua inutilizado, então uma abertura que ainda não terminou também falha ao tentar conectar.

**Red** (probe do revisor incorporado como `test_utilitario_timeout_durante_a_abertura_nao_deixa_conexao`, `uv run pytest tests/tecnicos/test_apoio_concorrencia.py -q`):

```
E   assert 1 == 0
FAILED test_apoio_concorrencia.py::test_utilitario_timeout_durante_a_abertura_nao_deixa_conexao
1 failed, 13 passed
```

**Green:** `14 passed` no módulo (5 execuções seguidas) e `130 passed` na suíte; ruff, ruff format, mypy limpos.

Testes acrescentados: o do probe; `test_utilitario_abertura_tardia_nao_executa_a_operacao` (abertura que só conclui depois do tempo limite: a operação não executa e nenhuma conexão sobra) e `test_utilitario_falha_na_abertura_vira_resultado_sem_vazar_conexao` (falha na abertura vira `Resultado.excecao`, sem vazamento). Os dois últimos já passavam antes da correção (cobertura); a primeira versão do segundo assumia que a conexão chegava a abrir, e a asserção foi ajustada para a garantia real (sem execução e sem conexões residuais), sem enfraquecer o que verifica.

