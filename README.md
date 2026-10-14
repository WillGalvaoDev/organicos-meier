# Orgânicos Méier

Regras de negócio: `organicos-meier-especificacao-funcional.md`. Arquitetura e fases: `organicos-meier-infraestrutura.md`. Método de trabalho: `AGENTS.md`.

## Ambiente de desenvolvimento

Requisitos: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker Desktop e Git.

```powershell
docker compose up -d db          # Postgres 17 em localhost:5433
copy .env.example .env           # ajuste SECRET_KEY
uv sync                          # cria .venv com dependências e ferramentas de teste
uv run pytest                    # suíte de testes
uv run ruff check . ; uv run ruff format --check . ; uv run mypy .
```

## Estrutura

```
config/            configuração do Django (settings por ambiente, urls, wsgi)
apps/              apps de domínio, criadas por fatia
templates/ static/ telas no servidor (HTMX entra com a primeira tela)
tests/ambiente/    verificação do andaime técnico
tests/aceitacao/   cenários da especificação §16
tests/tecnicos/    testes técnicos T-n da infraestrutura
docs/specs/_modelo modelos de spec.md, acceptance.md e review.md (AGENTS.md §5)
```

## Exceção técnica registrada

A estrutura inicial (configuração, banco, ferramentas e modelos de documentação) é andaime sem comportamento de negócio. Por isso foi criada sem o ciclo Red → Green, como permite o AGENTS.md §3. django-allauth e Procrastinate estão instalados, mas só entram em `INSTALLED_APPS` junto com a fatia que os usa, com testes escritos antes. Assim nenhuma rota, como um cadastro público, existe sem especificação.
