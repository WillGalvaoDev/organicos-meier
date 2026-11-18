# E16-01 — Registro do implementador

Agente 2.

## Red (observado antes do código de produção)

`uv run pytest -q tests/tecnicos/test_saude.py tests/ambiente` (arquivos inteiros, sem `-k`): **18 failed, 3 passed**.
- `test_saude.py` (A-1 a A-4): 404 em `/saude/` e `KeyError`/atributo ausente em `SECURE_REDIRECT_EXEMPT`.
- `test_homologacao.py` (A-5 a A-8, A-10 e A-11): `ALLOWED_HOSTS` aceito sem validação, sem `CSRF_TRUSTED_ORIGINS`, URL sem TLS ou com `-pooler` aceita, sem WhiteNoise.
- `test_artefatos_de_implantacao.py` (A-12 a A-14): `FileNotFoundError` (sem `Dockerfile`, `.dockerignore` nem `fly.toml`) e nenhum job `docker build`.
- Passaram de primeira 3 testes (guardas, sem Red), entre eles o A-9 (a recusa do simulador em produção já existia, E07-02).

Antes do Red foi adicionada só a dependência de desenvolvimento `pyyaml` (+ `types-pyyaml`), para ler o YAML do CI (A-14); sem ela o arquivo nem era coletado.

## Green

- `apps/nucleo/saude.py` e a rota `saude/` (A-1 a A-4): `SELECT 1` em `connections["default"]`, 200 `ok` / 503 `indisponivel`, só a classe do erro no log; `require_GET`; nada grava.
- `config/settings/prod.py`: `SECURE_REDIRECT_EXEMPT = [r"^saude/$"]`; `ALLOWED_HOSTS` obrigatório, sem lista vazia nem `*`; `CSRF_TRUSTED_ORIGINS` de `ORIGEM_PUBLICA`; TLS (`require` ou `verify-full`) e recusa de `-pooler`, com `CONN_MAX_AGE = 60` e `CONN_HEALTH_CHECKS`; WhiteNoise logo depois do `SecurityMiddleware` e `CompressedManifestStaticFilesStorage`. Dependências novas de produção: `gunicorn` e `whitenoise`.
- `Dockerfile` (Python 3.12, `uv sync --locked --no-dev`, `pg_dump` 17 pelo PGDG, `age`, usuário 10001, `collectstatic` com valores fictícios só naquele passo), `.dockerignore`, `fly.toml` e o job `imagem` do CI (sem `push`).

## Decisões técnicas e desvios

1. **`security.W021` (HSTS preload) silenciado** em `SILENCED_SYSTEM_CHECKS`, com o motivo no comentário: o preload é compromisso permanente e `*.fly.dev` não pode entrar na lista; volta com o domínio próprio (fase 2a). **`SECURE_HSTS_INCLUDE_SUBDOMAINS = True`** resolve a `security.W005`. O A-11 também pediu uma `SECRET_KEY` de 50+ caracteres no ambiente fictício (`security.W009`): só o AF de `test_homologacao.py` a usa.
2. **`.env` local isolado.** O `.env` do desenvolvedor (ignorado pelo git) preenche `ALLOWED_HOSTS` e escondia a ausência da variável (A-5). O subprocesso do teste neutraliza `environ.Env.read_env`.
3. **Testes existentes ajustados por consequência das variáveis novas obrigatórias** (nenhuma asserção removida): `_AMBIENTE_MINIMO` (`test_configuracao_producao.py`) ganhou `ALLOWED_HOSTS` e `sslmode=require`, e a `ORIGEM_PUBLICA` virou `https://homolog.exemplo.fly.dev`; `test_nucleo_campos_decimais.py::test_app_de_testes_fora_da_producao` define as mesmas variáveis no `monkeypatch` (como a E07-02 fez com `AMBIENTE`).
4. **Conexão do simulador (E07-R03):** `CONN_MAX_AGE`/`CONN_HEALTH_CHECKS` valem só para `default`, como a spec; a do simulador mantém os padrões.
5. **A-12:** o teste conta o `age` pela presença da palavra no `Dockerfile`.

