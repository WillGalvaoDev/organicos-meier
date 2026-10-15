# E01-01 — Revisão

Estado atual: **REPROVADO** (revisão independente ao final).

Abaixo, relato histórico do implementador, preservado como evidência declarada.

Exceção técnica ao TDD conforme `spec.md` (workflow e configuração do repositório não têm comportamento exercitável pelo pytest).

## Evidências

| Critério | Evidência |
|---|---|
| A-2, A-7, A-8 | PR #1, job `verificacoes` verde (29 s): https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38730159817. `ci.yml` não usa `secrets.*`. |
| A-3 | PR temporário `tmp-a3-pytest`, falhou na etapa `pytest`: https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38730562656 (a primeira tentativa falhou no mypy por um erro do próprio teste de falha, corrigido; a execução válida é esta). |
| A-4 | `tmp-a4-ruff`, falhou em `ruff check`: .../runs/38730329306 |
| A-5 | `tmp-a5-mypy`, falhou em `mypy`: .../runs/38730336488 |
| A-6 | `tmp-a6-lock`, falhou em `Instalar dependências (lockfile travado)`: .../runs/38730343938 |
| A-9 | `gh pr merge <n> --merge --admin` no PR do A-3: `GraphQL: Required status check "verificacoes" is failing. (mergePullRequest)` |
| A-10 | `git push origin main` e `git push --force origin main`: `[remote rejected] main -> main (protected branch hook declined)` / `Required status check "verificacoes" is expected` |
| A-11 | `gh api repos/WillGalvaoDev/organicos-meier/branches/main/protection`: contexts `["verificacoes"]`, strict true, enforce_admins true, force pushes e exclusão false |
| A-12 | `secret_scanning: enabled`, `secret_scanning_push_protection: enabled` |
| A-1 | Push na `main` após o merge do PR #1, job `verificacoes` verde: https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38730849149 |

## Comandos de configuração (reprodutíveis)

```
gh api -X PUT repos/WillGalvaoDev/organicos-meier/branches/main/protection --input prot.json
# prot.json: {"required_status_checks":{"strict":true,"contexts":["verificacoes"]},"enforce_admins":true,
#   "required_pull_request_reviews":null,"restrictions":null,"allow_force_pushes":false,"allow_deletions":false}
gh api -X PATCH repos/WillGalvaoDev/organicos-meier \
  -f 'security_and_analysis[secret_scanning][status]=enabled' \
  -f 'security_and_analysis[secret_scanning_push_protection][status]=enabled'
```

## Limitações

- Na data deste relato histórico, a revisão independente ainda não havia ocorrido. Resultado atual ao final.
- As branches e PRs temporários foram fechados sem merge e as branches apagadas; as execuções permanecem no histórico do Actions.

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

| Critérios | Verificação |
|---|---|
| A-1, A-2 | Histórico de push/PR verde consultado com `gh run list`; push atual e PR #9 verdes. Evidências originais do PR #1 preservadas acima. |
| A-3 | `gh run view 38730562656 --json conclusion,jobs`: falha em pytest, etapas anteriores verdes. |
| A-4 | Run 38730329306: falha em ruff check. |
| A-5 | Run 38730336488: falha em mypy. |
| A-6 | Run 38730343938: falha na instalação travada. |
| A-7 | Workflow postgres:17, log do CI e banco local confirmam 17.11. |
| A-8 | Workflow inspecionado: sem secrets.*, credenciais descartáveis de teste. |
| A-9 | Recusa histórica registrada pelo implementador; status obrigatório aplicado a administradores confirmado. Merge não tentado novamente. |
| A-10 | Não atendido integralmente: bloqueio por check ausente não prova exigência de PR (R01). Force push desabilitado. |
| A-11 | Consulta atual confirma verificacoes, strict=true, enforce_admins=true, force pushes/deletions=false. |
| A-12 | Consulta atual confirma secret scanning e push protection enabled; repositório público. |

### R01 — Bloqueador: proteção não exige pull request

Origem: spec E01-01, proteção da main, A-10 e README (toda mudança por PR).
Local: configuração remota e payload histórico deste arquivo (`required_pull_request_reviews: null`).

```powershell
gh api repos/WillGalvaoDev/organicos-meier/branches/main/protection
gh api repos/WillGalvaoDev/organicos-meier/rulesets
gh api repos/WillGalvaoDev/organicos-meier --jq '.security_and_analysis'
```

Resultado: a proteção não contém required_pull_request_reviews e a lista de rulesets é vazia. Não há regra exigindo PR. A mensagem histórica `Required status check "verificacoes" is expected` comprova somente recusa de commit sem check. A configuração permite push direto de commit que satisfaça os checks, conforme a [documentação oficial sobre status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging). Conclusão por inspeção da configuração e documentação; não foi feito push capaz de alterar main na auditoria.

Devolução: exigir PR sem exigir aprovação de outro humano (fora do escopo), manter status/strict/admins e validar recusa de push também para commit já verde. Registrar recusa pela exigência de PR, não apenas por check ausente. Configurações remotas não alteradas pelo revisor.

### TDD e próximo gate

Exceção técnica expressamente prevista e adequada. Execuções positivas e negativas do CI confirmadas; tentativas históricas de push/merge não repetidas. Revalidar R01 e A-9 a A-12 após correção.

## Correção após a reprovação (implementador)

**R01 — proteção não exigia pull request.** Corrigido na configuração remota (exceção técnica ao TDD, como na fatia):

```
gh api -X PUT repos/WillGalvaoDev/organicos-meier/branches/main/protection --input prot.json
# prot.json: required_status_checks {strict: true, contexts: [verificacoes]}, enforce_admins: true,
#   required_pull_request_reviews {required_approving_review_count: 0}, restrictions: null,
#   allow_force_pushes: false, allow_deletions: false
```

Resposta: `required_approving_review_count: 0` (PR exigido, sem aprovação de outro humano, conforme o escopo), `strict: true`, `enforce_admins: true`, `allow_force_pushes: false`.

Validação: ver "Validação R01" ao final.

Verificação após as correções (todas as fatias, mesma execução):

```
uv run pytest -q                 -> 127 passed (111 anteriores + 16 regressões)
uv run ruff check .              -> All checks passed
uv run ruff format --check .     -> ok
uv run mypy .                    -> Success: no issues found in 40 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
```

### Validação R01

1. **Primeira tentativa, sem valor probatório.** Com o CI do PR #10 verde, `git push origin HEAD:main` foi aceito. O commit era a cabeça de um PR aberto e que cumpria as regras, e o GitHub tratou o push como o merge do PR (#10 passou a `MERGED`). O conteúdo que entrou em `main` é o do PR #10, com `verificacoes` verde (run 38734352142). Isso não mostra se a regra de PR vale para commit fora de PR.
2. **Verificação correta.** Branch `tmp-r01-pr-obrigatorio` com commit vazio, PR #11 aberto, `verificacoes` verde (run 38734533703), PR fechado sem merge, e então:

```
git push origin HEAD:main
remote: error: GH006: Protected branch update failed for refs/heads/main.
remote: - Changes must be made through a pull request.
 ! [remote rejected] HEAD -> main (protected branch hook declined)

git push --force origin HEAD:main
 ! [remote rejected] HEAD -> main (protected branch hook declined)
```

`main` permaneceu em `6fe5b84`. A recusa vem da exigência de pull request, com o check já verde, para administrador (`enforce_admins: true`). A branch temporária e o PR #11 foram descartados.

