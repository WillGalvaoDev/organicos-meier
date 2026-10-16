from allauth.account import views as allauth_views
from django.urls import URLPattern, URLResolver, include, path, re_path

from apps.contas import views as contas_views

# Cada rota entra com a fatia que a especifica e testa. Só as rotas do allauth usadas aqui
# existem; cadastro e as demais ficam de fora. Os nomes são os que o allauth usa internamente.
urlpatterns: list[URLPattern | URLResolver] = [
    path("entrar/", allauth_views.login, name="account_login"),
    path("entrar/link/", contas_views.pedir_link_de_acesso, name="pedir_link_de_acesso"),
    path(
        "entrar/link/<str:token>/",
        contas_views.usar_link_de_acesso,
        name="usar_link_de_acesso",
    ),
    path("sair/", allauth_views.logout, name="account_logout"),
    path("reautenticar/", allauth_views.reauthenticate, name="account_reauthenticate"),
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
    path("convite/<str:token>/", contas_views.aceitar_convite, name="aceitar_convite"),
    path("inicio/", contas_views.inicio, name="inicio"),
    path("administracao/", contas_views.painel_administracao, name="painel_administracao"),
    path(
        "administracao/convites/",
        contas_views.convites_administracao,
        name="convites_administracao",
    ),
    path(
        "seguranca/webauthn/keys/<int:pk>/remove/",
        contas_views.remover_passkey,
        name="mfa_remove_webauthn",
    ),
    path("seguranca/", include("allauth.mfa.urls")),
]
