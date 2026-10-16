from allauth.account import views as allauth_views
from django.urls import URLPattern, URLResolver, path, re_path

from apps.contas import views as contas_views

# Cada rota entra com a fatia que a especifica e testa. Só as rotas do allauth usadas aqui
# existem; cadastro e as demais ficam de fora. Os nomes são os que o allauth usa internamente.
urlpatterns: list[URLPattern | URLResolver] = [
    path("entrar/", allauth_views.login, name="account_login"),
    path("sair/", allauth_views.logout, name="account_logout"),
    path("recuperar-acesso/", allauth_views.password_reset, name="account_reset_password"),
    path(
        "recuperar-acesso/enviado/",
        allauth_views.password_reset_done,
        name="account_reset_password_done",
    ),
    re_path(
        r"^recuperar-acesso/chave/(?P<uidb36>[0-9A-Za-z]+)-(?P<key>.+)/$",
        allauth_views.password_reset_from_key,
        name="account_reset_password_from_key",
    ),
    path(
        "recuperar-acesso/concluido/",
        allauth_views.password_reset_from_key_done,
        name="account_reset_password_from_key_done",
    ),
    path("inicio/", contas_views.inicio, name="inicio"),
]
