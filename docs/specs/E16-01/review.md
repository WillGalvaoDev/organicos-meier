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
