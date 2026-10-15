# E01-05 — Revisão

Estado atual: **REPROVADO** no commit `523cd9c` (revalidação independente ao final).

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


## Revalidação independente — e7eec3c — 2026-10-15

Revisor: Codex, agente 3. Commit exato: `e7eec3c81b9455af94cb23acb0adc2886a4f97f5`; árvore inicialmente limpa. **Decisão: REPROVADO. A E01 ainda não está aprovada.** R01 a R04 permanecem encerrados; R05/A-7 continua com bloqueador de limpeza da conexão em abertura. Esta decisão substitui a decisão anterior para o SHA auditado, preservando o histórico.

### Verificações executadas

| Comando/evidência | Resultado |
|---|---|
| `uv run pytest -q` | 130 passed em 6,89 s, Postgres 17.11 real |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 54 files already formatted |
| `uv run mypy .` | Success: no issues found in 40 source files |
| `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` | No changes detected |
| `uv run python manage.py check --settings=config.settings.test` | 0 issues |
| `uv run pytest -c pyproject.toml "$env:TEMP/om_e01_6b7b9ab_probes.py" -q` | 11 passed em 3,78 s; inclui o probe anterior de R05, sem alterações |
| `uv run pytest -c pyproject.toml "$env:TEMP/om_e01_e7eec3c_conexao_em_abertura.py" -q` | 1 failed em 1,45 s: conexão em abertura já iniciada permanece no Postgres após timeout |
| [CI do commit auditado](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38739955114) | 130 passed em 6,64 s, Postgres 17.11 |

### Matriz de aceitação atual

| Critério | Resultado | Evidência |
|---|---|---|
| A-1 | PASSOU | Resultados na ordem das operações |
| A-2 | PASSOU | Conexões próprias e PIDs distintos |
| A-3 | PASSOU | Atualização perdida determinística, contador 1 |
| A-4 | PASSOU | select_for_update, 20 repetições com contador 2 |
| A-5 | PASSOU | Valor e exceção preservados por operação |
| A-6 | PASSOU | TempoEsgotado identifica operação; timeout de barreira e consulta real passam |
| A-7 | FALHOU | Casos existentes e abertura anterior passam; conexão ainda não entregue ao wrapper permanece aberta após timeout (R05 abaixo) |

### R05 — correção anterior confirmada, abertura em andamento ainda não coberta

Referências: spec E01-05, regra Conexões (fechar ao final inclusive por timeout, sem conexões herdadas por testes seguintes), A-7 e devolução anterior (abertura que retorne tarde ou falhe). **Classificação: bloqueador.** Não é nova regra comercial nem ampliação para outra entrega.

A publicação do wrapper antes de ensure_connection resolve o probe anterior: quando o wrapper já possui self.connection, close() alcança a conexão. O Event também impede executar a operação depois de uma abertura tardia. Ambos foram verificados; não são novamente reprovados.

Permanece outra janela da mesma abertura: connect() já entrou em execução, get_new_connection() estabeleceu a conexão real, mas ainda não retornou para a atribuição a self.connection. Nesse intervalo:

1. A thread principal encontra o wrapper registrado e troca seu método connect (`tests/apoio/concorrencia.py:47`). Isso só afeta chamadas futuras, não cancela o connect que já está em execução.
2. close() (linha 50) encontra self.connection=None e retorna sem encerrar a conexão real ainda em abertura.
3. executar_em_paralelo levanta TempoEsgotado; pg_stat_activity ainda contém a conexão da thread. O encerramento só ocorre depois que a abertura retorna e a thread chega ao finally.

Conferido no Django instalado pelo lockfile: `django/db/backends/base/base.py:256` atribui `self.connection = self.get_new_connection(conn_params)`; close() nas linhas 344–353 retorna quando self.connection é None. O novo teste de abertura tardia do implementador pausa antes de entrar em connect, portanto valida a substituição do método para uma chamada futura, mas não cobre a chamada já em execução.

