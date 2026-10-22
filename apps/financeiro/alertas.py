"""Alertas financeiros (E09-03).

Um alerta é identificado por `(tipo, chave)`: a chave vem do fato (o `id_externo` do pagamento, o
`id_movimento` do provedor, a data da conciliação, ou `"geral"` nos estados globais). Há no
máximo um aberto por par; abrir de novo devolve o existente, sem novo aviso. Só a abertura avisa
o administrador, no site e por e-mail, na mesma transação. Nenhum dado pessoal vai no alerta.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, connection, transaction
from django.db.transaction import TransactionManagementError
from django.urls import reverse

from apps.catalogo.templatetags.catalogo import reais
from apps.contas.models import Conta, Papel, Situacao
from apps.financeiro.models import AlertaFinanceiro, Gravidade, TipoDeAlerta
from apps.notificacoes.emissao import emitir_evento_para_varios
from apps.notificacoes.eventos import Evento
from apps.nucleo.auditoria import _validar_sem_segredos
from apps.nucleo.tempo import agora

logger = logging.getLogger(__name__)

MAIOR_CHAVE = 64

GRAVIDADE_POR_TIPO: dict[str, str] = {
    TipoDeAlerta.INVARIANTE_VIOLADO: Gravidade.CRITICO,
    TipoDeAlerta.RESERVA_INSUFICIENTE: Gravidade.AVISO,
    TipoDeAlerta.PAGAMENTO_SEM_CONCILIACAO: Gravidade.AVISO,
    TipoDeAlerta.DIVERGENCIA_NA_CONCILIACAO: Gravidade.AVISO,
    TipoDeAlerta.APROVADO_APOS_A_MARGEM: Gravidade.AVISO,
    TipoDeAlerta.DUPLICIDADE: Gravidade.AVISO,
}


def _valor(dados: dict[str, Any], campo: str) -> str:
    """O valor em reais de um campo de `dados`, ou um traço se ele não veio."""
    bruto = dados.get(campo)
    return "-" if bruto is None else reais(Decimal(str(bruto)))


def _corpo_do_invariante(dados: dict[str, Any]) -> str:
    diferenca = abs(Decimal(str(dados.get("diferenca", "0.00"))))
    return (
        f"O saldo do provedor está {reais(diferenca)} abaixo do dinheiro de terceiros. "
        "Utilizações da reserva e retiradas de receita estão bloqueadas."
    )


def _corpo_da_reserva(dados: dict[str, Any]) -> str:
    return (
        f"Obrigações sem cobertura: {_valor(dados, 'sem_cobertura')}. "
        f"Saldo livre da reserva: {_valor(dados, 'livre')}."
    )


def _corpo_do_pagamento_sem_conciliacao(dados: dict[str, Any]) -> str:
    return (
        f"O pagamento {dados.get('id_externo', '-')} de {_valor(dados, 'valor')} "
        "ainda não tem lançamento no livro-razão."
    )


def _corpo_da_divergencia(dados: dict[str, Any]) -> str:
    data = dados.get("data", "-")
    if "id_movimento" in dados:
        return (
            f"Em {data}, o movimento {dados['id_movimento']} do provedor não tem par no "
            "livro-razão."
        )
    return f"Em {data}, a conciliação achou uma diferença de {_valor(dados, 'diferenca')}."


def _corpo_da_devolucao(dados: dict[str, Any]) -> str:
    return (
        f"Pedido {dados.get('pedido', '-')}, valor {_valor(dados, 'valor')}: "
        "gerou obrigação de devolução integral."
    )


TEXTO_POR_TIPO: dict[str, tuple[str, Callable[[dict[str, Any]], str]]] = {
    TipoDeAlerta.INVARIANTE_VIOLADO: (
        "Alerta crítico: saldo do provedor abaixo das obrigações",
        _corpo_do_invariante,
    ),
    TipoDeAlerta.RESERVA_INSUFICIENTE: ("Reserva insuficiente", _corpo_da_reserva),
    TipoDeAlerta.PAGAMENTO_SEM_CONCILIACAO: (
        "Pagamento sem conciliação",
        _corpo_do_pagamento_sem_conciliacao,
    ),
    TipoDeAlerta.DIVERGENCIA_NA_CONCILIACAO: (
        "Divergência na conciliação diária",
        _corpo_da_divergencia,
    ),
    TipoDeAlerta.APROVADO_APOS_A_MARGEM: (
        "Pagamento aprovado depois da margem",
        _corpo_da_devolucao,
    ),
    TipoDeAlerta.DUPLICIDADE: ("Pagamento em duplicidade", _corpo_da_devolucao),
}


def _exigir_transacao(operacao: str) -> None:
    if not connection.in_atomic_block:
        raise TransactionManagementError(f"{operacao} exige uma transação aberta.")


def _validar(tipo: str, chave: str, dados: dict[str, Any]) -> None:
    if tipo not in GRAVIDADE_POR_TIPO:
        raise ValueError(f"tipo de alerta desconhecido: {tipo!r}")
    if not isinstance(chave, str) or not 1 <= len(chave) <= MAIOR_CHAVE:
        raise ValueError(f"a chave do alerta deve ter de 1 a {MAIOR_CHAVE} caracteres")
    _validar_sem_segredos(dados, "dados")


def _aberto(tipo: str, chave: str) -> AlertaFinanceiro | None:
    alerta: AlertaFinanceiro | None = AlertaFinanceiro.objects.filter(
        tipo=tipo, chave=chave, resolvido_em__isnull=True
    ).first()
    return alerta


def abrir_alerta(tipo: str, chave: str, dados: dict[str, Any]) -> AlertaFinanceiro:
    """Abre o alerta e avisa os administradores, ou devolve o que já está aberto para o par."""
    _exigir_transacao("abrir_alerta")
    _validar(tipo, chave, dados)
    existente = _aberto(tipo, chave)
    if existente is not None:
        return existente
    gravidade = GRAVIDADE_POR_TIPO[tipo]
    try:
        with transaction.atomic():
            alerta = AlertaFinanceiro.objects.create(
                tipo=tipo, chave=chave, gravidade=gravidade, dados=dados, aberto_em=agora()
            )
            _avisar(alerta)
    except IntegrityError:
        # outra transação abriu o mesmo par primeiro: a restrição parcial decidiu
        existente = _aberto(tipo, chave)
        if existente is None:
            raise
        return existente
    nivel = logging.ERROR if gravidade == Gravidade.CRITICO else logging.WARNING
    logger.log(nivel, "Alerta financeiro aberto: tipo=%s chave=%s", tipo, chave)
    return alerta


def _avisar(alerta: AlertaFinanceiro) -> None:
    administradores = list(
        Conta.objects.filter(papel=Papel.ADMINISTRADOR, situacao=Situacao.ATIVA).order_by("pk")
    )
    if not administradores:
        logger.warning(
            "Alerta financeiro %s sem aviso: nenhum administrador ativo (tipo=%s)",
            alerta.pk,
            alerta.tipo,
        )
        return
    titulo, montar_corpo = TEXTO_POR_TIPO[alerta.tipo]
    emitir_evento_para_varios(
        Evento.ALERTA_FINANCEIRO,
        administradores,
        titulo=titulo,
        corpo=montar_corpo(alerta.dados),
        link=reverse("financeiro_resumo"),
        chave_base=f"alerta_financeiro:{alerta.pk}",
    )


def resolver_alerta(tipo: str, chave: str, *, motivo: str) -> AlertaFinanceiro | None:
    """Fecha o alerta aberto do par, com o motivo; sem alerta aberto, devolve `None`."""
    _exigir_transacao("resolver_alerta")
    alerta = _aberto(tipo, chave)
    if alerta is None:
        return None
    resolvido_em: datetime = agora()
    alerta.resolvido_em = resolvido_em
    alerta.motivo_da_resolucao = motivo
    alerta.save(update_fields=["resolvido_em", "motivo_da_resolucao"])
    return alerta


def alertas_abertos(tipo: str | None = None) -> list[AlertaFinanceiro]:
    """Os alertas abertos, os críticos primeiro e depois por ordem de abertura."""
    abertos = AlertaFinanceiro.objects.filter(resolvido_em__isnull=True)
    if tipo is not None:
        abertos = abertos.filter(tipo=tipo)
    return sorted(
        abertos.order_by("aberto_em", "pk"), key=lambda a: a.gravidade != Gravidade.CRITICO
    )
