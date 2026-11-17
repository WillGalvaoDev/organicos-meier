# Homologação no Fly.io

Documento de operação do ambiente de homologação (E16-01 a E16-08). Nenhum valor secreto aparece aqui: as variáveis são só nomes, significado e origem.

> **Estado:** o ambiente ainda **não foi implantado**. A E16-08 (implantação e roteiro) depende das contas da fase 0 (Fly.io, Neon, Cloudflare R2, AWS SES, Sentry, Better Stack e cliente OAuth do Google). Este documento descreve a configuração que a implantação deve produzir; as verificações com evidência ficam no `docs/specs/E16-08/review.md`.

## Componentes

| Componente | Configuração | Onde está definido |
|---|---|---|
| App no Fly.io | `organicos-meier-homolog`, região primária `gru` (São Paulo) | `fly.toml` |
| Processo `web` | `gunicorn config.wsgi`, 2 workers, tempo-limite de 30 s, porta interna 8000, HTTPS forçado, verificação de saúde em `GET /saude/` a cada 30 s; pode desligar sem uso | `fly.toml` |
| Processo `worker` | `python manage.py procrastinate worker`, uma máquina sempre ligada (as tarefas periódicas só rodam com ele) | `fly.toml` |
| Máquinas | `shared-cpu-1x`, 512 MB, para os dois processos | `fly.toml` |
| Banco | branch do Neon em `aws-sa-east-1`, conexão direta (sem `-pooler`) e `sslmode=require` | `DATABASE_URL` |
| Bucket de arquivos | bucket privado do Cloudflare R2, credencial própria (avatares e comprovantes) | `R2_BUCKET_ARQUIVOS` |
| Bucket de backups | outro bucket privado do R2, credencial própria, com regra de ciclo de vida de 35 dias (configurada na implantação) | `R2_BUCKET_BACKUPS` |
| E-mail | AWS SES (`sa-east-1`) pela interface SMTP, em modo sandbox na fase 1; domínio e endereços verificados registrados na implantação | `EMAIL_*` |
| Observabilidade | projeto do Sentry (`SENTRY_DSN`) com os monitores de cron `verificar-operacao` e `backup-diario`; monitor de disponibilidade do Better Stack em `/saude/` | E16-03 |
| Pagamentos | simulador (`PROVEDOR_PAGAMENTOS=simulador`, `AMBIENTE=homologacao`), WhatsApp `desligado`; o simulador é recusado em produção | `fly.toml` |

A homologação usa o domínio `*.fly.dev`, com HTTPS do próprio Fly.io. Domínio próprio, Cloudflare na frente e limite de requisições nas rotas de login e convite ficam para a preparação da fase 2a.

## Variáveis e segredos

Os segredos são definidos com `fly secrets set NOME=valor`. Só as cinco variáveis não secretas do `[env]` estão no `fly.toml`: `DJANGO_SETTINGS_MODULE`, `AMBIENTE`, `PROVEDOR_PAGAMENTOS`, `CANAL_WHATSAPP` e `TZ`.

