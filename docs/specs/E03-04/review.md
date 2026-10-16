# E03-04 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **APROVADO** sobre `0ceb171` (2026-10-16). E03 global: **REPROVADO**. Evidências históricas do implementador abaixo; revisão independente ao final.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

## Ciclos TDD

**Andaime (sem comportamento, justificado):** app `apps.interesses` com `ParcelaDeInteresse` só
com campos (`sequencia` com marcador `db_default=0`), `consultas.py` com corpos triviais,
`ParcelaFactory`, migração `0001_initial`. Suíte antes do Red: 860 passando.

**Red** (`uv run pytest tests/tecnicos/test_interesses_*.py`): **32 falhas, 2 passando**. Motivos:
`UniqueViolation` em `sequencia` (o marcador `0` do andaime repete na segunda parcela: a sequência
do banco ainda não existe), `DID NOT RAISE IntegrityError` nas restrições, triggers e exclusão,
`'0' == '0.000'` em `total_reservado`, ausência de `FOR UPDATE` na leitura travada. Os 2 que
passavam: `quantidades_em_uso` sem parcelas (`[]`) e as atualizações válidas do cenário 75 (sem
restrição, tudo é aceito) — guardas de regressão. Nota de honestidade: as falhas por `UniqueViolation`
são o motivo esperado ("falta a sequência do banco"), mas aparecem como erro de integridade e não
como asserção; os testes de restrição falham por `DID NOT RAISE`.

**Green:** migração `0002_restricoes` com a sequência `interesses_parcela_sequencia`, os seis
`CHECK`s e as triggers (`gatilhos.py`); `save()` que relê a sequência após a criação;
`consultas.py`. Resultado: `test_interesses_*.py` 34 passando; suíte completa **894 passando**;
`ruff check`, `ruff format`, `mypy --strict`, `makemigrations --check` limpos.

**Refactor / ajustes:** os dois blocos `pytest.raises` com várias linhas (PT012) foram movidos para
o auxiliar `_gravar`, sem mudar asserções (feito junto do Green, depois do Red). A tentativa de
usar `DB_DEFAULT` falhou (não existe nesta versão do Django); trocada pela releitura da sequência.

## Matriz de critérios

| Critério | Teste |
|---|---|
| A-1 | `test_interesses_parcela_modelo.py::test_sequencias_distintas_e_crescentes_e_quantidades_exatas` |
| A-2 | `::test_banco_recusa_troca_das_colunas_imutaveis` (4 colunas) |
| A-3 | `::test_banco_recusa_exclusao` |
| A-4 | `::test_banco_recusa_insercao_invalida`, `::test_banco_recusa_atualizacao_invalida`, `::test_banco_recusa_soma_acima_do_original_na_atualizacao` |
| A-5 | `::test_atualizacoes_validas_do_cenario_75` |
| A-6, A-7 | `test_interesses_consultas.py::test_total_reservado_soma_ativas_e_em_pedido_do_produto`, `::test_total_reservado_sem_parcelas_e_zero` |
| A-8 | `::test_quantidades_em_uso_inclui_reservadas_e_pendentes` |
| A-9 | `test_interesses_concorrencia.py::test_vinte_insercoes_em_paralelo_recebem_sequencias_distintas` |
| A-10 | `test_interesses_parcela_modelo.py::test_sequencia_informada_na_criacao_e_ignorada`, `::test_insercao_por_sql_tambem_ignora_a_sequencia_informada` |
| A-11 | `test_interesses_consultas.py::test_leitura_com_trava_usa_for_update_ordenado_pela_sequencia` |

## Decisões técnicas (derivadas, sem alterar regra de negócio)

- **A-10 (escolha registrada):** o valor informado é **ignorado**. A trigger `BEFORE INSERT`
  sempre grava `nextval` da sequência, inclusive para SQL direto; o `save()` relê a coluna para
  que o objeto em memória não guarde o valor informado. O `db_default=0` do campo é apenas o
  marcador do DEFAULT.
- **A-11 (forma de travar registrada):** parâmetro `travar: bool = False` em `total_reservado` e
  `quantidades_em_uso`; com `travar=True` as linhas são lidas com `select_for_update()` e
  `order_by("sequencia")`. `total_reservado` soma em Python no caso travado, porque `FOR UPDATE`
  não combina com agregação.
- Sem `travar`, `total_reservado` usa `SUM` no banco e `quantidades_em_uso` ainda devolve na ordem
  de `sequencia`.
- `CHECK` extra `parcela_situacao_valida` (situação restrita aos quatro valores), além dos
  pedidos pela especificação.
- A trigger de colunas imutáveis só dispara quando o valor muda (`IS DISTINCT FROM`), então o
  `save()` comum do ORM, que reenvia as colunas, passa.

## Limitações de verificação

- `total_reservado` não filtra por rodada ativa: a parcela ainda não tem vínculo com a rodada
  (spec, "Fora do escopo"); a E05 ajusta sem mudar a assinatura.
- O teste A-9 prova sequências distintas em 20 inserções simultâneas, não a ordem de commit.
- A sequência do banco tem lacunas após rollback (comportamento normal do Postgres); a FIFO
  depende da ordem, não de valores contíguos.

## Revisão independente — 0ceb171 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: APROVADO.**

A-1 a A-11: sequência atribuída pelo banco, imutabilidade, não exclusão, CHECKs, leituras e travas cobertos e verdes, inclusive vinte inserções concorrentes. Sem achado impeditivo nesta fatia; vínculo da parcela com rodada continua no escopo futuro documentado.

Verificação comum: `uv run pytest -q` — **1058 passed em 147,85 s**; ruff check limpo; ruff format — 238 arquivos; mypy — 193 arquivos sem erros; checks Django e migrações sem pendências. Os probes adicionais de fronteira terminaram em **8 failed, 8 passed em 4,36 s**, reproduzindo E03-R01. Não houve correção de produção ou testes pelo revisor.

Comandos completos, achados, reprodução, limites e parecer global estão em [E03-08/review.md](../E03-08/review.md), na seção de revisão independente deste SHA. Os relatos Red/Green anteriores foram conferidos com o diff e a cobertura; a execução Green é independente, a cronologia Red é evidência documentada pelo implementador.
