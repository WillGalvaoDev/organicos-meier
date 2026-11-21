from config.observabilidade import iniciar_sentry

from .base import *  # noqa: F403

DEBUG = True
AMBIENTE = "desenvolvimento"

# Em desenvolvimento o WhatsApp é o simulador (nunca a Meta).
CANAL_WHATSAPP = env("CANAL_WHATSAPP", default="simulado")  # noqa: F405

# Segredo dos avisos do simulador de pagamentos, só para desenvolvimento.
SEGREDO_AVISOS_SIMULADOR = env("SEGREDO_AVISOS_SIMULADOR", default="segredo-do-simulador-dev")  # noqa: F405

# O Sentry só é iniciado em desenvolvimento se o DSN estiver definido (E16-03).
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    iniciar_sentry(SENTRY_DSN, AMBIENTE)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "contato@organicosmeier.local"

# WebAuthn aceita origem sem HTTPS só fora de produção.
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = True
