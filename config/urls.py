from allauth.account import views as allauth_views
from allauth.socialaccount.providers.google.provider import GoogleProvider
from allauth.socialaccount.providers.oauth2.urls import default_urlpatterns
from django.urls import URLPattern, URLResolver, include, path, re_path

from apps.catalogo import views as catalogo_views
from apps.contas import views as contas_views
from apps.fornecedores import views as fornecedores_views
from apps.rodadas import views as rodadas_views

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
    path(
        "convite/<str:token>/google/",
        contas_views.cadastrar_com_google,
        name="cadastrar_com_google",
    ),
    path(
        "entrar/google/concluir/",
        contas_views.concluir_cadastro_google,
        name="socialaccount_signup",
    ),
    path("entrar/google/recusado/", contas_views.google_recusado, name="socialaccount_login_error"),
    path(
        "entrar/google/cancelado/",
        contas_views.google_recusado,
        name="socialaccount_login_cancelled",
    ),
    path("entrar/", include(default_urlpatterns(GoogleProvider))),
    path("inicio/", contas_views.inicio, name="inicio"),
    path("perfil/", contas_views.perfil, name="perfil"),
    path("perfil/avatar/<int:pk>/", contas_views.avatar, name="avatar"),
    path("administracao/", contas_views.painel_administracao, name="painel_administracao"),
    path(
        "administracao/usuarios/",
        contas_views.usuarios_administracao,
        name="usuarios_administracao",
    ),
    path(
        "administracao/usuarios/<int:pk>/remover/",
        contas_views.confirmar_remocao,
        name="confirmar_remocao",
    ),
    path(
        "administracao/usuarios/<int:pk>/<str:acao>/",
        contas_views.acao_de_moderacao,
        name="acao_de_moderacao",
    ),
    path("administracao/fornecedores/", fornecedores_views.lista, name="fornecedores_lista"),
    path("administracao/fornecedores/novo/", fornecedores_views.novo, name="fornecedores_novo"),
    path(
        "administracao/fornecedores/<int:pk>/",
        fornecedores_views.detalhe,
        name="fornecedores_detalhe",
    ),
    path(
        "administracao/fornecedores/<int:pk>/editar/",
        fornecedores_views.editar,
        name="fornecedores_editar",
    ),
    path(
        "administracao/fornecedores/<int:pk>/minimo/",
        fornecedores_views.minimo,
        name="fornecedores_minimo",
    ),
    path(
        "administracao/fornecedores/<int:pk>/rodadas/abrir/",
        rodadas_views.abrir,
        name="rodadas_abrir",
    ),
    path(
        "administracao/fornecedores/<int:pk>/produtos/novo/",
        catalogo_views.novo,
        name="produtos_novo",
    ),
    path("administracao/produtos/<int:pk>/", catalogo_views.detalhe, name="produtos_detalhe"),
    path(
        "administracao/produtos/<int:pk>/multiplo/",
        catalogo_views.multiplo,
        name="produtos_multiplo",
    ),
    path("administracao/rodadas/<int:pk>/estoque/", rodadas_views.estoque, name="rodadas_estoque"),
    path(
        "administracao/rodadas/<int:pk>/estoque/incluir/",
        rodadas_views.estoque_incluir,
        name="rodadas_estoque_incluir",
    ),
    path(
        "administracao/estoque/<int:pk>/alterar/",
        rodadas_views.estoque_alterar,
        name="estoque_alterar",
    ),
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
