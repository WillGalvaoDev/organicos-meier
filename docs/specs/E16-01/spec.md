# E16-01 — Imagem, processos e configuração da homologação

Fatia 1 de 8 da milestone **E16 — Homologação e encerramento da fase 1**. Agente 1 (especificador).

## Versões dos documentos-base

Especificação funcional v1.7 e infraestrutura v1.8 (29/10/2026). O texto da milestone 16 cita a base v1.6/v1.7. As seções usadas na E16 não mudaram entre essas versões:
- especificação §13 e §15;
- infraestrutura 2, 5, 6, 7 e 8.

O gate de especificação é feito pelo especificador, por decisão do responsável.

## Divisão da E16

| Fatia | Objetivo |
|---|---|
| E16-01 | Imagem de contêiner, processos web e worker, configuração de homologação no Fly.io com Neon e verificação de saúde |
| E16-02 | Arquivos enviados (avatares e comprovantes) num bucket privado do Cloudflare R2 |
| E16-03 | Observabilidade: Sentry sem dados pessoais e monitor externo das tarefas, independente do worker (herdado da E15) |
| E16-04 | Backup externo diário do banco, cifrado, no R2 |
| E16-05 | Restauração: conferência depois de restaurar e procedimento com teste cronometrado |
| E16-06 | Página de regras completa para o comprador (§13; herdado da E14) |
| E16-07 | Rastreabilidade dos cenários 1 a 119 e dos testes T-1 a T-55, com verificação automática |
| E16-08 | Homologação executada e relatório final de encerramento da fase 1 |

Ordem de implementação:
1. **Começam em qualquer ordem:** E16-01, E16-06 e E16-07.
2. **Depois da E16-01:** E16-02, E16-03 e E16-04.
3. **Depois da E16-04:** E16-05.
4. **Por último:** E16-08, que depende de todas as outras e das contas da fase 0 (ver "Dependências").

## Contexto e objetivo

A fase 1 termina com a homologação (infraestrutura 7). O repositório ainda não tem imagem de contêiner, configuração do Fly.io, servidor de aplicação nem arquivos estáticos servidos fora do `runserver`. O `prod.py` (E07-02) já existe, com HTTPS, cookies seguros, `AMBIENTE` obrigatório e a recusa do simulador em produção. Esta fatia torna a aplicação implantável no Fly.io (região `gru`), com o banco num branch do Neon (São Paulo), em dois processos: web e worker.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 2 | Django num único deploy; Neon Postgres em `aws-sa-east-1`; Fly.io `gru` com uma instância web e uma worker; segredos via `fly secrets`; homologação num app separado. |
| Infraestrutura 5 | Ambientes separados com credenciais próprias; o simulador nunca é ativado em produção; segredos só em variáveis do provedor; nenhum dado pessoal em logs. |
| Infraestrutura 7 | Fase 1: desenvolvimento e homologação, sem operação em produção. |
| Especificação §15, Operação | Ambientes separados; a primeira fase usa apenas o simulador. |
| E07-02 | `AMBIENTE` obrigatório em `prod.py`; simulador recusado em produção (T-12); `SEGREDO_AVISOS_SIMULADOR` obrigatório com o simulador. |
| E04-04 | `prod.py` recusa `CANAL_WHATSAPP=simulado` em qualquer `AMBIENTE`. |
| Milestone 16, herdado da E07 | A homologação usa `prod.py` com `AMBIENTE=homologacao`, `PROVEDOR_PAGAMENTOS=simulador` e `SEGREDO_AVISOS_SIMULADOR`, com o WhatsApp `desligado`. |

## Escopo

**Dentro:**
- `Dockerfile` e `.dockerignore`;
- `fly.toml` do app de homologação;
- servidor de aplicação para o processo web;
- arquivos estáticos servidos pela própria aplicação;
- a rota `/saude/`;
- os ajustes de `prod.py` para o Fly.io e o Neon;
- um passo de CI que constrói a imagem.

**Fora:**
- arquivos enviados (E16-02), Sentry (E16-03) e backup (E16-04);
- a criação das contas e a implantação de fato (E16-08);
- um app de produção: a fase 1 não opera em produção (infraestrutura 7);
- Cloudflare na frente da homologação (ver "Decisões técnicas").

## Regras

### Imagem

1. **`Dockerfile`** com Python 3.12 (a versão do `pyproject.toml`), dependências instaladas pelo `uv sync --locked --no-dev` e a aplicação copiada.
   - A imagem roda como usuário sem privilégios (não `root`).
   - Contém o cliente `pg_dump`/`pg_restore` da versão 17, a mesma família do banco (compose e Neon), e o binário `age`, usados pela E16-04.
   - Não contém `.env`, `.venv`, `media/`, `.git` nem segredos. O `.dockerignore` exclui esses caminhos.
2. **Arquivos estáticos:** o `collectstatic` roda na construção da imagem. A construção não pode depender de segredo real: quando o comando exige variáveis, recebe valores fictícios só naquele passo, e eles não ficam na imagem final como variáveis de ambiente.
3. **Processos** (os dois usam `config.settings.prod`):
   - **web:** `gunicorn config.wsgi`, escutando em `0.0.0.0:8000`, com 2 workers e tempo-limite de 30 s;
   - **worker:** `python manage.py procrastinate worker`.