O probe abaixo pausa deterministicamente o retorno de get_new_connection depois de criar conexão real; não inventa um PID nem altera a contagem do servidor. Ao retornar TempoEsgotado em 0,3 s, confirmou self.connection=None no wrapper e **1 conexão no Postgres, esperado 0**. Após liberar a abertura no finally, a thread termina e a operação de negócio não executa. Portanto o defeito comprovado é a ausência de limpeza antes do retorno, não execução indevida da operação. Uma sessão remanescente pode interferir no encerramento/recriação do banco dos testes seguintes.

### Reprodução completa

Salvar como arquivo temporário e rodar `uv run pytest -c pyproject.toml <arquivo> -q` a partir da raiz. Resultado observado: `assert 1 == 0`.

```python
import threading
import pytest
from django.db import connection
from django.db.backends.postgresql.base import DatabaseWrapper
from tests.apoio.concorrencia import executar_em_paralelo, TempoEsgotado


@pytest.mark.django_db(transaction=True)
@pytest.mark.concorrencia
def test_timeout_com_connect_ja_em_execucao(monkeypatch):
    liberar = threading.Event()
    abriu = threading.Event()
    executou = threading.Event()
    registro = {}
    original = DatabaseWrapper.get_new_connection

    def abrir_com_retorno_lento(self, params):
        raw = original(self, params)
        if threading.current_thread().name.startswith("concorrencia-"):
            registro["thread"] = threading.current_thread()
            registro["pid"] = raw.info.backend_pid
            registro["wrapper_sem_conexao"] = self.connection is None
            abriu.set()
            liberar.wait(5)
        return raw

    with connection.cursor() as c:
        c.execute("SELECT 1")
    monkeypatch.setattr(DatabaseWrapper, "get_new_connection", abrir_com_retorno_lento)
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(lambda _b: executou.set(), tempo_limite=0.3)
        assert abriu.is_set()
        assert registro["wrapper_sem_conexao"]
        with connection.cursor() as c:
            c.execute("SELECT count(*) FROM pg_stat_activity WHERE pid=%s", [registro["pid"]])
            quantidade = c.fetchone()[0]
        assert quantidade == 0
    finally:
        liberar.set()
        if "thread" in registro:
            registro["thread"].join(3)
            assert not registro["thread"].is_alive()
        assert not executou.is_set()
```

### TDD e devolução ao implementador

O relato Red de 1 failed/13 passed, seguido de Green de 14 testes e suíte de 130, é coerente com o diff e com o probe anterior agora verde. Nenhum teste anterior foi removido para ocultar falhas. Mantida a ressalva já documentada: a sequência temporal original é evidência transcrita pelo implementador, não execução presenciada pelo revisor.

Para encerrar R05, controlar também a abertura real já em andamento: o retorno por timeout precisa respeitar a garantia de ausência de conexões residuais, sem esperar indefinidamente e sem depender somente de substituir connect para chamadas futuras. Acrescentar este cenário antes de corrigir, registrar Red → Green e revalidar A-1 a A-7, retomada, trava e abertura tardia/falha. Não foi feita correção pelo revisor.

### Decisão global

E01-01 a E01-04 continuam APROVADAS. A E01-05 e, portanto, a E01 permanecem REPROVADAS por R05/A-7. O próximo gate é correção técnica com TDD e nova revisão independente; não há decisão de negócio pendente. Alterações desta revisão limitam-se aos cinco review.md. Nenhuma alteração remota, push ou merge foi realizado.

## Correção da revalidação e7eec3c — conexão em abertura já em andamento (implementador)

**Causa.** Entre o driver estabelecer a conexão (`get_new_connection`) e o Django atribuí-la a `self.connection`, o wrapper está sem conexão: `close()` não tem o que fechar e trocar `connect` só afeta chamadas futuras.

**Correção** (`tests/apoio/concorrencia.py`): cada thread conecta com um `application_name` único (`concorrencia-<id>-<i>`, via `OPTIONS` do wrapper da própria thread). No timeout, o chamador encerra no servidor os backends das operações pendentes (`pg_terminate_backend` filtrado por esse nome) e espera, de forma limitada (2 s), que desapareçam de `pg_stat_activity`. Não depende do estado Python da thread e não espera a abertura terminar. O que já existia continua: wrapper registrado antes de abrir, `connect` inutilizado, evento `expirado`.