## A-15 (imagem), evidência local

O CI não rodou (sem push). Localmente, `docker build -t organicos-meier:local .` terminou com código 0 e:
- `pg_dump --version`: `pg_dump (PostgreSQL) 17.12 (Debian 17.12-1.pgdg12+1)`;
- `age --version`: `1.1.1`;
- `id -u`: `10001`;
- nenhuma variável `SECRET_KEY` ou `DATABASE_URL` no ambiente da imagem; `collectstatic` rodou na construção (5 arquivos copiados).
O resultado do job no PR fica para o registro do revisor.

## Verificação

`uv run pytest -q tests/ambiente tests/tecnicos/test_saude.py tests/tecnicos/test_configuracao_producao.py tests/tecnicos/test_configuracao_pagamentos.py tests/tecnicos/test_nucleo_campos_decimais.py tests/tecnicos/test_pagamentos_fronteiras.py`: verde. Suíte completa, `ruff` e `mypy`: no fim da E16 inteira (registro na última fatia). Os testes e o código de cada passo foram commitados juntos; o Red foi observado como descrito acima. Sem push, PR nem merge.

## Correção encontrada na suíte completa da etapa (implementador, 2026-11-17)

A suíte completa acusou 19 falhas depois das E16-01 e E16-04: (a) a rota `/saude/` não declarava a política de acesso (`@publica`), e os testes que varrem as rotas (E02-10 e outras) a acusaram; (b) `test_nenhuma_tarefa_periodica_faz_aporte` (E09-05) executa todas as tarefas periódicas, e o `backup_diario`, sem as variáveis do R2 nos testes, levanta `BackupFalhou("configuracao")` como a regra 8 da E16-04 manda. Correção: `@publica` em `apps/nucleo/saude.py`; no teste da E09-05, a tarefa `backup_diario` passa a ser conferida com `pytest.raises(BackupFalhou, match="configuracao")` (as demais seguem como antes; a asserção de que nenhuma tarefa faz aporte não mudou).

**Suíte completa da E16 (E16-01 a E16-08):** `uv run pytest -q`: **3554 passed, 1 skipped (A-15 do backup, sem as ferramentas no Windows; passou no contêiner), 2 xfailed (A-3 e A-4 da E16-08, bloqueados por dependência)**, em 11 min 50 s. `ruff` e `mypy` (554 arquivos) limpos.


---

## Revisão independente — agente 3 — 2026-11-17

Base avaliada: `52f8745870ebfa007ad6a94edf7f968ae472d04e`, branch
`e16-especificacoes`, diff contra `02f8e91`. Requisitos lidos antes do código:
AGENTS.md, especificação funcional v1.7, infraestrutura v1.8 e as oito specs e
acceptances da E16. Registros do implementador acima preservados integralmente.
A evidência global de execução está no parecer da E16-08 abaixo.

**Veredito da fatia: REPROVADO.**

### E16-R01 — Bloqueador — imagem atual não constrói

Referências: E16-01 regras de construção/estáticos, A-12 e A-15;
`Dockerfile:34`, `config/settings/prod.py:82` e `.github/workflows/ci.yml` (job `imagem`).

Execução independente: `docker build -t organicos-meier:revisor-e16-52f8745 .`.
Resultado: código 1 no `RUN ... python manage.py collectstatic --noinput`, com
`django.core.exceptions.ImproperlyConfigured: Set the R2_ENDPOINT environment variable`.
O passo fornece apenas as variáveis anteriores às E16-02/03/04; as novas variáveis
obrigatórias de R2, Sentry e backup não estão no ambiente fictício de construção.
A imagem anterior registrada pelo implementador não demonstra o build de `52f8745`.
O mesmo Dockerfile impede o job do PR e a implantação da E16-08.

