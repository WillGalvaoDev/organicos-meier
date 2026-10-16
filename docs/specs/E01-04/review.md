# E01-04 — Revisão

Estado atual: **APROVADO** no commit `06e2faf` (revalidação independente de 2026-10-16 ao final).

Abaixo, relato histórico do implementador, preservado como evidência declarada.

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

- Na data deste relato histórico, a revisão independente ainda não havia ocorrido. Resultado atual ao final.
- Sem teste de concorrência de auditoria (spec dispensa).

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
| A-1 a A-5 | Inserção e recusa save/delete/lotes/SQL passam em test_nucleo_so_insercao.py. |
| A-6, A-7 | Conteúdo, relógio, sistema e motivo opcional passam. |
| A-8 | Recusas update/delete na aplicação e SQL passam. |
| A-9 | Termos reservados, caixa e estruturas aninhadas passam; filtro especificado é por chave, não detector universal de segredo em texto livre. |
| A-10 | Remoção do usuário preserva entrada e referência. |
| A-11 | Rollback elimina entrada. |
| A-12 | Bulk create de três entradas passa. |
| A-13 | Três combinações previstas passam; identificador vazio não coberto é aceito (R04). |
| A-14 | Autor ausente e ação vazia recusados pelo serviço. |

### R04 — Bloqueador: banco permite usuário sem identificador

Origem: funcional §14, spec E01-04 (autor nunca vazio, identificador obrigatório garantido por constraint), extensão negativa de A-13.
Local: `apps/nucleo/auditoria.py:50` e constraint em `apps/nucleo/migrations/0001_auditoria.py`.

A condição IS NOT NULL aceita string vazia. SQL direto ou inserção direta pelo modelo/bulk_create pode gravar autor_tipo='usuario', autor_id='', deixando uma entrada imutável sem identificação do autor. Não basta validar no serviço.

Devolução: impedir identificador vazio por constraint, manter sistema sem identificador e registrar migração/testes dos caminhos de inserção. Conferir espaços vazios de forma coerente com identificadores textuais.

```python
import pytest
from django.db import connection, transaction, IntegrityError


@pytest.mark.django_db(transaction=True)
def test_autor_vazio_no_banco():
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as c:
        c.execute(
            "INSERT INTO nucleo_entradaauditoria (autor_tipo,autor_id,acao,momento,motivo,alteracoes,objeto_tipo,objeto_id) VALUES ('usuario','','teste',CURRENT_TIMESTAMP,'','{}','teste.objeto','1')"
        )
```

Probe no banco de testes: failed, DID NOT RAISE IntegrityError.

### Limites de escopo

A proteção cobre UPDATE/DELETE conforme especificado, não TRUNCATE nem alterações por proprietário privilegiado. A decisão histórica foi identificada; não se atesta proteção universal contra administração do banco. Permissões de produção pertencem à etapa operacional. Autorização de domínio e transações financeiras não são implementadas nesta fatia.

### Evidência TDD — importante (E01-TDD)

Os relatos anteriores são evidência declarada pelo implementador, preservada. Git contém testes e implementação juntos no commit de cada fatia; PRs #6 a #9 só apontam para a especificação. Não foram encontrados logs originais ou estados intermediários que confirmem independentemente a sequência temporal Red → Green por comportamento. Falhas de coleta por módulo ausente demonstram falta da interface, mas não exercitam as asserções individuais. Isso não prova ausência de TDD; limita o que se pode atestar (AGENTS.md §3 e §8).

Na devolução, vincular os registros originais disponíveis aos comandos e testes; apresentar Red → Green das regressões antes das correções. Remover artificialmente a implementação agora não comprova TDD histórico. A conferência dessa rastreabilidade permanece pendente para aprovação; não se exige commit por teste.

### Próximo gate

Correção com TDD e revalidação de R04, constraints/migrações, preservação de autor, atomicidade e imutabilidade.

## Correção após a reprovação (implementador)

**R04 — banco aceitava autor `usuario` com identificador vazio.** Correção: a constraint `auditoria_autor_id_conforme_tipo` agora exige, para `usuario`, `autor_id IS NOT NULL` e `autor_id ~ '\S'` (ao menos um caractere não branco); `sistema` continua exigindo NULL. Migração `nucleo/0002_autor_id_nao_vazio`.

