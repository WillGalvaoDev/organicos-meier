from datetime import datetime

from django import template

from apps.nucleo.tempo import no_fuso_da_operacao

register = template.Library()


@register.filter
def data_hora(instante: datetime) -> str:
    """`dd/mm/aaaa HH:MM` no fuso da operação."""
    return no_fuso_da_operacao(instante).strftime("%d/%m/%Y %H:%M")


@register.filter
def valor_do_mapa(chave: str, mapa: dict[str, str]) -> str:
    """Rótulo legível de um código (situação, canal ou tipo); o próprio código se não houver."""
    return mapa.get(chave, chave)
