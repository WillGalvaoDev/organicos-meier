# Orgânicos Méier

Regras de negócio: `organicos-meier-especificacao-funcional.md`. Arquitetura e fases: `organicos-meier-infraestrutura.md`. Método de trabalho: `AGENTS.md`.

## Ambiente de desenvolvimento

Requisitos: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker Desktop e Git.

```powershell
docker compose up -d db          # Postgres 17 em localhost:5433
                                 # (se o banco local já existia antes da E02-01, recrie-o:
                                 #  docker compose down -v ; docker compose up -d db ; uv run python manage.py migrate)
copy .env.example .env           # ajuste SECRET_KEY
uv sync                          # cria .venv com dependências e ferramentas de teste
uv run pytest                    # suíte de testes
uv run ruff check . ; uv run ruff format --check . ; uv run mypy .
```

### Envio de e-mails (E04-03)

Os avisos por e-mail ficam numa fila no banco e são enviados por uma tarefa periódica do
Procrastinate, a cada minuto. Em desenvolvimento, suba o *worker* ao lado do servidor:

```powershell
uv run python manage.py migrate                    # inclui as tabelas do Procrastinate
uv run python manage.py procrastinate worker       # processa a fila de envios
```

Sem o *worker*, os envios continuam pendentes; as notificações do site não dependem dele.
Em produção, o SMTP vem do ambiente (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`,
`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`), com os segredos em `fly secrets`.

> Desde a E03-01 o fornecedor tem campos obrigatórios novos. Bancos locais que já tenham
> fornecedores de teste devem ser recriados (`docker compose down -v`, `docker compose up -d db`,
> `uv run python manage.py migrate`), como na E02-01.

## Fluxo de contribuição

Toda mudança entra por branch e pull request para `main`; push direto é bloqueado. O job `verificacoes` do GitHub Actions (ruff check, ruff format --check, mypy e pytest contra Postgres 17) precisa estar verde e a branch precisa estar atualizada com a `main` para o merge.

## Estrutura

```
config/            configuração do Django (settings por ambiente, urls, wsgi)
apps/              apps de domínio, criadas por fatia
templates/ static/ telas no servidor (HTMX entra com a primeira tela)
apps/contas/       contas, papéis, e-mail normalizado e e-mails banidos
apps/fornecedores/ fornecedores: dados, cadastro e gestão pelo administrador (E03)
apps/nucleo/       núcleo técnico sem regra de negócio (valores, tempo, auditoria)
tests/apoio/       app só de testes (modelos de apoio e utilitários), registrado apenas em settings/test.py
tests/ambiente/    verificação do andaime técnico
tests/aceitacao/   cenários da especificação §16
tests/tecnicos/    testes técnicos T-n da infraestrutura
docs/specs/_modelo modelos de spec.md, acceptance.md e review.md (AGENTS.md §5)
```

## Exceção técnica registrada

A estrutura inicial (configuração, banco, ferramentas e modelos de documentação) é andaime sem comportamento de negócio. Por isso foi criada sem o ciclo Red → Green, como permite o AGENTS.md §3. django-allauth e Procrastinate estavam instalados, mas só entram em `INSTALLED_APPS` junto com a fatia que os usa, com testes escritos antes (o Procrastinate entrou na E04-03). Assim nenhuma rota, como um cadastro público, existe sem especificação.
