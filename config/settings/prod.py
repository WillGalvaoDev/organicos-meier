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
