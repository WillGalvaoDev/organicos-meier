from .base import *  # noqa: F403

DEBUG = True

# Em desenvolvimento o WhatsApp é o simulador (nunca a Meta).
CANAL_WHATSAPP = env("CANAL_WHATSAPP", default="simulado")  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "contato@organicosmeier.local"

# WebAuthn aceita origem sem HTTPS só fora de produção.
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = True