**Red** (probe do revisor incorporado como `test_utilitario_timeout_com_connect_ja_em_execucao_nao_deixa_conexao`):

```
uv run pytest tests/tecnicos/test_apoio_concorrencia.py -q
E   assert 1 == 0
FAILED test_apoio_concorrencia.py::test_utilitario_timeout_com_connect_ja_em_execucao_nao_deixa_conexao
1 failed, 14 passed
```

**Green:**

```
uv run pytest tests/tecnicos/test_apoio_concorrencia.py -q (5 execuções seguidas) -> 15 passed em todas
uv run pytest -q                -> 131 passed
uv run ruff check .             -> All checks passed
uv run ruff format --check .    -> ok
uv run mypy .                   -> Success: no issues found in 40 source files
```

Regressões cobertas pelos testes do módulo: retomada tardia, trava de linha real, timeout durante a abertura (`ensure_connection`), abertura tardia, falha de abertura e este cenário (`connect` já em execução).

**Limitação residual.** Se o backend ainda estiver no handshake de autenticação, ele não aparece em `pg_stat_activity` no instante do encerramento; nesse caso a thread, ao retornar da abertura, vê `expirado` e fecha a própria conexão (sem executar a operação). Não há ponto em que a operação executada depois do timeout acesse o banco.


## Revalidação independente — 523cd9c — 2026-10-15

Revisor: Codex, agente 3. SHA auditado: `523cd9c2780ba50fdd4f962873c86844b1ca7b8b`, árvore inicialmente limpa. Spec e acceptance da E01-05 relidos. **Decisão: REPROVADO.** A E01 global permanece reprovada exclusivamente pelo bloqueador R05/A-7 abaixo; as outras quatro fatias continuam aprovadas.

### Verificações independentes

| Comando/evidência | Resultado |
|---|---|
| `uv run pytest -q` | 131 passed em 7,81 s, Postgres 17.11 real |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 54 files already formatted |
| `uv run mypy .` | Success: no issues found in 40 source files |
| `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` | No changes detected |
| `uv run python manage.py check --settings=config.settings.test` | 0 issues |
| Probes independentes das revisões anteriores | 12 passaram sem alteração, incluindo o cenário de conexão já aberta mas ainda não entregue ao wrapper |
| Probe novo: abertura em andamento conclui depois da consulta de limpeza | 1 failed: assert 1 == 0 |
| Bateria conjunta dos probes | 1 failed, 12 passed em 3,75 s |
| [CI do commit](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38743418962) | 131 passed em 8,40 s, Postgres 17.11 |

Comando da bateria conjunta, a partir da raiz (arquivos temporários da revisão):

```powershell
uv run pytest -c pyproject.toml "$env:TEMP/om_e01_523cd9c_abertura_apos_varredura.py" "$env:TEMP/om_e01_e7eec3c_conexao_em_abertura.py" "$env:TEMP/om_e01_6b7b9ab_probes.py" -q
```

### Matriz E01-05

| Critério | Resultado | Evidência |
|---|---|---|
| A-1 | PASSOU | Resultados na ordem de entrada |
| A-2 | PASSOU | PIDs distintos, conexão própria por operação |
| A-3 | PASSOU | Corrida sem trava produz contador 1 |
| A-4 | PASSOU | select_for_update, 20 repetições com contador 2 |
| A-5 | PASSOU | Valores e exceções por operação preservados |
| A-6 | PASSOU | Casos de timeout de barreira e consulta dos testes/probes passaram |
| A-7 | FALHOU | Abertura em andamento pode estabelecer conexão depois da consulta de limpeza; conexão permanece após retorno de TempoEsgotado |

### R05 — correção parcial confirmada; bloqueador remanescente

**Referência:** spec E01-05, regra Conexões (encerrar inclusive por timeout, sem conexões para testes seguintes), A-7 e devolução anterior sobre abertura em andamento/tardia. **Classificação: bloqueador.**

O application_name exclusivo e pg_terminate_backend resolvem o cenário anterior: o backend já visível no Postgres é encerrado, mesmo sem self.connection no wrapper. A prova anterior passou sem alteração. O filtro usa os nomes das operações pendentes e exclui o PID do chamador; não foi constatado encerramento de conexões de outras operações nos testes executados.

