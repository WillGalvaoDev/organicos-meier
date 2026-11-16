"""Os tipos de alerta operacional (E15-02): gravidade, natureza, texto e link de cada um.

Os alertas operacionais usam o mesmo modelo e as mesmas funções dos financeiros (`AlertaFinanceiro`,
`abrir_alerta`, `resolver_alerta`). Cada módulo de verificação registra aqui os seus tipos.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from django.urls import reverse

from apps.nucleo.tempo import no_fuso_da_operacao

if TYPE_CHECKING:
    from apps.financeiro.models import AlertaFinanceiro


class Natureza(StrEnum):
    CONDICAO = "condicao"  # aberto enquanto a situação dura; resolvido pela verificação
    FATO = "fato"  # registra um acontecimento; resolvido pela ciência do administrador


@dataclass(frozen=True)
class Classificacao:
    gravidade: str
    natureza: Natureza
    titulo: str
    corpo: Callable[[dict[str, Any]], str]
    link: Callable[[dict[str, Any]], str]


CLASSIFICACAO: dict[str, Classificacao] = {}


def registrar_tipo(tipo: str, classificacao: Classificacao) -> None:
    CLASSIFICACAO[tipo] = classificacao


def data_e_hora(iso: str) -> str:
    """Um instante ISO em Brasília, `dd/mm/aaaa hh:mm`."""
    return f"{no_fuso_da_operacao(datetime.fromisoformat(iso)):%d/%m/%Y %H:%M}"


def link_do_alerta(alerta: "AlertaFinanceiro") -> str:
    """A URL do alerta: a do tipo operacional ou a tela financeira."""
    classificacao = CLASSIFICACAO.get(alerta.tipo)
    if classificacao is None:
        return reverse("financeiro_resumo")
    return classificacao.link(alerta.dados)


def natureza_do_alerta(alerta: "AlertaFinanceiro") -> str | None:
    """`condicao` ou `fato`; `None` para os alertas financeiros."""
    classificacao = CLASSIFICACAO.get(alerta.tipo)
    return None if classificacao is None else str(classificacao.natureza)
