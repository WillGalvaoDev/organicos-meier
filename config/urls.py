from allauth.account import views as allauth_views
from allauth.socialaccount.providers.google.provider import GoogleProvider
from allauth.socialaccount.providers.oauth2.urls import default_urlpatterns
from django.urls import URLPattern, URLResolver, include, path, re_path

from apps.catalogo import views as catalogo_views
from apps.contas import views as contas_views
from apps.fornecedores import views as fornecedores_views
from apps.interesses import views as interesses_views
from apps.notificacoes import views as notificacoes_views
from apps.pagamentos import views as pagamentos_views
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
    path("catalogo/", catalogo_views.catalogo, name="catalogo_lista"),
    path(
        "catalogo/<int:pk>/",
        catalogo_views.catalogo_do_fornecedor,
        name="catalogo_fornecedor",
    ),
    path("carrinho/", interesses_views.carrinho, name="carrinho"),
    path("interesses/", interesses_views.definir, name="interesses_definir"),
    path(
        "interesses/pendentes/remover/",
        interesses_views.remover_pendentes,
        name="interesses_remover_pendentes",
    ),
    path("notificacoes/", notificacoes_views.central, name="notificacoes"),
    path("notificacoes/lidas/", notificacoes_views.marcar_todas, name="notificacoes_marcar_todas"),
    path(
        "notificacoes/<int:pk>/lida/",
        notificacoes_views.marcar_lida,
        name="notificacoes_marcar_lida",
    ),
    path("comunicados/", notificacoes_views.comunicados, name="comunicados"),
    path(
        "administracao/comunicados/",
        notificacoes_views.comunicados_administracao,
        name="comunicados_administracao",
    ),
    path("administracao/envios/", notificacoes_views.envios_lista, name="envios_lista"),
    path(
        "administracao/envios/<int:pk>/",
        notificacoes_views.envio_detalhe,
        name="envio_detalhe",
    ),
    path("pagamentos/avisos/", pagamentos_views.avisos, name="pagamentos_avisos"),
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
        "administracao/rodadas/<int:pk>/fechamento/iniciar/",
        rodadas_views.fechamento_iniciar,
        name="rodadas_fechamento_iniciar",
    ),
    path(
        "administracao/rodadas/<int:pk>/fechamento/prorrogar/",
        rodadas_views.fechamento_prorrogar,
        name="rodadas_fechamento_prorrogar",
    ),
    path(
        "administracao/rodadas/<int:pk>/pagamento/abrir/",
        rodadas_views.pagamento_abrir,
        name="rodadas_pagamento_abrir",
    ),
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
        "administracao/produtos/<int:pk>/incremento/",
        catalogo_views.incremento,
        name="produtos_incremento",
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
