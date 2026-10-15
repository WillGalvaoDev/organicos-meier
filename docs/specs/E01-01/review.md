# E01-01 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

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
| A-1 | Execução do push na `main` após o merge do PR #1 (registrada no review da fatia seguinte) |

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

- Nenhuma revisão independente feita ainda. A-1 depende do merge.