Entretanto, `_encerrar_no_servidor` (`tests/apoio/concorrencia.py:56-83`) retorna assim que a consulta encontra zero sessões, ou ao acabar o prazo de limpeza. Zero sessões naquele instante não significa que as aberturas pendentes terminaram. Uma chamada connect já iniciada pode estabelecer sua conexão depois da consulta. Trocar o método connect (linha 48) não cancela essa chamada em andamento, e o Event expirado só é consultado após ensure_connection retornar (linha 115).

Sequência reproduzida:

1. A thread já entrou em get_new_connection, mas ainda não estabeleceu a sessão; a abertura é pausada de forma determinística.
2. O prazo de 0,3 s vence. A consulta no servidor não encontra o application_name e a função retorna TempoEsgotado.
3. A chamada de abertura em andamento é liberada; estabelece uma conexão real com o application_name da operação expirada.
4. Antes de o driver entregar a conexão ao wrapper, o chamador consulta pg_stat_activity: **1 sessão, esperado 0**. A limpeza já terminou e não volta a executar.
5. Ao liberar o retorno do driver, a thread finalmente fecha a sessão e não executa a operação de negócio. Essa limpeza eventual não garante isolamento dos testes seguintes no intervalo.

O probe utiliza atraso controlado na chamada do driver; não é alegação de que um handshake real de rede foi observado. Conexão, PID e contagem são reais no Postgres. É a sequência tardia também reconhecida como limitação residual pelo implementador. Não executar a operação depois do timeout e não deixar conexões residuais são garantias distintas; a primeira passou e a segunda ainda falha. Não se está reabrindo R01 a R04 nem adicionando regra de negócio.

### Reprodução independente completa

Salvar como arquivo temporário e executar `uv run pytest -c pyproject.toml <arquivo> -q`. A prova libera eventos e aguarda a thread no finally, evitando deixar a própria sessão de teste aberta.

```python
import threading
import pytest
from django.db import connection
from django.db.backends.postgresql.base import DatabaseWrapper
from tests.apoio.concorrencia import executar_em_paralelo, TempoEsgotado


@pytest.mark.django_db(transaction=True)
@pytest.mark.concorrencia
def test_abertura_em_andamento_conclui_apos_varredura(monkeypatch):
    permitir_abertura = threading.Event()
    permitir_retorno = threading.Event()
    entrou = threading.Event()
    abriu = threading.Event()
    executou = threading.Event()
    registro = {}
    original = DatabaseWrapper.get_new_connection

    def abertura_atrasada(self, params):
        if not threading.current_thread().name.startswith("concorrencia-"):
            return original(self, params)
        registro["thread"] = threading.current_thread()
        entrou.set()
        permitir_abertura.wait(5)
        raw = original(self, params)
        registro["pid"] = raw.info.backend_pid
        registro["nome"] = params["application_name"]
        abriu.set()
        permitir_retorno.wait(5)
        return raw

    with connection.cursor() as c:
        c.execute("SELECT 1")
    monkeypatch.setattr(DatabaseWrapper, "get_new_connection", abertura_atrasada)
    try:
        with pytest.raises(TempoEsgotado):
            executar_em_paralelo(lambda _b: executou.set(), tempo_limite=0.3)
        assert entrou.is_set()
        # O cleanup no servidor ja terminou; a chamada connect original ainda esta em curso.
        permitir_abertura.set()
        assert abriu.wait(3)
        with connection.cursor() as c:
            c.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE pid=%s AND application_name=%s",
                [registro["pid"], registro["nome"]],
            )
            restantes = c.fetchone()[0]
        assert restantes == 0
    finally:
        permitir_abertura.set()
        permitir_retorno.set()
        if "thread" in registro:
            registro["thread"].join(3)
            assert not registro["thread"].is_alive()
        assert not executou.is_set()
```

### TDD, devolução e próximo gate

