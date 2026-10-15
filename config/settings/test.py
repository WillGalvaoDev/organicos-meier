import os

os.environ.setdefault("SECRET_KEY", "chave-apenas-para-testes")
os.environ.setdefault("DATABASE_URL", "postgres://organicos:organicos@localhost:5433/organicos")

from .base import *  # noqa: F403
from .base import INSTALLED_APPS as _APPS_BASE

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# App só de testes (modelos de apoio). Nunca em base.py nem em prod.py.
INSTALLED_APPS = [*_APPS_BASE, "tests.apoio"]