| Variável | Significado | Origem |
|---|---|---|
| `SECRET_KEY` | Chave secreta do Django (50 caracteres ou mais) | gerada pelo responsável |
| `DATABASE_URL` | URL de conexão direta do branch do Neon, com `sslmode=require` | console do Neon |
| `ALLOWED_HOSTS` | Domínios do app (sem `*`), separados por vírgula | domínio `*.fly.dev` do app |
| `ORIGEM_PUBLICA` | Origem pública (`https://...`) dos links dos e-mails; também a origem do CSRF | domínio do app |
| `EMAIL_BACKEND` | Backend de e-mail do Django (SMTP em homologação) | configuração |
| `DEFAULT_FROM_EMAIL` | Remetente dos e-mails | endereço verificado no SES |
| `EMAIL_HOST` | Servidor SMTP do SES | console do SES |
| `EMAIL_HOST_USER` | Usuário SMTP do SES | console do SES |
| `EMAIL_HOST_PASSWORD` | Senha SMTP do SES | console do SES |
| `EMAIL_PORT` | Porta SMTP (padrão 587) | opcional |
| `EMAIL_USE_TLS` | TLS no SMTP (padrão ligado) | opcional |
| `GOOGLE_CLIENT_ID` | Identificador do cliente OAuth do Google | console do Google |
| `GOOGLE_CLIENT_SECRET` | Segredo do cliente OAuth do Google | console do Google |
| `SEGREDO_AVISOS_SIMULADOR` | Segredo com que o simulador assina os avisos | gerado pelo responsável |
| `R2_ENDPOINT` | Endpoint S3 da conta do R2 (`https://<conta>.r2.cloudflarestorage.com`) | console do Cloudflare |
| `R2_BUCKET_ARQUIVOS` | Nome do bucket de arquivos enviados | console do Cloudflare |
| `R2_ACCESS_KEY_ID` | Chave de acesso do bucket de arquivos | token de API do R2 (só esse bucket) |
| `R2_SECRET_ACCESS_KEY` | Segredo do bucket de arquivos | token de API do R2 |
| `R2_BUCKET_BACKUPS` | Nome do bucket de backups | console do Cloudflare |
| `R2_BACKUP_ACCESS_KEY_ID` | Chave de acesso do bucket de backups | token de API do R2 (só esse bucket) |
| `R2_BACKUP_SECRET_ACCESS_KEY` | Segredo do bucket de backups | token de API do R2 |
| `BACKUP_CHAVE_PUBLICA_AGE` | Chave pública do `age` (começa com `age1`) | gerada com `age-keygen`; a privada fica com o responsável |
| `SENTRY_DSN` | DSN do projeto do Sentry | console do Sentry |
| `VERSAO_DA_APLICACAO` | Referência da versão para o Sentry (opcional) | opcional |

## Implantar e atualizar

1. Antes do primeiro deploy: crie o app (`fly apps create organicos-meier-homolog`) e defina todos os segredos acima com `fly secrets set`.
2. Implante a partir do commit da `main` que contém as E16-01 a E16-07: `fly deploy`. A imagem é construída pelo `Dockerfile`.
3. A migração roda como `release_command` (`python manage.py migrate --noinput`) antes de cada versão nova subir. Se a migração falhar, a troca de versão não acontece.
4. Para voltar à versão anterior: `fly releases` lista as versões e as imagens; `fly deploy --image <imagem anterior>` volta a ela. Uma migração já aplicada não é desfeita sozinha: avalie antes de voltar.
5. Escala: `fly scale count web=1 worker=1`. O worker nunca fica em zero fora de uma restauração (`docs/operacao/restauracao.md`).

## Monitoramento

- **Disponibilidade:** o monitor do Better Stack consulta `GET https://<app>.fly.dev/saude/` a cada 3 minutos e avisa por e-mail quando a resposta não é 200.
- **Tarefas periódicas:** os monitores de cron do Sentry `verificar-operacao` (a cada 5 minutos, margem de 10) e `backup-diario` (às 06:00 UTC, margem de 120 minutos) avisam quando o check-in não chega, mesmo com o worker inteiro parado.
- **Alertas internos:** o painel do administrador (`administracao/`) e os alertas operacionais da E15 cobrem as demais tarefas.
- **Para quem vai cada aviso:** o e-mail do responsável pelo projeto, configurado nas regras do Better Stack e do Sentry.

## Credenciais e menor privilégio

- A credencial do bucket de arquivos **não** lê o de backups, e a credencial de backups **não** lê o de arquivos: cada token de API do R2 é restrito a um bucket.
- A aplicação só conhece a **chave pública** do `age`. A chave privada não fica no Fly.io: é guardada pelo responsável (`docs/operacao/restauracao.md`, seção "Guarda da chave privada").
- Nenhum segredo fica na imagem, no `fly.toml` ou no repositório. O Sentry recebe os eventos sem dados pessoais (E16-03).

## Custos observados

A estimativa da infraestrutura 10 é de US$ 8–15 por mês (Fly.io com duas máquinas pequenas, Neon, R2, SES, Sentry e Better Stack em planos de entrada).

| Serviço | Custo mensal observado | Comparação com a infraestrutura 10 |
|---|---|---|
| Fly.io (web e worker) | a medir depois da implantação | — |
| Neon | a medir depois da implantação | — |
| Cloudflare R2 | a medir depois da implantação | — |
| AWS SES | a medir depois da implantação | — |
| Sentry | a medir depois da implantação | — |
| Better Stack | a medir depois da implantação | — |
