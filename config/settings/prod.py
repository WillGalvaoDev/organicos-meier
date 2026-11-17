"""Produção (Fly.io + Neon). Ainda não usado: a fase 1 roda só em desenvolvimento e homologação.

`AMBIENTE` (`homologacao` ou `producao`) é obrigatório. Na fase 1 o único provedor de pagamentos
é o simulador, então `producao` nunca carrega: a aplicação não inicia em produção com o simulador
(A3, cenário 38, T-12; E07-02). A homologação usa estas configurações com dados de teste.
"""

from django.core.exceptions import ImproperlyConfigured

from config.armazenamento import storage_do_r2
from config.observabilidade import iniciar_sentry

from .base import *  # noqa: F403

DEBUG = False
# A verificação de saúde interna do Fly.io é feita por HTTP, sem `X-Forwarded-Proto` (E16-01).
SECURE_REDIRECT_EXEMPT = [r"^saude/$"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Hosts e origens (E16-01): obrigatórios e explícitos. Lista vazia ou com `*` é recusada.
ALLOWED_HOSTS = [h.strip() for h in env.list("ALLOWED_HOSTS") if h.strip()]  # noqa: F405
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS deve listar os domínios do ambiente.")

# Obrigatórios, sem valor padrão: se faltarem, o carregamento falha.
# O envio real (SES) é configurado na E04 e na homologação.
EMAIL_BACKEND = env("EMAIL_BACKEND")  # noqa: F405
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")  # noqa: F405
# SMTP (por exemplo, a interface SMTP do SES). Os segredos vêm do ambiente (`fly secrets`); com
# usuário e senha vazios o envio falha e entra no fluxo de tentativas (E04-03).
EMAIL_HOST = env("EMAIL_HOST", default="localhost")  # noqa: F405
EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa: F405
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # noqa: F405
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")  # noqa: F405
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # noqa: F405
# Origem pública dos links enviados por e-mail (convites); sem padrão em produção.
ORIGEM_PUBLICA = env("ORIGEM_PUBLICA")  # noqa: F405
CSRF_TRUSTED_ORIGINS = [ORIGEM_PUBLICA]
# Credenciais do login com Google, obrigatórias em produção.
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID")  # noqa: F405
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET")  # noqa: F405

# Ambiente e provedor de pagamentos (E07-02). A recusa vale para web, worker e comandos, porque
# todos carregam estas configurações. As mensagens não trazem segredos.
AMBIENTE = env("AMBIENTE", default="")  # noqa: F405
if AMBIENTE not in ("homologacao", "producao"):
    raise ImproperlyConfigured("AMBIENTE deve ser 'homologacao' ou 'producao'.")
if AMBIENTE == "producao" and PROVEDOR_PAGAMENTOS == "simulador":  # noqa: F405
    raise ImproperlyConfigured("O simulador de pagamentos não pode ser usado em produção.")
if PROVEDOR_PAGAMENTOS == "simulador":  # noqa: F405
    SEGREDO_AVISOS_SIMULADOR = env("SEGREDO_AVISOS_SIMULADOR")  # noqa: F405

# Mensagens simuladas em produção dariam a falsa impressão de que o aviso saiu (A3, cenário 38).
if CANAL_WHATSAPP == "simulado":  # noqa: F405
    raise ImproperlyConfigured("CANAL_WHATSAPP=simulado não é permitido em produção.")

# Banco (E16-01): TLS obrigatório e conexão direta do Neon. O pool (`-pooler`, PgBouncer em modo
# transação) quebra `LISTEN/NOTIFY` e as travas de sessão do Procrastinate. As mensagens não trazem
# a URL nem a senha. A conexão do simulador (E07-R03) mantém os padrões da base.
_banco = DATABASES["default"]  # noqa: F405
if _banco.get("OPTIONS", {}).get("sslmode") not in ("require", "verify-full"):
    raise ImproperlyConfigured("DATABASE_URL deve exigir TLS (sslmode=require).")
if "-pooler" in str(_banco.get("HOST", "")):
    raise ImproperlyConfigured("DATABASE_URL deve usar a conexão direta do Neon, sem -pooler.")
_banco["CONN_MAX_AGE"] = 60
_banco["CONN_HEALTH_CHECKS"] = True

# Estáticos pela própria aplicação (E16-01): o WhiteNoise logo depois do `SecurityMiddleware`.
MIDDLEWARE = [
    MIDDLEWARE[0],  # noqa: F405
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],  # noqa: F405
]
# Arquivos enviados no bucket privado do R2 (E16-02). As quatro variáveis são obrigatórias.
STORAGES = {
    "default": storage_do_r2(
        env("R2_ENDPOINT"),  # noqa: F405
        env("R2_BUCKET_ARQUIVOS"),  # noqa: F405
        env("R2_ACCESS_KEY_ID"),  # noqa: F405
        env("R2_SECRET_ACCESS_KEY"),  # noqa: F405
    ),
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Verificações de implantação silenciadas, cada uma com o motivo (E16-01, regra 11).
SILENCED_SYSTEM_CHECKS = [
    # HSTS preload é um compromisso permanente com a lista dos navegadores; o domínio `*.fly.dev`
    # da homologação não pode entrar nela. A decisão volta com o domínio próprio (fase 2a).
    "security.W021",
]

# Sentry sem dados pessoais (E16-03): o DSN é obrigatório em homologação e produção. O filtro está
# em `config/observabilidade.py`.
SENTRY_DSN = env("SENTRY_DSN")  # noqa: F405
iniciar_sentry(SENTRY_DSN, AMBIENTE)
