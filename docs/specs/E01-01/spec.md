# E01-01 — Integração contínua

Fatia 1 de 5 da milestone **E01 — Fundação de engenharia**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7 (base declarada: especificação v1.6)
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Toda fatia seguinte precisa de uma verificação automática e reproduzível: testes, lint, formatação e tipos, contra um Postgres real. Esta fatia cria o pipeline de CI no GitHub Actions. Ela não implementa regra de negócio.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| AGENTS.md §4.7 e §8 | Encerramento só com testes relevantes verdes. Suíte, lint e tipos passam. |
| AGENTS.md §3, agente 3 | O revisor executa verificações de forma independente sempre que possível. |
| Infraestrutura §2 e §7 (fase 1) | Postgres, Django, testes contra o simulador em desenvolvimento e homologação. |
| Infraestrutura §5 | Transações e travas reais (`select_for_update`) exigem Postgres, não SQLite. |
| README.md | Comandos de verificação: `pytest`, `ruff check`, `ruff format --check`, `mypy`. |

## Escopo

**Dentro:**

- Workflow do GitHub Actions disparado por push em `main` e por pull request para `main`.
- Serviço Postgres 17 no job, com o mesmo usuário, senha e banco de `compose.yaml`.
- Instalação com uv a partir do `uv.lock`, sem alterar o lockfile.
- Etapas: `ruff check`, `ruff format --check`, `mypy`, `pytest`.
- Falha em qualquer etapa deixa o job vermelho.
- Proteção da branch `main` no GitHub (decisão D-1), configurada depois da primeira execução verde do job.
- Varredura de segredos e bloqueio de push com segredo (*secret scanning* e *push protection*), gratuitos em repositório público.
- `README.md`: seção curta sobre o fluxo de contribuição (branch, pull request, CI obrigatório).

**Fora:**

- Deploy, homologação e segredos de produção (E16).
- Revisão obrigatória por aprovação no GitHub: o projeto tem um único responsável, e a revisão independente é registrada no `review.md`.
- Relatórios de cobertura com limite mínimo (a definir quando houver código de domínio).

## Regras e estados

- **Gatilhos:** `push` para `main` e `pull_request` com destino `main`.
- **Ambiente:** Ubuntu do GitHub Actions, Python 3.12 (o mesmo de `.python-version`), uv.
- **Dependências:** instaladas com o lockfile travado (`uv sync --locked`). Se o `pyproject.toml` divergir do `uv.lock`, o job falha.
- **Banco:** Postgres 17 como serviço, com verificação de saúde antes dos testes. `DATABASE_URL` aponta para ele. Nenhum segredo real é usado: a `SECRET_KEY` de teste vem de `config/settings/test.py`.
- **Ordem das etapas:** lint, formatação, tipos, testes. O job para na primeira etapa que falhar e termina vermelho.
- **Saída:** o resultado do pytest aparece no log do job, com o resumo de testes.
- **Proteção da `main`:**
  - o status `verificacoes` é obrigatório para merge;
  - a branch precisa estar atualizada com a `main` antes do merge (*strict*);
  - a regra vale também para administradores;
  - push direto, push forçado e exclusão da `main` são bloqueados.

  A partir daí, toda mudança, inclusive de documentação, entra por pull request.

## Interfaces

- Arquivo `.github/workflows/ci.yml`.
- Um job, `verificacoes`, com status visível no commit e no pull request.
- Regra de proteção da `main` e configurações de segurança do repositório, aplicadas com `gh api`. Os comandos usados ficam registrados no `review.md`, para que a configuração seja reproduzível.

## Invariantes

- O CI usa as mesmas versões travadas do desenvolvimento local (`uv.lock`, Python 3.12, Postgres 17).
- O CI não depende de serviços externos além do GitHub Actions e das imagens públicas do Postgres.
- Nenhum segredo é necessário para o job passar.

## Casos-limite e concorrência

- Lockfile desatualizado: o job falha na instalação.
- Postgres ainda iniciando: os testes só começam depois da verificação de saúde.
- Execuções simultâneas em commits diferentes não compartilham banco, porque cada job tem seu próprio serviço.

## Exceção técnica ao TDD

O workflow e as configurações do repositório não têm comportamento exercitável pelo pytest. A verificação é a própria execução do CI e a tentativa real das operações bloqueadas (critérios em `acceptance.md`), registradas como evidência no `review.md`, conforme o AGENTS.md §3.

## Dependências e decisões

- **D-1 (decidida em 2026-10-15):** o repositório passou a ser público, o que libera a proteção de branch no plano gratuito. O repositório já está público. A proteção e a varredura de segredos são configuradas nesta fatia.
- Consequência: tudo o que está versionado fica visível publicamente. O `.env` e qualquer segredo continuam fora do Git, e a varredura de segredos passa a ser uma segunda barreira.
- Sem decisões em aberto.
