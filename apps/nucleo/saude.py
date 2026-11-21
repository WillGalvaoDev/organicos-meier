"""A rota de saúde (E16-01): a verificação que o Fly.io e o monitor de disponibilidade consultam.

Sem autenticação, sem sessão e sem escrita. Não expõe dado, versão nem detalhe de erro: só `ok` ou
`indisponivel`, e o log recebe apenas a classe do erro.
"""

import logging

from django.db import connections
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from apps.contas.permissoes import publica

logger = logging.getLogger(__name__)


@publica
@require_GET
def saude(request: HttpRequest) -> HttpResponse:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as erro:
        logger.error("verificação de saúde falhou: erro=%s", type(erro).__name__)
        return HttpResponse("indisponivel", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