4. **Migrações:** `python manage.py migrate --noinput` como `release_command` do Fly.io, antes de cada nova versão subir. Uma migração que falha impede a troca de versão.

### `fly.toml` (homologação)

5. App de homologação na região primária `gru`.
   - **web:** `http_service` na porta interna 8000, HTTPS forçado, verificação de saúde em `GET /saude/` a cada 30 s com tempo-limite de 5 s.
   - **worker:** sem serviço HTTP, uma máquina sempre ligada (ver "Decisões técnicas").
   - Variáveis não secretas no `[env]`: `DJANGO_SETTINGS_MODULE=config.settings.prod`, `AMBIENTE=homologacao`, `PROVEDOR_PAGAMENTOS=simulador`, `CANAL_WHATSAPP=desligado`, `TZ=UTC`.
   - Os segredos ficam fora do arquivo e são definidos por `fly secrets`. A lista é a da regra 9.

### Rota `/saude/`

6. `GET /saude/`, sem autenticação e sem sessão:
   - executa `SELECT 1` na conexão `default`;
   - em sucesso, responde **200** com o corpo `ok` (`text/plain`);
   - se a consulta falhar, responde **503** com o corpo `indisponivel`, sem detalhe do erro, e registra no log só a classe do erro.

   A rota não grava nada, não cria sessão nem cookie e não registra auditoria. Ela fica fora do redirecionamento HTTPS (`SECURE_REDIRECT_EXEMPT`), porque a verificação interna do Fly.io é feita por HTTP. Qualquer outro método responde 405.

### `prod.py`

7. **Hosts e origens:**
   - `ALLOWED_HOSTS` obrigatório em `prod.py`, sem padrão;
   - lista vazia ou com `*` é recusada com `ImproperlyConfigured("ALLOWED_HOSTS deve listar os domínios do ambiente.")`;
   - `CSRF_TRUSTED_ORIGINS` é derivado de `ORIGEM_PUBLICA`, que já é obrigatória.
8. **Banco:**
   - `DATABASE_URL` obrigatório;
   - `CONN_MAX_AGE = 60` e `CONN_HEALTH_CHECKS = True`;
   - em homologação e produção, a URL precisa ter `sslmode=require` (ou `verify-full`). Sem isso: `ImproperlyConfigured("DATABASE_URL deve exigir TLS (sslmode=require).")`;
   - a URL não pode usar o endpoint com pool do Neon (`-pooler` no host), porque o Procrastinate usa `LISTEN/NOTIFY` e travas de sessão. Com o pool: `ImproperlyConfigured("DATABASE_URL deve usar a conexão direta do Neon, sem -pooler.")`.

   Nenhuma mensagem de erro de configuração contém segredo, URL ou senha.
9. **Segredos esperados em homologação** (todos já obrigatórios em `prod.py` ou acrescentados pelas E16-02 a E16-04): `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, `ORIGEM_PUBLICA`, `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` e `SEGREDO_AVISOS_SIMULADOR`.

   A lista completa, com as variáveis das fatias seguintes, fica em `docs/operacao/homologacao.md`, que a E16-08 cria.
10. **Estáticos:** em `prod.py`, `STORAGES["staticfiles"]` usa o armazenamento comprimido com manifesto do WhiteNoise, com o middleware logo depois do `SecurityMiddleware`. Desenvolvimento e testes continuam como hoje.
11. **Verificações de implantação:** `manage.py check --deploy --fail-level WARNING`, com `config.settings.prod` e um ambiente fictício completo, passa sem aviso. Um aviso que não se aplique (por exemplo, por causa do proxy do Fly.io) só pode ser silenciado em `SILENCED_SYSTEM_CHECKS` com um comentário que diga o motivo.

### CI

12. O workflow de CI ganha um job que constrói a imagem (`docker build`) sem publicá-la. A construção quebrada falha o PR. O job `verificacoes` não muda nesta fatia. A E16-04 acrescenta a ele a instalação do `pg_dump` 17 e do `age`.

### Correção E16-R01 — construção autossuficiente (revisão de 2026-11-17)

O `docker build` do commit `52f8745` falha no `collectstatic` com `Set the R2_ENDPOINT environment variable`. O passo de construção só recebeu as variáveis anteriores às E16-02, E16-03 e E16-04. As regras 13 a 15 completam a regra 2, sem mudar o que ela pede.

13. **Ambiente de construção completo:** o `RUN` do `collectstatic` recebe um valor fictício para **cada** variável que `config/settings/base.py` e `config/settings/prod.py` leem sem padrão. Isso inclui as da E16-02 (`R2_ENDPOINT`, `R2_BUCKET_ARQUIVOS`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`), da E16-03 (`SENTRY_DSN`) e da E16-04 (`R2_BUCKET_BACKUPS`, `R2_BACKUP_ACCESS_KEY_ID`, `R2_BACKUP_SECRET_ACCESS_KEY`, `BACKUP_CHAVE_PUBLICA_AGE`).
    - **Nomes não resolvíveis:** todo host e toda URL fictícios usam o domínio reservado `construcao.invalid` (RFC 2606) ou `localhost`. Isso vale também para os valores que já existem (`construcao.invalido` passa a `construcao.invalid`).
    - **Valores que passam nas validações de `prod.py`:**
      - `SENTRY_DSN=https://ficticio@construcao.invalid/0`;
      - `BACKUP_CHAVE_PUBLICA_AGE` começando com `age1`, sem ser uma chave real (por exemplo, `age1ficticiasoparaconstrucao`).
    - **Escopo:** os valores ficam só naquele `RUN`, na própria linha do comando. Nunca entram em `ENV` nem em `ARG` e não aparecem na configuração da imagem final (`docker image inspect`, campo `Config.Env`).
    - **Sem acesso externo:** a construção não conecta ao banco, ao R2 nem ao Sentry. O `collectstatic` não abre conexão com o banco, e o Sentry inicializado com o DSN fictício não envia nada sem evento.
