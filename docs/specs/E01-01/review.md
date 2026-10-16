# E01-01 — Revisão

Estado atual: **APROVADO** no commit `06e2faf` (revalidação independente de 2026-10-16 ao final).

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
| A-1 | PASSOU | [run 38734822451](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38734822451) — push de 6b7b9ab, todas as etapas verdes. |
| A-2 | PASSOU | [run 38736289522](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38736289522) — novo PR #17, branch derivada de 6b7b9ab com commit vazio, verificacoes verde. |
| A-3 | PASSOU | [run 38736502533](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38736502533) — PR #13, falha proposital somente em pytest; lint/formatação/tipos verdes. |
| A-4 | PASSOU | [run 38736259905](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38736259905) — PR #14, import os não usado, falha em ruff check. |
| A-5 | PASSOU | [run 38736267742](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38736267742) — PR #15, str atribuída a int, falha em mypy. |
| A-6 | PASSOU | [run 38736280240](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38736280240) — PR #16, dependência acrescentada sem lock; uv sync --locked recusa lock desatualizado. |
| A-7 | PASSOU | test_banco_e_postgres passou localmente; workflow postgres:17 e log do CI confirmam 17.11. |
| A-8 | PASSOU | ci.yml relido: sem secrets.*, credenciais locais de teste; permissions contents: read. |
| A-9 | PASSOU | Tentativa administrativa de merge do PR #13 vermelho recusada: Required status check "verificacoes" is failing. |
| A-10 | PASSOU | Push direto e forçado com lease do commit verde do PR #17 já fechado: ambos GH006, Changes must be made through a pull request. |
| A-11 | PASSOU | gh api: verificacoes obrigatório, strict=true, enforce_admins.enabled=true; PR obrigatório com zero aprovações humanas. |
| A-12 | PASSOU | gh api: secret_scanning e secret_scanning_push_protection enabled. |

### R01 — ENCERRADO; decisão da fatia: APROVADO

A configuração remota foi consultada novamente: required_pull_request_reviews.required_approving_review_count=0, required_status_checks.strict=true, contexts=[verificacoes], enforce_admins.enabled=true, allow_force_pushes.enabled=false e allow_deletions.enabled=false. Rulesets adicionais: []. Credencial utilizada: WillGalvaoDev, admin=true, conforme API. Segurança: secret scanning e push protection ativos.

Reexecução real com novo commit vazio `3a4337034ca4a4b757b7d136ae05e7ec48360355`, baseado em 6b7b9ab. PR #17 e CI verde; PR fechado sem merge antes dos pushes:

```powershell
git push origin 3a4337034ca4a4b757b7d136ae05e7ec48360355:refs/heads/main
git push --force-with-lease=refs/heads/main:6b7b9ab4282cc87b8f211385ebeb8be264b864da origin 3a4337034ca4a4b757b7d136ae05e7ec48360355:refs/heads/main
```

Ambos terminaram com exit 1, GH006, `Changes must be made through a pull request` e `protected branch hook declined`. A modalidade forçada foi protegida por lease do SHA auditado; não se tentou reescrever histórico. A main permaneceu exatamente em 6b7b9ab.

A-9 foi reexecutado com `gh pr merge 13 --merge --admin --match-head-commit 73ed6f1d260bd55746adf602659993f8807585d8`: recusa GraphQL `Required status check "verificacoes" is failing. (mergePullRequest)`. PR permaneceu OPEN, mergedAt=null, até ser fechado na limpeza.

Probes A-3 a A-6 foram realizados em branches temporárias derivadas do commit auditado. A primeira tentativa de A-3 (run 38736249206) falhou antes, em mypy, por comparação de literais 1 == 2; foi corrigido apenas o probe para `assert len([1]) == 2`, gerando a execução válida da matriz. Não houve alteração do projeto para fazê-lo passar.

PRs #13 a #17 foram fechados sem merge; branches remotas/locais temporárias e worktree de CI removidos. Nenhuma regra remota foi alterada. A-1 usa a execução de push já existente do SHA exato: não foi gerado novo push na main. A exceção técnica ao TDD continua adequada. Próximo gate desta fatia: encerrado; a E01 global continua reprovada por E01-05.

## Revalidação independente — e7eec3c — 2026-10-15

Revisor: Codex, agente 3. Commit exato: `e7eec3c81b9455af94cb23acb0adc2886a4f97f5`. **Decisão desta fatia: APROVADO, mantida.** A E01 global continua REPROVADA por R05/A-7 da E01-05, conforme relatório atualizado daquela fatia.

O diff desde 6b7b9ab altera apenas o utilitário/testes de concorrência e relatórios. Não modifica código de produção, configurações, workflow, dependências, documentos-base ou critérios de aceitação. Reexecutados `uv run pytest -q` (130 passed em 6,89 s, Postgres 17.11 real), `uv run ruff check .` (limpo), `uv run ruff format --check .` (54 arquivos), `uv run mypy .` (40 arquivos, sem erros), `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` (sem mudanças) e `uv run python manage.py check --settings=config.settings.test` (0 issues). Os critérios automatizados das matrizes anteriores permanecem verdes.

Os 11 probes independentes da revalidação anterior foram repetidos sem alteração e passaram (3,78 s), incluindo R02, R03, R04 e o cenário anterior de R05. A aprovação das quatro primeiras fatias permanece; o novo cenário falho de conexão em abertura está documentado na E01-05. CI do SHA auditado: [run 38739955114](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38739955114), 130 passed em 6,64 s.

