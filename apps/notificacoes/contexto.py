"""Contador de notificações não lidas no cabeçalho (E04-01)."""

from django.http import HttpRequest

from apps.notificacoes.models import Notificacao


def notificacoes_nao_lidas(request: HttpRequest) -> dict[str, int]:
    """Uma consulta para conta autenticada; nenhuma para anônimo."""
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {"notificacoes_nao_lidas": 0}
    total = Notificacao.objects.filter(conta_id=usuario.pk, lida_em__isnull=True).count()
    return {"notificacoes_nao_lidas": total}
