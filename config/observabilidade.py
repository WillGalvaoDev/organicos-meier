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
# Chaves de identificação pessoal: um segmento da chave (minúscula, dividida por `_`, `-` e `.`)
# igual a um destes (E16-R02, regra 3-B). `first_name` e `telefone_do_comprador` entram;
# `pedido` e `id_externo` não.
_SEGMENTOS_PESSOAIS = frozenset(
    {
        "nome",
        "name",
        "username",
        "usuario",
        "telefone",
        "phone",
        "celular",
        "cpf",
        "endereco",
        "address",
        "ip",
    }
)
# Contextos técnicos do SDK: o nome do interpretador e do sistema não identificam ninguém.
_CONTEXTOS_TECNICOS = frozenset({"runtime", "os", "trace"})
_SEM_TEXTO_LIMPO = {"trace_id", "span_id", "parent_span_id"}
_PARTES_COM_CHAVES_SENSIVEIS = ("extra", "tags", "contexts")

# Rotas com credencial de uso único no caminho (E16-R02, regra 3-A). O segmento do token é qualquer
# sequência sem `/`, `?`, `#` ou espaço; o resto do caminho fica (`/convite/[removido]/google/`).
# O padrão da rota (`/convite/{token}/`, nome da transação) não é um token e fica como está.
ROTAS_COM_SEGREDO = (
    re.compile(r"(/entrar/link/)(?!\{)[^/?#\s]+"),
    re.compile(r"(/convite/)(?!\{)[^/?#\s]+"),
)


def _trocar_tokens(texto: str) -> str:
    for padrao in ROTAS_COM_SEGREDO:
        texto = padrao.sub(rf"\1{REMOVIDO}", texto)
    return texto


def limpar_texto(texto: str) -> str:
    return _TELEFONE.sub(REMOVIDO, _EMAIL.sub(REMOVIDO, _trocar_tokens(texto)))


def _chave_sensivel(chave: str) -> bool:
    segmentos = set(re.split(r"[_\-.]", chave.lower()))
    return bool(_CHAVE_SENSIVEL.search(chave)) or bool(segmentos & _SEGMENTOS_PESSOAIS)


def rotas_com_token_nao_cobertas(padroes: Any) -> list[str]:
    """As rotas com parâmetro `token` que `ROTAS_COM_SEGREDO` não cobre (para o teste que impede
    que uma rota nova com token fique esquecida)."""
    from django.urls import URLPattern, URLResolver

    sentinela = "TOKEN-DE-VERIFICACAO"
    esquecidas: list[str] = []

    def percorrer(lista: Any, prefixo: str) -> None:
        for padrao in lista:
            rota = str(padrao.pattern)
            if isinstance(padrao, URLResolver):
                percorrer(padrao.url_patterns, prefixo + rota)
            elif isinstance(padrao, URLPattern):
                completa = prefixo + rota
                if not re.search(r"<(?:\w+:)?\w*token\w*>|\(\?P<\w*token\w*>", completa):
                    continue
                caminho = "/" + re.sub(
                    r"<(?:\w+:)?(\w+)>|\(\?P<(\w+)>[^)]*\)",
                    lambda m: sentinela if "token" in (m.group(1) or m.group(2)) else "x",
                    completa,
                ).lstrip("^").rstrip("$")
                if sentinela in limpar_texto(caminho):
                    esquecidas.append(completa)

    percorrer(padroes, "")
    return esquecidas


def _limpar_valor(valor: Any, *, chaves_sensiveis: bool) -> Any:
    """Troca e-mails e telefones nos textos; com `chaves_sensiveis`, também os valores de chaves
    como `senha` ou `token`. Percorre dicionários e listas em qualquer profundidade."""
    if isinstance(valor, str):
        return limpar_texto(valor)
    if isinstance(valor, dict):
        limpo = {}
        for chave, item in valor.items():
            if chaves_sensiveis and isinstance(chave, str) and _chave_sensivel(chave):
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
            nova["url"] = limpar_texto(_sem_consulta(requisicao["url"]))
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
        for migalha in migalhas["values"]:
            if isinstance(migalha, dict) and isinstance(migalha.get("data"), dict):
                migalha["data"] = _limpar_valor(migalha["data"], chaves_sensiveis=True)
    usuario = evento.get("user")
    if isinstance(usuario, dict):
        if "id" in usuario:
            evento["user"] = {"id": usuario["id"]}
        else:
            del evento["user"]
    for parte, valor in list(evento.items()):
        if parte in ("request", "user", "event_id", "timestamp", "release", "environment"):
            continue
        if parte == "contexts" and isinstance(valor, dict):
            evento[parte] = {
                nome: _limpar_valor(contexto, chaves_sensiveis=nome not in _CONTEXTOS_TECNICOS)
                for nome, contexto in valor.items()
            }
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
            DjangoIntegration(transaction_style="url"),
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