O Red transcrito de 1 failed/14 passed e o Green de 15 testes no módulo/131 na suíte são coerentes com o diff e com a regressão anterior agora aprovada. Não foram removidos testes antigos. Mantida a ressalva documental já aceita: cronologia histórica relatada pelo implementador, sem logs brutos ou commits intermediários; os resultados desta revisão foram executados independentemente.

Para encerrar R05, tratar o ciclo completo de abertura e encerramento, incluindo chamadas já iniciadas que ainda não aparecem no servidor. A condição de término da limpeza precisa assegurar que não resta abertura capaz de criar sessão após o retorno; uma consulta vazia ou uma espera fixa, isoladamente, não fornece essa garantia. A solução deve também preservar o timeout limitado e a ausência de execução da operação expirada. Não basta acrescentar outra consulta em um instante diferente.

Implementador deve acrescentar a regressão acima antes da correção, registrar Red → Green e cobrir a sequência inteira: antes de iniciar connect, connect em curso sem sessão, sessão estabelecida ainda não entregue, conexão entregue, erro de abertura e retomada depois do timeout. Revalidar A-1 a A-7 e a suíte, seguido de revisão independente. Nenhuma implementação foi corrigida pelo revisor e nenhuma decisão comercial é necessária.

**Decisão global:** E01-01 a E01-04 APROVADAS; E01-05 e E01 REPROVADAS. Os cinco review.md foram atualizados; não houve alteração remota, push ou merge nesta revisão.

## Correção R05 conforme "Correção R05" do spec.md (implementador)

Base: revisão `523cd9c` (REPROVADO por abertura em andamento que cria a sessão depois da consulta de limpeza) e seção "Correção R05" do `spec.md` e critérios A-8 a A-18 do `acceptance.md`, escritos pelo especificador. Implementado o desenho obrigatório, sem repetir as abordagens listadas em "O que não fazer".

**Andaime (sem comportamento, registrado como exceção técnica):** `LimpezaIncompleta`, `aguardar_limpezas_pendentes`, `limpezas_pendentes`, argumento `tempo_limite_limpeza` e `guarda_entre_testes` entraram como stubs; a suíte seguiu em `131 passed`.

**Red pela asserção** (`uv run pytest tests/tecnicos/test_apoio_concorrencia.py -q`, com os testes novos e os stubs):

```
5 failed, 18 passed
E   assert 1 == 0                                        test_r05_revisor_abertura_em_andamento_conclui_apos_varredura  (A-9)
E   assert 0.5 <= 0.2039999999997235                     test_r05_abertura_lenta_liberada_por_timer_termina_sem_sessao  (A-10)
E   KeyError: 'application_name'                         test_r05_erro_na_abertura_com_tempo_esgotado_e_sem_sessao       (A-14)
E   TempoEsgotado: ... (esperado LimpezaIncompleta)      test_r05_limpeza_incompleta_quando_a_abertura_passa_do_prazo   (A-15, A-16)
E   TypeError: '<' not supported between 'int' and 'NoneType'  test_r05_conexao_do_utilitario_tem_nome_exclusivo_e_connect_timeout (A-17)
```

A-8 e A-11 já passavam antes da correção (herdados das correções anteriores) e ficam como cobertura de regressão, junto com A-12 e A-13, como previsto no acceptance.

**Implementação** (`tests/apoio/concorrencia.py`, `tests/conftest.py`):

- Fases `ANTES`, `ABRINDO`, `ABERTA`, `SEM_CONEXAO` por operação; fase e `expirado` só mudam sob um `threading.Condition` por chamada.
- Cada thread instala em seu wrapper um `connect` controlado: se expirado, recusa sem abrir; senão `ABRINDO`, chama o `connect` original (que usa `get_new_connection` da classe, sem sobrescrevê-lo), e ao retornar passa a `ABERTA` ou, se expirou durante a abertura, fecha a própria conexão, passa a `SEM_CONEXAO` e levanta `TempoEsgotado` sem executar a operação. Erro na abertura leva a `SEM_CONEXAO`. No `finally`, a thread fecha as conexões e passa a `SEM_CONEXAO`.
- Timeout no chamador: marca `expirado` e o retrato das pendentes sob a trava, aborta as barreiras, encerra no servidor as sessões já abertas (`application_name` único por operação), espera com `Condition.wait_for` e prazo (`tempo_limite_limpeza`, 30 s) as aberturas em andamento, e confirma em `pg_stat_activity` zero sessões (repetindo, pois `pg_terminate_backend` é assíncrono). Limpo: `TempoEsgotado`. Prazo estourado ou sessão restante: registra a pendência e levanta `LimpezaIncompleta` com operação e fase.
- `connect_timeout` das threads = 10 s (menor que o prazo de limpeza).
- Guarda: fixture `autouse` em `tests/conftest.py`, ativa só com pendência registrada; resolve com `aguardar_limpezas_pendentes` e, se restar sessão, `pytest.fail` citando a operação.