Retorno ao implementador: tornar a construção autossuficiente com configurações
fictícias limitadas ao passo necessário, sem segredos, serviços reais ou persistência
na imagem; provar o build do commit corrigido e as verificações de binários/usuário.
Não foi feita correção de produção pelo revisor.

Demais verificações: revisão de `/saude/`, tratamento do erro de banco, política
pública, HTTP interno, hosts/CSRF, TLS/conexão direta, WhiteNoise, processos e CI.
A-1 a A-14 têm cobertura local; isso não substitui o A-15 nem sana R01.
Os registros Red/Green descrevem comandos, falhas e guardas já existentes. Testes e
produção estão nos mesmos commits: o histórico sozinho não prova a ordem interna;
não encontrei contradição que autorize afirmar uma violação de TDD.

## Correção E16-R01 — construção autossuficiente (implementador, 2026-11-17)

- **Red observado** (`uv run pytest -q tests/ambiente/test_artefatos_de_implantacao.py`): A-16 falhou com 13 variáveis faltando no `RUN` do `collectstatic`; A-17 falhou com `ImproperlyConfigured: Set the R2_ENDPOINT environment variable` (o `.env` local foi neutralizado no subprocesso); A-19 falhou (sem `docker image inspect` no CI). A-18 passou na primeira (guarda: a conferência já foi escrita junto do apoio).
- **Green:** o `RUN` do `Dockerfile` ganhou `R2_*`, `R2_BACKUP_*`, `R2_BUCKET_BACKUPS`, `BACKUP_CHAVE_PUBLICA_AGE` e `SENTRY_DSN`, todos fictícios, na linha do comando (nunca em `ENV` ou `ARG`); todo host é `construcao.invalid` ou `localhost` (`construcao.invalido` passou a `.invalid`). `tests/ambiente/apoio.py` extrai as variáveis obrigatórias por `ast` (a mesma função serve ao A-1 da E16-08) e confere o `Dockerfile`. O CI ganhou o passo que recusa `SECRET_KEY`, `DATABASE_URL`, `SENTRY_DSN`, `R2_*` e `BACKUP_*` em `Config.Env`.
- **A-20, evidência no commit corrigido `281d191` (imagem `organicos-meier:e16-281d191`):** `docker build` saída 0; `pg_dump (PostgreSQL) 17.12`; `age 1.1.1`; `id -u` = 10001; `docker image inspect` saída 0, com 0 variáveis `SECRET_KEY|DATABASE_URL|SENTRY_DSN|R2_*|BACKUP_*` em `Config.Env`; `test_backup_externo_ferramentas.py` dentro dessa imagem (`EXIGIR_FERRAMENTAS_DE_BACKUP=1`): **1 passed**. Um build anterior (`7b96491`) também passou, mas não é a evidência.
- Ajuste: o A-13 da E16-03 conferia que `SENTRY_DSN` não aparece no texto do CI; o passo novo cita o nome para recusá-lo. O teste passou a conferir o `env` dos jobs e passos no YAML.
- Sem push, PR nem merge. Código corrigido no commit `281d191` (os commits seguintes só mudam documentos).


## Revalidação independente — 2026-11-18 — commit 5f12d21

**APROVADO no escopo local; R01 encerrado.** Especificação corrigida e A-16 a A-20 confrontados com Dockerfile, testes e CI. Build independente `docker build -q -t organicos-meier:revisor-e16-5f12d21 .`: saída 0, imagem `sha256:12115dc40d2d093aadc3526770ac95baf0ed6ef696aad66ffea85b2f46ad3484`. Conferidos `pg_dump` 17.12, `age` 1.1.1, UID 10001 e ausência de SECRET_KEY, DATABASE_URL, SENTRY_DSN, R2_* e BACKUP_* em Config.Env. Collectstatic recebeu ambiente fictício completo. A-15 do backup executado nesta imagem: 1 passed (7,42s), com ferramentas reais e PostgreSQL local. Isso não substitui a homologação E16-08. Registro Red/Green preservado e conferido; suíte e verificações globais em E16-08.
