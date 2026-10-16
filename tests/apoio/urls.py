"""URLconf só de testes: as rotas reais mais uma rota protegida por reautenticação (E02-03)."""

from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, URLResolver, path

from apps.contas.administracao import exige_reautenticacao_por_passkey
from config.urls import urlpatterns as rotas_reais


@exige_reautenticacao_por_passkey
def acao_sensivel(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ação sensível executada")


urlpatterns: list[URLPattern | URLResolver] = [
    *rotas_reais,
    path("teste/acao-sensivel/", acao_sensivel, name="teste_acao_sensivel"),
]
