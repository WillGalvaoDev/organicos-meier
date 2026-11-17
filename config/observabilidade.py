"""Sentry sem dados pessoais (E16-03).

O Sentry roda em homologação e produção. Nenhum e-mail, telefone, nome, cookie, token, corpo de
requisição ou parâmetro SQL sai para fora do país (infraestrutura 5): os filtros abaixo limpam cada
evento e cada breadcrumb antes do envio e, se o filtro falhar, o evento é descartado.
"""

import logging
import os
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)

REMOVIDO = "[removido]"
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# telefone brasileiro, com ou sem DDI, parênteses e hífen; isolado de letras e dígitos (os
# identificadores hexadecimais do próprio Sentry não casam)
_TELEFONE = re.compile(r"(?<!\w)(?:\+?55[\s-]?)?\(?\d{2}\)?[\s-]?9?\d{4}[\s-]?\d{4}(?!\w)")
_CHAVE_SENSIVEL = re.compile(
    r"senha|password|token|secret|segredo|chave|key|authorization|cookie|email|whatsapp",
    re.IGNORECASE,
)
_SEM_TEXTO_LIMPO = {"trace_id", "span_id", "parent_span_id"}
_PARTES_COM_CHAVES_SENSIVEIS = ("extra", "tags", "contexts")


def limpar_texto(texto: str) -> str:
    return _TELEFONE.sub(REMOVIDO, _EMAIL.sub(REMOVIDO, texto))


def _limpar_valor(valor: Any, *, chaves_sensiveis: bool) -> Any:
    """Troca e-mails e telefones nos textos; com `chaves_sensiveis`, também os valores de chaves
    como `senha` ou `token`. Percorre dicionários e listas em qualquer profundidade."""
    if isinstance(valor, str):
        return limpar_texto(valor)
    if isinstance(valor, dict):
        limpo = {}
        for chave, item in valor.items():
            if chaves_sensiveis and isinstance(chave, str) and _CHAVE_SENSIVEL.search(chave):
                limpo[chave] = REMOVIDO
            elif chave in _SEM_TEXTO_LIMPO:
                limpo[chave] = item
            else:
                limpo[chave] = _limpar_valor(item, chaves_sensiveis=chaves_sensiveis)
        return limpo
    if isinstance(valor, list):
        return [_limpar_valor(item, chaves_sensiveis=chaves_sensiveis) for item in valor]
    return valor


def _sem_consulta(url: str) -> str:
    partes = urlsplit(url)
    return urlunsplit((partes.scheme, partes.netloc, partes.path, "", ""))


def limpar_evento(evento: dict[str, Any]) -> dict[str, Any]:
    """O evento só com o que pode sair: método e caminho da requisição (mais o `User-Agent`), só o
    `id` do usuário, textos sem e-mail nem telefone e valores sensíveis removidos."""
    requisicao = evento.get("request")
    if isinstance(requisicao, dict):
        nova: dict[str, Any] = {}
        if "method" in requisicao:
            nova["method"] = requisicao["method"]
        if isinstance(requisicao.get("url"), str):
            nova["url"] = _sem_consulta(requisicao["url"])
        cabecalhos = requisicao.get("headers")
        if isinstance(cabecalhos, dict):
            agente = {k: v for k, v in cabecalhos.items() if str(k).lower() == "user-agent"}
            if agente:
                nova["headers"] = agente
        evento["request"] = nova
    migalhas = evento.get("breadcrumbs")
    if isinstance(migalhas, dict) and isinstance(migalhas.get("values"), list):
        migalhas["values"] = [
            m
            for m in migalhas["values"]
            if not (isinstance(m, dict) and m.get("category") == "query")
        ]
    usuario = evento.get("user")
    if isinstance(usuario, dict):
        if "id" in usuario:
            evento["user"] = {"id": usuario["id"]}
        else:
            del evento["user"]
    for parte, valor in list(evento.items()):
        if parte in ("request", "user", "event_id", "timestamp", "release", "environment"):
            continue
        evento[parte] = _limpar_valor(valor, chaves_sensiveis=parte in _PARTES_COM_CHAVES_SENSIVEIS)
    return evento


def antes_de_enviar(evento: Any, dica: Any) -> Any:
    """`before_send`: nunca deixa sair um evento sem filtro; se o filtro falhar, descarta."""
    try:
        return limpar_evento(evento)
    except Exception as erro:
        logger.error("filtro do Sentry falhou; evento descartado: erro=%s", type(erro).__name__)
        return None


def antes_do_breadcrumb(migalha: Any, dica: Any) -> Any:
    """`before_breadcrumb`: descarta as consultas SQL, tira a query string das requisições de saída
    e limpa os textos."""
    try:
        if migalha.get("category") == "query":
            return None
        dados = migalha.get("data")
        if isinstance(dados, dict) and isinstance(dados.get("url"), str):
            dados["url"] = _sem_consulta(dados["url"])
        return _limpar_valor(migalha, chaves_sensiveis=False)
    except Exception as erro:
        logger.error("filtro do Sentry falhou; breadcrumb descartado: erro=%s", type(erro).__name__)
        return None


def opcoes_do_sentry(
    dsn: str, ambiente: str, release: str | None, *, transport: Any = None
) -> dict[str, Any]:
    """As opções de `sentry_sdk.init`, as mesmas em produção e nos testes."""
    opcoes: dict[str, Any] = {
        "dsn": dsn,
        "environment": ambiente,
        "release": release,
        "send_default_pii": False,
        "include_local_variables": False,
        "max_request_body_size": "never",
        "traces_sample_rate": 0,
        "integrations": [
            DjangoIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        "before_send": antes_de_enviar,
        "before_breadcrumb": antes_do_breadcrumb,
    }
    if transport is not None:
        opcoes["transport"] = transport
    return opcoes


def iniciar_sentry(dsn: str, ambiente: str, iniciar: Callable[..., Any] = sentry_sdk.init) -> None:
    iniciar(**opcoes_do_sentry(dsn, ambiente, os.environ.get("VERSAO_DA_APLICACAO") or None))
