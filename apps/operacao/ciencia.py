"""A ciência do administrador (E15-04): encerra um alerta de fato.

Só alerta de natureza `fato` se encerra por ciência. Um alerta de condição encerrado à mão voltaria
na verificação seguinte, enquanto a situação continuasse; os financeiros têm regra própria (E09).
A ciência só muda `resolvido_em` e o motivo do alerta, e grava a auditoria `alerta.ciencia`.
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.contas.models import Conta, Papel, Situacao
from apps.financeiro.models import AlertaFinanceiro
from apps.nucleo.auditoria import registrar_auditoria
from apps.nucleo.tempo import agora
from apps.operacao.tipos import CLASSIFICACAO, Natureza

MOTIVO_DA_CIENCIA = "ciência do administrador"
MENSAGENS = {
    "nao_e_fato": "Este alerta se encerra sozinho quando a situação é resolvida.",
    "ja_resolvido": "Este alerta já foi encerrado.",
}


class CienciaRecusada(Exception):
    """A ciência não pode ser registrada. `codigo` diz o motivo."""

    def __init__(self, codigo: str) -> None:
        self.codigo = codigo
        super().__init__(MENSAGENS[codigo])


def dar_ciencia(autor: Conta | None, alerta: AlertaFinanceiro) -> AlertaFinanceiro:
    """Resolve o alerta de fato com o motivo "ciência do administrador". Só o administrador
    ativo (`PermissionDenied`); com a trava do alerta, duas ciências simultâneas resolvem uma
    vez e a outra recebe `ja_resolvido`."""
    if autor is None or autor.papel != Papel.ADMINISTRADOR or autor.situacao != Situacao.ATIVA:
        raise PermissionDenied
    with transaction.atomic():
        travado = AlertaFinanceiro.objects.select_for_update().get(pk=alerta.pk)
        classificacao = CLASSIFICACAO.get(travado.tipo)
        if classificacao is None or classificacao.natureza != Natureza.FATO:
            raise CienciaRecusada("nao_e_fato")
        if travado.resolvido_em is not None:
            raise CienciaRecusada("ja_resolvido")
        travado.resolvido_em = agora()
        travado.motivo_da_resolucao = MOTIVO_DA_CIENCIA
        travado.save(update_fields=["resolvido_em", "motivo_da_resolucao"])
        registrar_auditoria(
            autor, "alerta.ciencia", travado, {"tipo": travado.tipo, "chave": travado.chave}
        )
    return travado
