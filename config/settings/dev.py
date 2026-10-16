from .base import *  # noqa: F403

DEBUG = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "contato@organicosmeier.local"

# WebAuthn aceita origem sem HTTPS só fora de produção.
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = True
