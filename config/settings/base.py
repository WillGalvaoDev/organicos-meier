"""Configuração comum a todos os ambientes.

Apps de negócio e bibliotecas com comportamento (django-allauth, Procrastinate)
entram aqui só junto com a fatia que as usa, com testes escritos antes (AGENTS.md).
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS: list[str] = env.list("ALLOWED_HOSTS", default=[])
# Origem pública (esquema + domínio) para links em e-mails enviados fora de uma requisição.
ORIGEM_PUBLICA = env("ORIGEM_PUBLICA", default="http://localhost:8000")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.usersessions",
    "allauth.mfa",
    "apps.nucleo",
    "apps.fornecedores",
    "apps.contas",
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
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
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
