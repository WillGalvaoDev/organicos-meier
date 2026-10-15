# E01-01 — Critérios de aceitação

Verificação por execução do CI no GitHub (exceção técnica ao TDD, ver `spec.md`). Cada critério precisa de evidência no `review.md`: link da execução e resultado.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | AGENTS.md §8 | positivo | o código atual da `main`, com os testes de ambiente | um push é feito para `main` | o job `verificacoes` roda ruff check, ruff format --check, mypy e pytest, e termina verde |
| A-2 | AGENTS.md §8 | positivo | uma branch com pull request para `main` | o pull request é aberto ou atualizado | o job roda e o status aparece no pull request |
| A-3 | AGENTS.md §8 | negativo | uma branch temporária com um teste que falha de propósito | o pull request é aberto | o job termina vermelho na etapa do pytest |
| A-4 | AGENTS.md §8 | negativo | uma branch temporária com erro de lint (por exemplo, import não usado) | o pull request é aberto | o job termina vermelho na etapa do ruff |
| A-5 | AGENTS.md §8 | negativo | uma branch temporária com erro de tipo | o pull request é aberto | o job termina vermelho na etapa do mypy |
| A-6 | Infra §2 | negativo | uma branch temporária com `pyproject.toml` alterado sem atualizar o `uv.lock` | o pull request é aberto | o job termina vermelho na instalação |
| A-7 | Infra §5 | positivo | o job em execução | o pytest roda `tests/ambiente/test_ambiente.py::test_banco_e_postgres` | o teste passa contra o Postgres 17 do serviço, e não contra SQLite |
| A-8 | Spec da fatia, invariantes | positivo | o workflow | ele é inspecionado | não referencia segredos do repositório |
| A-9 | D-1 | negativo | a proteção da `main` configurada e o pull request de A-3 com o job vermelho | tento fazer o merge, inclusive como administrador | o GitHub recusa o merge |
| A-10 | D-1 | negativo | a proteção da `main` configurada | tento um push direto e um push forçado para a `main` | o GitHub recusa os dois |
| A-11 | D-1 | positivo | a proteção da `main` configurada | consulto a regra com `gh api repos/{dono}/{repo}/branches/main/protection` | o status obrigatório é `verificacoes`, com *strict* e regra aplicada a administradores |
| A-12 | D-1, AGENTS.md §6 | positivo | o repositório | consulto as configurações de segurança | *secret scanning* e *push protection* estão ativos |

As branches temporárias de A-3 a A-6 são descartadas depois da verificação, sem merge.

Ordem de execução, porque o status `verificacoes` só pode ser exigido depois de ter rodado uma vez:

1. A fatia é desenvolvida numa branch, e o pull request dela para a `main` gera a primeira execução (A-2, A-7 e A-8).
2. A proteção e a varredura de segredos são configuradas (A-11 e A-12).
3. Rodam as branches temporárias (A-3 a A-6) e as tentativas bloqueadas (A-9 e A-10).
4. O merge do pull request desta fatia já passa pela proteção, e o push resultante na `main` comprova o A-1.

## Mapeamento para verificação

| Critério | Evidência esperada |
|---|---|
| A-1, A-2, A-7 | link da execução verde e trecho do log do pytest |
| A-3 a A-6 | link de cada execução vermelha e etapa em que falhou |
| A-8 | trecho do `ci.yml` |
| A-9, A-10 | mensagem de recusa do GitHub em cada tentativa |
| A-11, A-12 | saída das consultas `gh api` |
