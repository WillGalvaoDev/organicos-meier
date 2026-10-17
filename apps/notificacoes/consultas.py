"""Consulta administrativa dos envios (E04-07). Só leitura.

Nada aqui grava. Os envios de acesso não têm token nem corpo no banco (E04-05), então a consulta
não tem como mostrá-los.
"""

from collections.abc import Mapping

from django.db.models import OuterRef, QuerySet, Subquery

from apps.notificacoes.eventos import Canal, Evento
from apps.notificacoes.models import Envio, SituacaoEnvio, TentativaDeEnvio

# "enviado" é aceitação pelo serviço, e não entrega (L-13): vale para os dois canais
ROTULOS_SITUACAO = {
    SituacaoEnvio.PENDENTE.value: "Pendente",
    SituacaoEnvio.ENVIADO.value: "Aceito pelo serviço",
    SituacaoEnvio.FALHOU.value: "Falhou",
    SituacaoEnvio.CANCELADO.value: "Cancelado",
}
ROTULOS_CANAL = {Canal.EMAIL.value: "E-mail", Canal.WHATSAPP.value: "WhatsApp"}
ROTULOS_TIPO = {
    **{evento.value: str(evento.label) for evento in Evento},
    "acesso:convite": "Convite",
    "acesso:link_de_acesso": "Link de acesso",
    "acesso:conta_allauth": "Recuperação de senha",
}


def filtros_validos(filtros: Mapping[str, str]) -> dict[str, str]:
    """Só os filtros com valor conhecido; o resto é ignorado, sem erro."""
    aceitos = {
        "situacao": ROTULOS_SITUACAO,
        "canal": ROTULOS_CANAL,
        "tipo": ROTULOS_TIPO,
    }
    return {
        campo: filtros[campo] for campo, validos in aceitos.items() if filtros.get(campo) in validos
    }


def envios_para_administracao(filtros: Mapping[str, str]) -> QuerySet[Envio]:
    """Do mais recente para o mais antigo, com a classe do último erro (sem N+1)."""
    ultimo_erro = (
        TentativaDeEnvio.objects.filter(envio=OuterRef("pk"))
        .exclude(erro="")
        .order_by("-numero")
        .values("erro")[:1]
    )
    return (
        Envio.objects.filter(**filtros_validos(filtros))
        .select_related("conta")
        .annotate(ultimo_erro=Subquery(ultimo_erro))
        .order_by("-criado_em", "-id")
    )


def contar_falhas() -> int:
    return Envio.objects.filter(situacao=SituacaoEnvio.FALHOU).count()
