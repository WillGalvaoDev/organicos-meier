"""Rota pública dos avisos do provedor (E07-05); a autenticidade vem da assinatura."""

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.contas.permissoes import publica
from apps.pagamentos.avisos import receber_aviso


@publica
@csrf_exempt
@require_POST
def avisos(request: HttpRequest) -> HttpResponse:
    return HttpResponse(status=receber_aviso(request.body, request.headers))
