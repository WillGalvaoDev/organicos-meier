# E01-02 — Revisão

Estado atual: **APROVADO** no commit `6b7b9ab` (revalidação independente ao final).

Abaixo, relato histórico do implementador, preservado como evidência declarada.

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
| A-1 a A-7, A-18 | Conversões de test_nucleo_valores.py passam nos exemplos; recusa geral de excesso de casas falha em R02. |
| A-8 a A-12 | Arredondamento HALF_UP e idempotência passam. |
| A-13 a A-15 | Múltiplos e passo inválido passam. |
| A-16, A-17, A-19 | test_nucleo_campos_decimais.py: limites, round-trip e float passam. |
| A-20 | App de apoio ausente em base/prod: teste e inspeção confirmam. |

### R02 — Bloqueador: entrada arredondada antes de validar casas

Origem: funcional §4.2/§9, infraestrutura 4.12, spec E01-02 e A-3/A-7.
Local: `apps/nucleo/valores.py:34` e `:38`.

`normalize()` aplica a precisão do contexto antes de fornecer o expoente. Na precisão padrão 28, os dígitos excedentes podem desaparecer e a validação passa. `dinheiro('1.00000000000000000000000000001')` devolve `1.00`; `quantidade('0.25000000000000000000000000001')` devolve `0.250`. Ambas deveriam levantar ValorInvalido, sem arredondar a entrada. Os valores estão na faixa de negócio; limitar magnitude não basta.

Devolução: validar casas sem arredondar; testar texto e Decimal, mantendo zeros finais equivalentes e exceções próprias nas recusas. Probe: **2 failed**, DID NOT RAISE ValorInvalido.

```python
import pytest
from apps.nucleo.valores import dinheiro, quantidade, ValorInvalido


@pytest.mark.parametrize(
    "funcao,valor",
    [
        (dinheiro, "1.00000000000000000000000000001"),
        (quantidade, "0.25000000000000000000000000001"),
    ],
)
def test_excesso_de_casas(funcao, valor):
    with pytest.raises(ValorInvalido):
        funcao(valor)
```

### Evidência TDD — importante (E01-TDD)

Os relatos anteriores são evidência declarada pelo implementador, preservada. Git contém testes e implementação juntos no commit de cada fatia; PRs #6 a #9 só apontam para a especificação. Não foram encontrados logs originais ou estados intermediários que confirmem independentemente a sequência temporal Red → Green por comportamento. Falhas de coleta por módulo ausente demonstram falta da interface, mas não exercitam as asserções individuais. Isso não prova ausência de TDD; limita o que se pode atestar (AGENTS.md §3 e §8).

Na devolução, vincular os registros originais disponíveis aos comandos e testes; apresentar Red → Green das regressões antes das correções. Remover artificialmente a implementação agora não comprova TDD histórico. A conferência dessa rastreabilidade permanece pendente para aprovação; não se exige commit por teste.

### Próximo gate

Correção com Red → Green, reexecução de R02/A-1 a A-20, suíte relevante verde e nova revisão independente. Nenhuma decisão comercial necessária.

## Correção após a reprovação (implementador)

**R02 — excesso de casas aceito além da precisão do contexto.** Causa: `normalize()` aplicava a precisão 28 do contexto antes de ler o expoente, descartando dígitos excedentes. Correção em `apps/nucleo/valores.py`: o expoente vem de `as_tuple()` (exato) e a validação exige que os dígitos além das casas permitidas sejam todos zero; zeros finais continuam equivalentes.

Testes novos (`tests/tecnicos/test_nucleo_valores.py`): `test_conversao_recusa_excesso_de_casas_alem_da_precisao_do_contexto` (texto e `Decimal`, dinheiro e quantidade) e `test_conversao_zeros_finais_continuam_equivalentes`.

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
| A-1 | PASSOU | test_conversao_dinheiro_texto_com_duas_casas |
| A-2 | PASSOU | test_conversao_dinheiro_inteiro_vira_duas_casas |
| A-3 | PASSOU | test_conversao_dinheiro_recusa_excesso_de_casas + regressões R02 |
| A-4 | PASSOU | test_conversao_recusa_float [dinheiro/quantidade] |
| A-5 | PASSOU | test_conversao_dinheiro_recusa_entradas_invalidas e decimal_nao_finito |
| A-6 | PASSOU | test_conversao_quantidade_aceita_ate_tres_casas |
| A-7 | PASSOU | test_conversao_quantidade_recusa_excesso_de_casas + regressões R02 |
| A-8 | PASSOU | test_arredondamento_7_99_vezes_0_25 |
| A-9 | PASSOU | test_arredondamento_2_50_vezes_0_25 |
| A-10 | PASSOU | test_arredondamento_12_99_vezes_0_35 |
| A-11 | PASSOU | test_arredondamento_idempotente |
| A-12 | PASSOU | test_arredondamento_recusa_float |
| A-13 | PASSOU | test_multiplo_exato_verdadeiro [3 pares] |
| A-14 | PASSOU | test_multiplo_exato_falso [2 pares] |
| A-15 | PASSOU | test_multiplo_passo_invalido [0/-0.25] |
| A-16 | PASSOU | test_campos_limite_da_precisao_gravam_e_relem_identicos |
| A-17 | PASSOU | test_campos_recusam_valor_acima_da_precisao [2 campos] |
| A-18 | PASSOU | test_conversao_dinheiro_notacao_com_expoente_normaliza |
| A-19 | PASSOU | test_campos_recusam_float_na_validacao |
| A-20 | PASSOU | test_app_de_testes_fora_da_producao; configurações inspecionadas |

### R02 — ENCERRADO; decisão da fatia: APROVADO

Inspeção de `apps/nucleo/valores.py` confirma uso de as_tuple sem normalize antes da validação. Probes independentes repetiram as duas entradas originais com texto e Decimal (quatro casos), todos recusados com ValorInvalido. Regressões versionadas de zeros finais equivalentes também passaram. Referências: funcional §4.2/§9, infraestrutura 4.12, spec e A-3/A-7.

Matriz executada em `tests/tecnicos/test_nucleo_valores.py` e `test_nucleo_campos_decimais.py`. Nenhum achado funcional aberto nesta fatia.

### Reavaliação de E01-TDD

Conferido o complemento do implementador: comando `uv run pytest -q`, baseline 111, Red declarado de 11 failed/116 passed, nomes das regressões, causas e Green de 127 passed. O diff mantém os testes anteriores e acrescenta 16 casos; não houve remoção ou afrouxamento para esconder defeitos. Os registros transcritos são aceitos como evidência documental prevista no AGENTS.md, que não exige logs brutos ou um commit por ciclo. A ordem histórica não foi observada diretamente pelo revisor e não pode ser reconstruída a partir do commit único: essa limitação permanece explícita. E01-TDD fica encerrado como ressalva documental, não como bloqueador adicional. Os testes executados agora comprovam o estado atual, não o passado.

Próximo gate desta fatia: encerrado. A E01 global continua reprovada pelo bloqueador de E01-05.
