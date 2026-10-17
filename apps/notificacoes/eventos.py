"""Catálogo de eventos e canais das notificações (E04-01)."""

from django.db import models

from apps.contas.models import Papel


class Evento(models.TextChoices):
    PRECO_ALTERADO = "preco_alterado", "Alteração de preço"
    FECHAMENTO_INICIADO = "fechamento_iniciado", "Início do fechamento"
    EXCEDENTES_REMOVIDOS = "excedentes_removidos", "Remoção de excedentes de caixa"
    PAGAMENTO_ABERTO = "pagamento_aberto", "Abertura do pagamento"
    PAGAMENTO_CONFIRMADO = "pagamento_confirmado", "Pagamento confirmado"
    ITENS_CANCELADOS = "itens_cancelados", "Cancelamento de itens"
    RETORNO_PARA_INTERESSE = "retorno_para_interesse", "Retorno para interesse"
    ESTORNO = "estorno", "Estorno"
    PREVISAO_DE_ENTREGA_ALTERADA = (
        "previsao_de_entrega_alterada",
        "Alteração de previsão de entrega",
    )
    RETIRADA_LIBERADA = "retirada_liberada", "Liberação de retirada"
    RODADA_CANCELADA = "rodada_cancelada", "Cancelamento da rodada"
    COMUNICADO = "comunicado", "Comunicado"
    FALHA_NO_PEDIDO_FORMAL = "falha_no_pedido_formal", "Falha no pedido formal"


class Canal(models.TextChoices):
    SITE = "site", "Site"
    EMAIL = "email", "E-mail"
    WHATSAPP = "whatsapp", "WhatsApp"


_SITE = frozenset({Canal.SITE})
_SITE_E_EMAIL = frozenset({Canal.SITE, Canal.EMAIL})
_TODOS = frozenset({Canal.SITE, Canal.EMAIL, Canal.WHATSAPP})

# A §12 delega à especificação técnica a distribuição dos eventos entre os canais. O site é o
# único canal que não depende de serviço externo. O e-mail vai em todos, menos no preço (§5.1:
# só o site). O WhatsApp vai só nos eventos com prazo ou ação imediata, sempre condicionado ao
# número e ao consentimento (E04-04).
CANAIS_POR_EVENTO: dict[Evento, frozenset[Canal]] = {
    Evento.PRECO_ALTERADO: _SITE,
    Evento.FECHAMENTO_INICIADO: _TODOS,
    Evento.EXCEDENTES_REMOVIDOS: _SITE_E_EMAIL,
    Evento.PAGAMENTO_ABERTO: _TODOS,
    Evento.PAGAMENTO_CONFIRMADO: _SITE_E_EMAIL,
    Evento.ITENS_CANCELADOS: _SITE_E_EMAIL,
    Evento.RETORNO_PARA_INTERESSE: _SITE_E_EMAIL,
    Evento.ESTORNO: _SITE_E_EMAIL,
    Evento.PREVISAO_DE_ENTREGA_ALTERADA: _SITE_E_EMAIL,
    Evento.RETIRADA_LIBERADA: _TODOS,
    Evento.RODADA_CANCELADA: _TODOS,
    Evento.COMUNICADO: _TODOS,
    Evento.FALHA_NO_PEDIDO_FORMAL: _SITE_E_EMAIL,
}

DESTINATARIO_POR_EVENTO: dict[Evento, Papel] = {
    evento: Papel.ADMINISTRADOR if evento is Evento.FALHA_NO_PEDIDO_FORMAL else Papel.COMPRADOR
    for evento in Evento
}
