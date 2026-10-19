"""Produção (Fly.io + Neon). Ainda não usado: a fase 1 roda só em desenvolvimento e homologação.

`AMBIENTE` (`homologacao` ou `producao`) é obrigatório. Na fase 1 o único provedor de pagamentos
é o simulador, então `producao` nunca carrega: a aplicação não inicia em produção com o simulador
(A3, cenário 38, T-12; E07-02). A homologação usa estas configurações com dados de teste.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

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
