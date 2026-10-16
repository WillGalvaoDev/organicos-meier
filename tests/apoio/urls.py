"""URLconf só de testes: as rotas reais mais rotas de apoio (E02-03 e E02-07)."""

import json

from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.helpers import complete_social_login
from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, URLResolver, path
from django.views.decorators.csrf import csrf_exempt

from apps.contas.administracao import exige_reautenticacao_por_passkey
from config.urls import urlpatterns as rotas_reais


@exige_reautenticacao_por_passkey
def acao_sensivel(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ação sensível executada")


@csrf_exempt
def retorno_google_simulado(request: HttpRequest) -> HttpResponse:
    """Simula o retorno do Google sem rede (E02-07).

    Monta o `SocialLogin` como o callback real faz (`sociallogin_from_response`) e o entrega à
    API de conclusão de login social do allauth (`complete_social_login`). O adaptador do projeto
    não é substituído.
    """
    dados = json.loads(request.POST["extra_data"])
    provedor = get_adapter().get_provider(request, "google")
    sociallogin = provedor.sociallogin_from_response(request, dados)
    sociallogin.state = {"process": "login"}
    resposta: HttpResponse = complete_social_login(request, sociallogin)
    return resposta


urlpatterns: list[URLPattern | URLResolver] = [
    *rotas_reais,
    path("teste/acao-sensivel/", acao_sensivel, name="teste_acao_sensivel"),
    path("teste/retorno-google/", retorno_google_simulado, name="teste_retorno_google"),
]
