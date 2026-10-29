"""Rotas da tela do simulador de pagamentos (E08-07), incluídas em `config/urls.py`."""

from django.urls import URLPattern, path

from apps.simulador_pagamentos import views

urlpatterns: list[URLPattern] = [
    path("", views.lista, name="simulador_pagamentos_lista"),
    path("avisos/entregar/", views.entregar, name="simulador_pagamentos_entregar"),
    path("depositar/", views.depositar, name="simulador_pagamentos_depositar"),
    path("saida/", views.saida, name="simulador_pagamentos_saida"),
    path("<str:id_externo>/aprovar/", views.aprovar, name="simulador_pagamentos_aprovar"),
    path("<str:id_externo>/recusar/", views.recusar, name="simulador_pagamentos_recusar"),
    path("<str:id_externo>/expirar/", views.expirar, name="simulador_pagamentos_expirar"),
]
