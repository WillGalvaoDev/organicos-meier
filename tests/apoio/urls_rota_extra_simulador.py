"""Rotas de config/urls.py com uma sexta rota no simulador (E08-07 A-9, só para teste)."""

from django.urls import path

from apps.simulador_pagamentos import views
from config.urls import urlpatterns as _reais

urlpatterns = [*_reais, path("simulador-extra/", views.lista, name="simulador_rota_a_mais")]
