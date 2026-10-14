import os

os.environ.setdefault("SECRET_KEY", "chave-apenas-para-testes")
os.environ.setdefault("DATABASE_URL", "postgres://organicos:organicos@localhost:5433/organicos")

from .base import *  # noqa: F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
