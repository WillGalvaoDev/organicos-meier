"""Controles do simulador de pagamentos (E07-01): o pagador e o provedor, para os testes.

Reproduzem aprovação, recusa, expiração, avisos atrasados, repetidos, fora de ordem ou perdidos,
falhas, indisponibilidade e atraso de consistência. Os controles de situação não passam pelo
plano de falhas: o plano só afeta as operações da interface.
"""

import json
from collections.abc import Callable, Sequence
from datetime import datetime

from django.db import transaction
from django.db.models import F

from apps.nucleo.tempo import agora, somar_horas
from apps.pagamentos.provedor import SituacaoNoProvedor
from apps.simulador_pagamentos import estado
from apps.simulador_pagamentos.models import AvisoSimulado
from apps.simulador_pagamentos.plano import PLANO

Receptor = Callable[[bytes, dict[str, str]], int]

_APROVAVEIS = (
    SituacaoNoProvedor.PENDENTE,
    SituacaoNoProvedor.CANCELADO,
    SituacaoNoProvedor.EXPIRADO,
)


def _instante(em: datetime | None) -> datetime:
    if em is None:
        return agora()
    somar_horas(em, 0)  # recusa o instante sem fuso
    return em


def aprovar(id_externo: str, *, em: datetime | None = None) -> None:
    """Aprova a partir de pendente, cancelada ou expirada (L-2, L-3).

    `em` anterior à criação, ou cobrança já aprovada ou recusada: `ValueError`. Um `em` no
    passado é uma aprovação que o provedor informa depois.
    """
    instante = _instante(em)
    with transaction.atomic():
        cobranca = estado.obter(id_externo, travar=True)
        if cobranca.situacao not in _APROVAVEIS:
            raise ValueError(f"cobrança {cobranca.situacao} não pode ser aprovada")
        if instante < cobranca.criado_em:
            raise ValueError("aprovação anterior à criação da cobrança")
        estado.mudar(cobranca, SituacaoNoProvedor.APROVADO, instante)
    estado.registrar("aprovar", id_externo)


def _encerrar_pendente(id_externo: str, situacao: SituacaoNoProvedor, operacao: str) -> None:
    with transaction.atomic():
        cobranca = estado.obter(id_externo, travar=True)
        if cobranca.situacao != SituacaoNoProvedor.PENDENTE:
            raise ValueError(f"só uma cobrança pendente pode ser {situacao.value}")
        estado.mudar(cobranca, situacao)
    estado.registrar(operacao, id_externo)


def recusar(id_externo: str) -> None:
    _encerrar_pendente(id_externo, SituacaoNoProvedor.RECUSADO, "recusar")


def expirar(id_externo: str) -> None:
    _encerrar_pendente(id_externo, SituacaoNoProvedor.EXPIRADO, "expirar")


def aprovar_no_cancelamento(id_externo: str, *, em: datetime | None = None) -> None:
    """O próximo `cancelar_cobranca` dessa cobrança aprova em vez de cancelar: o pagador
    concluiu no mesmo instante do cancelamento (infraestrutura 4.3)."""
    instante = None if em is None else _instante(em)
    cobranca = estado.obter(id_externo)
    if instante is not None and instante < cobranca.criado_em:
        raise ValueError("aprovação anterior à criação da cobrança")
    PLANO.aprovar_no_cancelamento(cobranca.pk, instante)


def reemitir_aviso(id_externo: str) -> AvisoSimulado:
    """Outro aviso para a mesma cobrança, sem mudar a situação (o provedor repetindo o evento)."""
    estado.obter(id_externo)
    estado.registrar("reemitir_aviso", id_externo)
    return estado.novo_aviso(id_externo)


def avisos_pendentes() -> list[AvisoSimulado]:
    return list(AvisoSimulado.objects.filter(entregas=0, descartado=False).order_by("pk"))


def descartar(aviso: AvisoSimulado) -> None:
    """O aviso perdido: nunca será entregue."""
    AvisoSimulado.objects.filter(pk=aviso.pk).update(descartado=True)
    estado.registrar("descartar", aviso.id_externo)


def corpo_e_cabecalhos(aviso: AvisoSimulado) -> tuple[bytes, dict[str, str]]:
    corpo = json.dumps(
        {"id_evento": aviso.id_evento, "tipo": aviso.tipo, "id_externo": aviso.id_externo},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return corpo, {estado.CABECALHO_DA_ASSINATURA: "sha256=" + estado.assinar(corpo)}


def entregar_avisos(
    avisos: Sequence[AvisoSimulado] | None = None,
    *,
    vezes: int = 1,
    receptor: Receptor | None = None,
) -> list[int]:
    """Entrega os avisos na ordem recebida (por padrão, os pendentes), cada um `vezes` vezes.

    Monta o corpo, assina e chama o `receptor` (por padrão, `receber_aviso`, a função que a rota
    de avisos chama; os testes podem injetar outro); devolve os códigos HTTP.

    Atrasado = não entregar ainda; repetido = `vezes`; fora de ordem = a ordem da lista; perdido
    = `descartar`.
    """
    if receptor is None:
        from apps.pagamentos.avisos import receber_aviso  # a função que a rota de avisos chama

        receptor = receber_aviso
    codigos: list[int] = []
    for aviso in avisos if avisos is not None else avisos_pendentes():
        for _ in range(vezes):
            corpo, cabecalhos = corpo_e_cabecalhos(aviso)
            codigos.append(receptor(corpo, cabecalhos))
            AvisoSimulado.objects.filter(pk=aviso.pk).update(entregas=F("entregas") + 1)
            estado.registrar("entregar_avisos", aviso.id_externo)
    return codigos


def indisponivel() -> None:
    """Toda operação da interface levanta `ProvedorIndisponivel`, até `normalizar()`."""
    PLANO.indisponivel()


def falhar_proximas(
    n: int, *, operacao: str | None = None, depois_de_executar: bool = False
) -> None:
    """As próximas `n` chamadas (de uma operação, ou de qualquer uma) falham. Com
    `depois_de_executar`, a operação é feita e gravada antes da exceção (tempo esgotado depois
    de o provedor aceitar)."""
    PLANO.falhar_proximas(n, operacao, depois_de_executar)


def atrasar_consistencia(id_externo: str, consultas: int) -> None:
    """As próximas `consultas` consultas e buscas do pagamento veem a situação anterior à última
    mudança (L-6)."""
    PLANO.atrasar(estado.obter(id_externo).pk, consultas)


def normalizar() -> None:
    PLANO.normalizar()


def reiniciar() -> None:
    PLANO.reiniciar()
