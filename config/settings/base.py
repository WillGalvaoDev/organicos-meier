"""Configuração comum a todos os ambientes.

Apps de negócio e bibliotecas com comportamento (django-allauth, Procrastinate)
entram aqui só junto com a fatia que as usa, com testes escritos antes (AGENTS.md).
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS: list[str] = env.list("ALLOWED_HOSTS", default=[])
# Origem pública (esquema + domínio) para links em e-mails enviados fora de uma requisição.
# O servidor de e-mail parado não pode segurar a trava de um envio indefinidamente (E04-03).
EMAIL_TIMEOUT = 10

# As tarefas do Procrastinate ficam em `tarefas.py` de cada app (E04-03).
PROCRASTINATE_AUTODISCOVER_MODULE_NAME = "tarefas"

# Canal de WhatsApp (E04-04). Na fase 1 só existem `desligado` e `simulado`; o canal real é da
# fase 3. Qualquer outro valor impede o carregamento, em qualquer ambiente.
CANAL_WHATSAPP = env("CANAL_WHATSAPP", default="desligado")
if CANAL_WHATSAPP not in ("desligado", "simulado"):
    raise ImproperlyConfigured("CANAL_WHATSAPP deve ser 'desligado' ou 'simulado'.")

ORIGEM_PUBLICA = env("ORIGEM_PUBLICA", default="http://localhost:8000")

INSTALLED_APPS = [
    "procrastinate.contrib.django",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",  # exigido pelos templates de passkeys do allauth
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.usersessions",
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "apps.nucleo",
    "apps.fornecedores",
    "apps.contas",
    "apps.rodadas",
    "apps.catalogo",
    "apps.interesses",
    "apps.notificacoes",
]

AUTH_USER_MODEL = "contas.Conta"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "allauth.usersessions.middleware.UserSessionsMiddleware",
    "apps.contas.middleware.RecusaContaSemAcesso",
    "apps.contas.middleware.ProtegeRotasDeMfa",
    "apps.contas.middleware.ExigePasskeyDoAdministrador",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.contas.contexto.google_habilitado",
                "apps.notificacoes.contexto.notificacoes_nao_lidas",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Avatares (E02-09). Em produção o storage do R2 entra com a homologação (E16).
MEDIA_ROOT = BASE_DIR / "media"

# --- Autenticação (E02-02) ---
AUTHENTICATION_BACKENDS = ["allauth.account.auth_backends.AuthenticationBackend"]
LOGIN_URL = "/entrar/"
LOGIN_REDIRECT_URL = "/inicio/"

ACCOUNT_LOGIN_METHODS = {"email"}
# `password1` precisa constar para o formulário de login manter o campo de senha.
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = "email_normalizado"
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_BY_CODE_ENABLED = False  # o link de acesso é próprio (E02-06)
ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False  # recuperação não envia e-mail a quem não tem conta
ACCOUNT_LOGOUT_REDIRECT_URL = "/entrar/"
ACCOUNT_ADAPTER = "apps.contas.adaptadores.AdaptadorConta"
ACCOUNT_FORMS = {
    "reset_password": "apps.contas.formularios.FormularioRecuperacao",
    "reset_password_from_key": "apps.contas.formularios.FormularioNovaSenha",
}

AUTH_PASSWORD_VALIDATORS = [
    {
        # `Conta` não tem username, first_name, last_name nem email (os atributos padrão do
        # Django, ignorados em silêncio): a semelhança é conferida com os campos reais.
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("nome", "email_normalizado")},
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- MFA do administrador: só passkeys (E02-03) ---
MFA_SUPPORTED_TYPES = ["webauthn"]
MFA_PASSKEY_LOGIN_ENABLED = True
MFA_ADAPTER = "apps.contas.adaptadores.AdaptadorMFA"
ACCOUNT_REAUTHENTICATION_TIMEOUT = 300

# --- Login com Google (E02-07) ---
SITE_ID = 1  # exigido pelo modelo SocialApp do allauth; não é usado para montar links
SOCIALACCOUNT_ADAPTER = "apps.contas.adaptadores.AdaptadorContaSocial"
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"  # o e-mail verificado do Google é exigido no adaptador
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False  # a associação por e-mail é feita pelo adaptador
SOCIALACCOUNT_STORE_TOKENS = False
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": (
            [{"client_id": GOOGLE_CLIENT_ID, "secret": GOOGLE_CLIENT_SECRET, "key": ""}]
            if GOOGLE_CLIENT_ID
            else []
        ),
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}