14. **Lista das variáveis obrigatórias:** uma função de teste lê a árvore de sintaxe de `base.py` e `prod.py` e devolve os nomes literais das chamadas `env("NOME")` e `env.<método>("NOME")` que não têm `default`.
    - Ela entra as condicionais, como `SEGREDO_AVISOS_SIMULADOR`, porque a homologação usa o simulador.
    - A mesma função serve à E16-08 A-1 ("conferido contra a lista extraída do código") e fica num módulo de apoio de `tests/ambiente/`.
15. **Guarda local:** um teste extrai do `Dockerfile` as variáveis definidas no `RUN` do `collectstatic`. Ele confere que:
    - nenhuma variável da lista da regra 14 falta;
    - os hosts e as URLs seguem a regra 13;
    - nenhuma delas aparece em `ENV` ou `ARG`.

    Depois, carrega `config.settings.prod` em subprocesso só com esse ambiente (mais `PATH`) e executa `python manage.py collectstatic --noinput --dry-run`, que precisa sair com código 0. É a prova sem Docker de que o passo de construção carrega as configurações atuais.
16. **CI e evidência no commit corrigido:**
    - o job `imagem` (regra 12) ganha um passo: `docker image inspect` da imagem construída, cujo `Config.Env` não contém `SECRET_KEY`, `DATABASE_URL`, `SENTRY_DSN` nem nenhuma variável que comece com `R2_` ou `BACKUP_`;
    - o `review.md` registra, para o hash do commit corrigido:
      - o `docker build` com saída 0;
      - as três verificações do A-15;
      - o `docker image inspect`;
      - a execução do E16-04 A-15 dentro dessa imagem.

      A imagem de um commit anterior não vale como evidência.

## Decisões técnicas

- **Gunicorn e WhiteNoise.** O Django não serve estáticos nem é servidor de produção. O Gunicorn é o servidor WSGI padrão, e o WhiteNoise serve os estáticos sem um proxy ou CDN a mais, o que cabe num único deploy (infraestrutura 2). Duas dependências novas, com necessidade demonstrada.
- **Worker sempre ligado e web ligada durante a homologação.** A infraestrutura 10 estima "homologação desligando sozinha". Na homologação, porém, é preciso demonstrar as tarefas periódicas (prazos, conciliação, verificação operacional e backup diário), e elas só rodam com o worker ligado. Por isso:
  - o worker fica com uma máquina sempre ligada;
  - a web pode desligar sem uso (`auto_stop_machines`), mas o monitor de disponibilidade da E16-03 a mantém acordada.

  Duas máquinas pequenas ficam dentro da faixa estimada para o Fly.io (US$ 8–15 por mês). O total fixo estimado, com Neon, SES, R2, Sentry e Better Stack, é de US$ 15–35 por mês (infraestrutura 10). Depois do relatório final, o responsável pode desligar a homologação até a fase 2a.
- **Conexão direta do Neon.** O pool do Neon (PgBouncer em modo transação) quebra `LISTEN/NOTIFY` e as travas de sessão do Procrastinate. Com 2 workers do Gunicorn e um worker, o número de conexões diretas é pequeno.
- **Sem Cloudflare na homologação.** A homologação usa o domínio `*.fly.dev`, com HTTPS do próprio Fly.io. O DNS próprio, a proteção e o limite de requisições nas rotas de login e convite (infraestrutura 2) ficam para a preparação da fase 2a. Isso é registrado no relatório final (E16-08).
- **WhatsApp `desligado`.** É o herdado da E07: o `prod.py` recusa `simulado` em qualquer ambiente (E04-04), e a fase 3 é que liga o canal.

## Invariantes

- A aplicação não inicia em produção com o simulador (T-12): as regras de `prod.py` da E07-02 não mudam.
- Nenhum segredo fica na imagem, no `fly.toml`, no repositório ou em mensagens de erro.
- `/saude/` não expõe dado, versão nem detalhe de erro.

## Dependências e decisões em aberto

- Depende da E07-02 (`prod.py`).
- Novas dependências de produção: `gunicorn` e `whitenoise`.
- Nenhuma decisão em aberto.