Configuração remota consultada novamente: PR obrigatório com zero aprovações humanas, verificacoes obrigatório/strict, enforce_admins=true, force pushes/deletions=false; secret scanning e push protection enabled. Os cenários negativos A-3 a A-6 e tentativas reais A-9/A-10 da revisão anterior continuam aplicáveis, pois workflow e configuração não mudaram. Não foram criados novos PRs negativos nem repetidas tentativas de push/merge nesta rodada. A-1 confirmado pelo CI do SHA exato; A-2 pelo CI verde do PR #18, run 38739814975. R01 permanece encerrado.

## Revalidação independente — 523cd9c — 2026-10-15

Revisor: Codex, agente 3. SHA: `523cd9c2780ba50fdd4f962873c86844b1ca7b8b`. **APROVADO nesta fatia, decisão mantida.** A E01 global continua REPROVADA por R05/A-7 da E01-05.

O diff desde e7eec3c altera somente utilitário/testes de concorrência e relatórios; código de produção, configurações, workflow, dependências, fontes de verdade e critérios permanecem iguais. Reexecução independente: `uv run pytest -q` → 131 passed em 7,81 s, Postgres 17.11; ruff check limpo; ruff format --check: 54 arquivos; mypy: 40 arquivos sem erros; makemigrations --check --dry-run (settings test): sem mudanças; manage.py check (settings test): 0 issues. Doze probes anteriores também passaram, sem modificação. A única falha adicional está reproduzida no relatório E01-05.

CI de push do SHA exato: [run 38743418962](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38743418962), 131 passed em 8,40 s, Postgres 17.11. Ressalvas documentais de TDD já registradas permanecem; não surgiu achado nesta fatia. Nenhuma implementação foi alterada pelo revisor.

Proteção e segurança remotas consultadas novamente: PR obrigatório com zero aprovações humanas, verificacoes obrigatório/strict, enforce_admins=true, force pushes/deletions=false; secret scanning e push protection ativos. CI do PR #19 também verde (run 38743263411). Os cenários negativos reais da revalidação 6b7b9ab permanecem válidos para workflow/configuração inalterados; não foram recriados nesta rodada. R01 permanece encerrado.


## Revalidação independente — b709ce3 — 2026-10-15

Revisor: Codex, agente 3. SHA auditado: `b709ce3ac41aa9dee593f7975efc88c6030019d0` (main, merge do PR #20). **APROVADO nesta fatia, mantida a decisão.** Fontes de verdade e implementação desta fatia não mudaram; alterações funcionais desta rodada estão no apoio de concorrência da E01-05. Matrizes anteriores permanecem aplicáveis, com a cobertura automatizada reexecutada na suíte completa: `uv run pytest -q`, **139 passed em 40,51 s**, Postgres real. R02, R03 e R04 também permanecem verdes nos probes independentes anteriores. Não surgiu achado nesta fatia.

Verificações: `uv run ruff check .` limpo; `uv run ruff format --check .`, 54 arquivos; `uv run mypy .`, 40 arquivos sem erros; `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`, sem mudanças; `uv run python manage.py check --settings=config.settings.test`, zero issues. CI do SHA exato: [run 38748612333](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38748612333), sucesso, 139 testes; PR #20: run 38748350219, sucesso. Mantida a limitação histórica das evidências TDD declaradas, já registrada nas revisões anteriores.

A E01 global continua **REPROVADA**, agora pela incompatibilidade técnica R06/A-17 documentada na E01-05; o vazamento R05 foi corrigido. Nenhum código de implementação ou teste versionado foi alterado pelo revisor.

Proteção remota consultada novamente: PR obrigatório, zero aprovações humanas, `verificacoes` obrigatório e strict, enforce_admins=true, force pushes/deletions=false. Secret scanning e push protection ativos. R01 permanece encerrado. Os cenários negativos reais A-3 a A-6 e A-9/A-10 da revisão 6b7b9ab não foram repetidos: workflow e proteções permanecem iguais. A-1/A-2 confirmados pelos CIs acima; nenhuma configuração remota foi alterada.


## Revalidação independente — 06e2faf — 2026-10-16

Revisor: Codex, agente 3. SHA auditado: `06e2fafef33b1beb5ae346e2ff6fd590a0184689`. **APROVADO nesta fatia, decisão mantida. E01 global APROVADA.** Implementação e requisitos desta fatia permanecem inalterados. R06 da E01-05 foi encerrado pela compatibilização do contrato com timeout fixo e pela revalidação independente; R01 a R05 continuam encerrados.

Evidências desta rodada: `uv run pytest -q`, **143 passed em 40,28 s**, Postgres 17.11; matriz A-1 a A-18 da E01-05 reexecutada, módulo com **27 passed nas cinco execuções consecutivas**. Ruff check limpo, format check 54 arquivos, mypy 40 arquivos sem erros, makemigrations --check --dry-run sem mudanças e manage.py check zero issues (settings test). CI do SHA exato [38897195100](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38897195100): sucesso. Mantidas as evidências anteriores e suas limitações documentais de TDD; não surgiu achado nesta fatia. Relatório detalhado da revalidação em `../E01-05/review.md`.

Somente os relatórios foram alterados pelo revisor, na branch `revisao/e01-06e2faf`, sem commit/push/merge. Gate de revisão da E01 encerrado.

Proteção e segurança remotas reconferidas: PR obrigatório, zero aprovações humanas, `verificacoes` obrigatório/strict, enforce_admins=true, force pushes/deletions=false; secret scanning e push protection ativos. R01 permanece encerrado. Os cenários negativos remotos das revisões anteriores não foram recriados porque workflow e regras não mudaram; nenhuma configuração remota foi alterada.
