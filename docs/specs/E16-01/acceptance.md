# E16-01 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Ambiente fictício completo (AF):** as variáveis da regra 9 com valores de teste, `AMBIENTE=homologacao`, `PROVEDOR_PAGAMENTOS=simulador`, `CANAL_WHATSAPP=desligado`, `ALLOWED_HOSTS=homolog.exemplo.fly.dev`, `ORIGEM_PUBLICA=https://homolog.exemplo.fly.dev` e `DATABASE_URL` apontando para o Postgres de teste com `sslmode=require`.
- **Carregamento das configurações:** em subprocesso, com `DJANGO_SETTINGS_MODULE=config.settings.prod` e o ambiente indicado, como nos testes de ambiente da E07-02.
- Os testes de `/saude/` usam o cliente de testes com as configurações de teste.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regra 6 | positivo | banco disponível | `GET /saude/` | 200, corpo `ok`, `text/plain`; nenhum cookie `Set-Cookie`; contagem de sessões e de `EntradaAuditoria` igual antes e depois. **Red esperado:** 404 |
| A-2 | Regra 6 | negativo | a consulta `SELECT 1` forçada a levantar `OperationalError` | `GET /saude/` | 503, corpo `indisponivel`, sem o texto do erro; um log com `OperationalError` |
| A-3 | Regra 6 | negativo | — | `POST`, `PUT` e `DELETE` em `/saude/` | 405 nos três |
| A-4 | Regra 6 | positivo | as configurações de teste com `SECURE_SSL_REDIRECT = True` e o `SECURE_REDIRECT_EXEMPT` de `prod.py`; requisição HTTP simples (sem `X-Forwarded-Proto`) |  `GET /saude/` | 200, sem redirecionamento para HTTPS; outra rota (por exemplo, `/entrar/`) responde 301 para HTTPS |
| A-5 | Regra 7 | negativo | AF sem `ALLOWED_HOSTS`; com `ALLOWED_HOSTS=*`; com `ALLOWED_HOSTS=` (vazio) | carregar | `ImproperlyConfigured` com "ALLOWED_HOSTS deve listar os domínios do ambiente." nos dois últimos; falha de variável ausente no primeiro |
| A-6 | Regra 7 | positivo | AF | carregar e ler `CSRF_TRUSTED_ORIGINS` | `["https://homolog.exemplo.fly.dev"]` |
| A-7 | Regra 8 | negativo | AF com `DATABASE_URL` sem `sslmode`; com `sslmode=disable`; com host `ep-x-pooler.sa-east-1.aws.neon.tech` e `sslmode=require` | carregar | as mensagens da regra 8, nessa ordem; nenhuma mensagem contém a senha nem a URL |
| A-8 | Regra 8 | positivo | AF com `sslmode=require`; depois com `sslmode=verify-full` | carregar e ler `DATABASES["default"]` | carrega nos dois; `CONN_MAX_AGE = 60` e `CONN_HEALTH_CHECKS = True` |
| A-9 | E07-02 (T-12) | negativo | AF com `AMBIENTE=producao` | carregar | a recusa do simulador continua ("O simulador de pagamentos não pode ser usado em produção.") |
| A-10 | Regra 10 | positivo | AF | carregar | `STORAGES["staticfiles"]["BACKEND"]` é o armazenamento comprimido com manifesto do WhiteNoise; o middleware do WhiteNoise vem logo depois do `SecurityMiddleware`; em `config.settings.test`, nada muda |
| A-11 | Regra 11 | positivo | AF | `manage.py check --deploy --fail-level WARNING` | saída 0, sem aviso; cada código em `SILENCED_SYSTEM_CHECKS` tem um comentário com o motivo |
| A-12 | Regras 1 e 2 | positivo | o `Dockerfile` e o `.dockerignore` | ler os arquivos | o `.dockerignore` exclui `.env`, `.venv`, `media`, `.git` e `staticfiles`; o `Dockerfile` usa `uv sync --locked --no-dev`, define um usuário não `root` e instala o cliente PostgreSQL 17 e o `age`; nenhuma linha `ENV` com `SECRET_KEY`, `DATABASE_URL` ou senha |
| A-13 | Regras 3 a 5 | positivo | o `fly.toml` | ler com um leitor TOML | `primary_region = "gru"`; processos `web` (com `gunicorn config.wsgi`) e `worker` (com `procrastinate worker`); `release_command` com `migrate --noinput`; a verificação em `/saude/`; o `[env]` com as cinco variáveis da regra 5 e nenhuma das variáveis secretas da regra 9 |
| A-14 | Regra 12 | positivo | o workflow de CI | ler o YAML | um job que executa `docker build` sem `push`; o job `verificacoes` com os mesmos passos de antes (a E16-04 acrescenta os dela) |
| A-15 | Regras 1 a 3 | positivo | o job de CI do A-14 | executar no PR | a imagem é construída; dentro dela, `pg_dump --version` mostra a versão 17, `age --version` responde e `id -u` é diferente de 0 (passos de verificação no mesmo job) |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-4 | `tests/tecnicos/test_saude.py` |
| A-5 a A-11 | `tests/ambiente/test_homologacao.py` |
| A-12 a A-14 | `tests/ambiente/test_artefatos_de_implantacao.py` |
| A-15 | o job de CI (evidência: o resultado do job no PR, registrado no `review.md`) |
