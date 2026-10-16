"""URLconf só de testes com uma rota SEM política, para provar a varredura (E02-10, A-11)."""

from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, URLResolver, path

from config.urls import urlpatterns as rotas_reais


def rota_esquecida(request: HttpRequest) -> HttpResponse:
    return HttpResponse("sem política")


urlpatterns: list[URLPattern | URLResolver] = [
    *rotas_reais,
    path("teste/esquecida/", rota_esquecida, name="teste_rota_esquecida"),
]
