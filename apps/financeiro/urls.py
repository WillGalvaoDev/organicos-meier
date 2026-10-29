"""Rotas das telas financeiras do administrador (E09-08), incluídas em `config/urls.py`."""

from django.urls import URLPattern, path

from apps.financeiro import views

urlpatterns: list[URLPattern] = [
    path("", views.resumo, name="financeiro_resumo"),
    path("movimentos/", views.movimentos, name="financeiro_movimentos"),
    path("reserva/", views.reserva, name="financeiro_reserva"),
    path("reserva/aporte/", views.aporte, name="financeiro_aporte"),
    path("obrigacoes/<int:pk>/designar/", views.designar, name="financeiro_designar"),
    path(
        "designacoes/<int:pk>/desfazer/",
        views.desfazer_designacao,
        name="financeiro_desfazer_designacao",
    ),
    path("obrigacoes/<int:pk>/cobrir/", views.cobrir_obrigacao, name="financeiro_cobrir_obrigacao"),
    path("despesas/<int:pk>/cobrir/", views.cobrir_despesa, name="financeiro_cobrir_despesa"),
    path("retirada/", views.retirada, name="financeiro_retirada"),
    path("conciliacoes/", views.conciliacoes, name="financeiro_conciliacoes"),
]
