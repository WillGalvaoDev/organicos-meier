from django.conf import settings
from django.http import HttpRequest


def google_habilitado(request: HttpRequest) -> dict[str, bool]:
    """O botão do Google só aparece quando as credenciais estão configuradas."""
    return {"GOOGLE_HABILITADO": bool(settings.GOOGLE_CLIENT_ID)}
