# Imagem de homologação e produção (E16-01). Dois processos usam esta mesma imagem: web e worker
# (comandos no fly.toml). Nada secreto entra na imagem: os segredos vêm de `fly secrets`.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Cliente do PostgreSQL 17 (a mesma família do banco) e o `age`, usados pelo backup (E16-04).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg age \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-17 \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

# Os estáticos são coletados na construção. O comando carrega as configurações de produção, que
# exigem variáveis: valores fictícios valem só para este passo, na linha do comando (nunca em ENV
# ou ARG), e não ficam na imagem final. Todo host usa `construcao.invalid` (RFC 2606) ou
# `localhost`; nada se conecta ao banco, ao R2 ou ao Sentry. Cada variável lida sem padrão em
# `config/settings` precisa estar aqui (conferido por tests/ambiente).
RUN DJANGO_SETTINGS_MODULE=config.settings.prod \
    SECRET_KEY=chave-ficticia-so-para-coletar-estaticos \
    DATABASE_URL="postgres://x:x@localhost:5432/x?sslmode=require" \
    ALLOWED_HOSTS=construcao.invalid \
    ORIGEM_PUBLICA=https://construcao.invalid \
    EMAIL_BACKEND=django.core.mail.backends.locmem.EmailBackend \
    DEFAULT_FROM_EMAIL=x@construcao.invalid \
    GOOGLE_CLIENT_ID=x GOOGLE_CLIENT_SECRET=x \
    AMBIENTE=homologacao SEGREDO_AVISOS_SIMULADOR=x \
    R2_ENDPOINT=https://construcao.invalid R2_BUCKET_ARQUIVOS=x \
    R2_ACCESS_KEY_ID=x R2_SECRET_ACCESS_KEY=x \
    R2_BUCKET_BACKUPS=x R2_BACKUP_ACCESS_KEY_ID=x R2_BACKUP_SECRET_ACCESS_KEY=x \
    BACKUP_CHAVE_PUBLICA_AGE=age1ficticiasoparaconstrucao \
    SENTRY_DSN=https://ficticio@construcao.invalid/0 \
    python manage.py collectstatic --noinput

RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "30"]
