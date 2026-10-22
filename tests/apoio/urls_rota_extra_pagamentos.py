"""Rotas de config/urls.py com uma segunda rota em apps.pagamentos (E08-07 A-9, só para teste)."""

from django.urls import path

from apps.pagamentos import views
from config.urls import urlpatterns as _reais

urlpatterns = [*_reais, path("pagamentos-extra/", views.avisos, name="pagamentos_rota_a_mais")]
