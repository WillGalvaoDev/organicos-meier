"""Produção (Fly.io + Neon). Ainda não usado: a fase 1 roda só em desenvolvimento e homologação.

A recusa de iniciar com o simulador de pagamentos (A3, cenário 38, T-12) entra
como comportamento testado, em fatia própria, e não como configuração solta.
"""

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
# Origem pública dos links enviados por e-mail (convites); sem padrão em produção.
ORIGEM_PUBLICA = env("ORIGEM_PUBLICA")  # noqa: F405
# Credenciais do login com Google, obrigatórias em produção.
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID")  # noqa: F405
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET")  # noqa: F405