Observação do ciclo: a primeira versão da constraint usava só o regex, e o teste A-13 já existente acusou que `NULL ~ '\S'` é NULL e o CHECK aceita; por isso o `IS NOT NULL` explícito.

Testes novos (`tests/tecnicos/test_nucleo_auditoria.py`): identificador `""`, `"   "` e tabulação por SQL direto; `""` e `"  "` por `save()` e `bulk_create`.

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
| A-1 | PASSOU | test_aplicacao_salva_objeto_novo |
| A-2 | PASSOU | test_aplicacao_recusa_alterar_objeto_gravado e objeto_relido |
| A-3 | PASSOU | test_aplicacao_recusa_delete_de_instancia |
| A-4 | PASSOU | test_aplicacao_recusa_operacoes_em_lote |
| A-5 | PASSOU | test_trigger_recusa_update_e_delete_por_sql_direto |
| A-6 | PASSOU | test_auditoria_registra_autor_acao_momento_motivo_alteracoes_objeto |
| A-7 | PASSOU | test_auditoria_sem_motivo_e_autor_sistema |
| A-8 | PASSOU | test_auditoria_recusa_alterar_ou_apagar |
| A-9 | PASSOU | test_auditoria_recusa_chaves_com_segredo [9 estruturas] |
| A-10 | PASSOU | test_auditoria_sobrevive_a_remocao_do_usuario |
| A-11 | PASSOU | test_auditoria_desfeita_junto_com_a_transacao |
| A-12 | PASSOU | test_auditoria_bulk_create_funciona e bulk_create do modelo de apoio |
| A-13 | PASSOU | test_auditoria_banco_recusa_combinacoes_invalidas_de_autor + R04, SQL/save/bulk_create |
| A-14 | PASSOU | test_auditoria_recusa_autor_ausente e acao_vazia |

### R04 — ENCERRADO; decisão da fatia: APROVADO

Modelo e migração 0002 exigem simultaneamente IS NOT NULL e regex de caractere não branco para usuário; sistema continua com NULL. Probes independentes de string vazia, espaços e tabulação por SQL levantaram IntegrityError. Testes versionados cobrem também save/bulk_create e os casos NULL/tipo desconhecido. A migração foi aplicada pelo setup do banco de testes; makemigrations não aponta divergência. Referências: funcional §14, spec E01-04 e A-13.

Matriz executada em `test_nucleo_so_insercao.py` e `test_nucleo_auditoria.py`. Limites de TRUNCATE/privilégios administrativos descritos anteriormente permanecem fora da garantia específica de UPDATE/DELETE. Nenhum achado funcional aberto nesta fatia.

### Reavaliação de E01-TDD

Conferido o complemento do implementador: comando `uv run pytest -q`, baseline 111, Red declarado de 11 failed/116 passed, nomes das regressões, causas e Green de 127 passed. O diff mantém os testes anteriores e acrescenta 16 casos; não houve remoção ou afrouxamento para esconder defeitos. Os registros transcritos são aceitos como evidência documental prevista no AGENTS.md, que não exige logs brutos ou um commit por ciclo. A ordem histórica não foi observada diretamente pelo revisor e não pode ser reconstruída a partir do commit único: essa limitação permanece explícita. E01-TDD fica encerrado como ressalva documental, não como bloqueador adicional. Os testes executados agora comprovam o estado atual, não o passado.

Próximo gate desta fatia: encerrado. A E01 global continua reprovada pelo bloqueador de E01-05.

## Revalidação independente — e7eec3c — 2026-10-15

Revisor: Codex, agente 3. Commit exato: `e7eec3c81b9455af94cb23acb0adc2886a4f97f5`. **Decisão desta fatia: APROVADO, mantida.** A E01 global continua REPROVADA por R05/A-7 da E01-05, conforme relatório atualizado daquela fatia.

O diff desde 6b7b9ab altera apenas o utilitário/testes de concorrência e relatórios. Não modifica código de produção, configurações, workflow, dependências, documentos-base ou critérios de aceitação. Reexecutados `uv run pytest -q` (130 passed em 6,89 s, Postgres 17.11 real), `uv run ruff check .` (limpo), `uv run ruff format --check .` (54 arquivos), `uv run mypy .` (40 arquivos, sem erros), `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` (sem mudanças) e `uv run python manage.py check --settings=config.settings.test` (0 issues). Os critérios automatizados das matrizes anteriores permanecem verdes.