**Verificação (final):**

```
uv run pytest tests/tecnicos/test_apoio_concorrencia.py -q (5 execuções seguidas) -> 23 passed em todas
   duração do módulo: 39,4 s; 39,4 s; 39,6 s; 40,0 s; 43,7 s
uv run pytest -q                -> 139 passed em 39,5 s
uv run ruff check .             -> All checks passed
uv run ruff format --check .    -> ok
uv run mypy .                   -> Success: no issues found in 40 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
```

**Matriz:**

| Critério | Teste | Resultado |
|---|---|---|
| A-1 a A-7 | testes existentes `test_utilitario_*` e `test_demonstracao_*` | passam |
| A-8 | `test_r05_antes_da_abertura_a_operacao_nao_abre_conexao_nem_executa` | passa (cobertura; já passava) |
| A-9 | `test_r05_revisor_abertura_em_andamento_conclui_apos_varredura` (probe de 523cd9c, ~10 s) | Red → Green |
| A-10 | `test_r05_abertura_lenta_liberada_por_timer_termina_sem_sessao` | Red → Green |
| A-11 | `test_r05_revisor_connect_ja_em_execucao` (probe de e7eec3c, ~5 s) | passa (já passava) |
| A-12 | `test_r05_revisor_timeout_durante_abertura` (probe de 6b7b9ab) e `test_utilitario_operacao_expirada_nao_reabre_conexao` | passam (cobertura) |
| A-13 | `test_utilitario_timeout_libera_trava_de_linha` | passa (cobertura) |
| A-14 | `test_r05_erro_na_abertura_com_tempo_esgotado_e_sem_sessao` e `test_utilitario_falha_na_abertura_vira_resultado_sem_vazar_conexao` | Red → Green |
| A-15, A-16 | `test_r05_limpeza_incompleta_quando_a_abertura_passa_do_prazo` | Red → Green |
| A-17 | `test_r05_conexao_do_utilitario_tem_nome_exclusivo_e_connect_timeout` | Red → Green |
| A-18 | 5 execuções do módulo e suíte completa, acima | passam |

**Observações:**

- Os três probes do revisor foram extraídos por script diretamente dos blocos de código deste `review.md`, sem alterar o corpo. Só foram renomeados para `test_r05_revisor_*` (nome original no comentário acima de cada um) e receberam comentários `# type: ignore[...]` em algumas linhas, porque o mypy estrito acusa as anotações ausentes e os tipos do dicionário `registro`. Nenhuma asserção foi alterada.
- Os testes anteriores de R05 foram mantidos. Há sobreposição com os probes literais (mesmo cenário, versões adaptadas), o que soma ~15 s à duração do módulo.
- Erro meu durante o ciclo: a primeira versão do teste A-14 instrumentava `get_new_connection` também para a thread do chamador (a conexão do chamador ainda não estava aberta), e a limpeza falhou por isso. Corrigido no teste (filtro por nome da thread e conexão do chamador aberta antes); não houve alteração da implementação.
- Desvio de nomenclatura: o spec cita `aguardar_limpezas_pendentes` como a função da guarda e a fixture `autouse` a chama; a função auxiliar que converte `LimpezaIncompleta` em `pytest.fail` e que o A-16 testa diretamente foi nomeada `guarda_entre_testes` em `tests/conftest.py`.
- Limitação: a guarda resolve apenas pendências registradas por `LimpezaIncompleta`. Uma thread pendente continua viva se bloqueada fora do banco, mas sem conexão e sem poder abrir outra.