Os 11 probes independentes da revalidação anterior foram repetidos sem alteração e passaram (3,78 s), incluindo R02, R03, R04 e o cenário anterior de R05. A aprovação das quatro primeiras fatias permanece; o novo cenário falho de conexão em abertura está documentado na E01-05. CI do SHA auditado: [run 38739955114](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38739955114), 130 passed em 6,64 s.

## Revalidação independente — 523cd9c — 2026-10-15

Revisor: Codex, agente 3. SHA: `523cd9c2780ba50fdd4f962873c86844b1ca7b8b`. **APROVADO nesta fatia, decisão mantida.** A E01 global continua REPROVADA por R05/A-7 da E01-05.

O diff desde e7eec3c altera somente utilitário/testes de concorrência e relatórios; código de produção, configurações, workflow, dependências, fontes de verdade e critérios permanecem iguais. Reexecução independente: `uv run pytest -q` → 131 passed em 7,81 s, Postgres 17.11; ruff check limpo; ruff format --check: 54 arquivos; mypy: 40 arquivos sem erros; makemigrations --check --dry-run (settings test): sem mudanças; manage.py check (settings test): 0 issues. Doze probes anteriores também passaram, sem modificação. A única falha adicional está reproduzida no relatório E01-05.

CI de push do SHA exato: [run 38743418962](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38743418962), 131 passed em 8,40 s, Postgres 17.11. Ressalvas documentais de TDD já registradas permanecem; não surgiu achado nesta fatia. Nenhuma implementação foi alterada pelo revisor.


## Revalidação independente — b709ce3 — 2026-10-15

Revisor: Codex, agente 3. SHA auditado: `b709ce3ac41aa9dee593f7975efc88c6030019d0` (main, merge do PR #20). **APROVADO nesta fatia, mantida a decisão.** Fontes de verdade e implementação desta fatia não mudaram; alterações funcionais desta rodada estão no apoio de concorrência da E01-05. Matrizes anteriores permanecem aplicáveis, com a cobertura automatizada reexecutada na suíte completa: `uv run pytest -q`, **139 passed em 40,51 s**, Postgres real. R02, R03 e R04 também permanecem verdes nos probes independentes anteriores. Não surgiu achado nesta fatia.

Verificações: `uv run ruff check .` limpo; `uv run ruff format --check .`, 54 arquivos; `uv run mypy .`, 40 arquivos sem erros; `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`, sem mudanças; `uv run python manage.py check --settings=config.settings.test`, zero issues. CI do SHA exato: [run 38748612333](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38748612333), sucesso, 139 testes; PR #20: run 38748350219, sucesso. Mantida a limitação histórica das evidências TDD declaradas, já registrada nas revisões anteriores.

A E01 global continua **REPROVADA**, agora pela incompatibilidade técnica R06/A-17 documentada na E01-05; o vazamento R05 foi corrigido. Nenhum código de implementação ou teste versionado foi alterado pelo revisor.


## Revalidação independente — 06e2faf — 2026-10-16

Revisor: Codex, agente 3. SHA auditado: `06e2fafef33b1beb5ae346e2ff6fd590a0184689`. **APROVADO nesta fatia, decisão mantida. E01 global APROVADA.** Implementação e requisitos desta fatia permanecem inalterados. R06 da E01-05 foi encerrado pela compatibilização do contrato com timeout fixo e pela revalidação independente; R01 a R05 continuam encerrados.

Evidências desta rodada: `uv run pytest -q`, **143 passed em 40,28 s**, Postgres 17.11; matriz A-1 a A-18 da E01-05 reexecutada, módulo com **27 passed nas cinco execuções consecutivas**. Ruff check limpo, format check 54 arquivos, mypy 40 arquivos sem erros, makemigrations --check --dry-run sem mudanças e manage.py check zero issues (settings test). CI do SHA exato [38897195100](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38897195100): sucesso. Mantidas as evidências anteriores e suas limitações documentais de TDD; não surgiu achado nesta fatia. Relatório detalhado da revalidação em `../E01-05/review.md`.

Somente os relatórios foram alterados pelo revisor, na branch `revisao/e01-06e2faf`, sem commit/push/merge. Gate de revisão da E01 encerrado.
