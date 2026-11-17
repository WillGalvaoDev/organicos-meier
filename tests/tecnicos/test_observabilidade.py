"""E16-03: Sentry sem dados pessoais e monitor de cron externo (acceptance A-3 a A-12).

O Sentry roda com um transporte em memória (TM): os envelopes ficam numa lista, sem rede.
"""

import json
import logging
from collections.abc import Callable, Iterator
from typing import Any

import pytest
import sentry_sdk
from django.core.signals import request_finished
from django.db import close_old_connections, connection
from django.test import Client
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from apps.operacao.models import ExecucaoDaTarefa
from config.observabilidade import opcoes_do_sentry
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

DSN = "https://chave-publica@o0.ingest.sentry.io/1"
EMAIL = "ana@exemplo.com"
TELEFONE = "(21) 99999-0000"


class TransporteEmMemoria(Transport):
    def __init__(self, options: Any = None) -> None:
        super().__init__(options)
        self.envelopes: list[Envelope] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        self.envelopes.append(envelope)

    def _itens(self, tipo: str) -> list[dict[str, Any]]:
        return [
            dict(item.payload.json or {})
            for e in self.envelopes
            for item in e.items
            if item.type == tipo
        ]

    def eventos(self) -> list[dict[str, Any]]:
        return self._itens("event")

    def checkins(self) -> list[dict[str, Any]]:
        return self._itens("check_in")

    def texto(self) -> str:
        """Todo o conteúdo enviado, serializado."""
        return " ".join(
            json.dumps(item.payload.json, default=str) for e in self.envelopes for item in e.items
        )


@pytest.fixture
def tm() -> Iterator[TransporteEmMemoria]:
    transporte = TransporteEmMemoria()
    sentry_sdk.init(**opcoes_do_sentry(DSN, "homologacao", None, transport=transporte))
    yield transporte
    sentry_sdk.get_client().close()
    sentry_sdk.init(dsn=None)


# --- inicialização ------------------------------------------------------------------------------


def test_sem_dsn_nada_e_enviado_e_a_tarefa_conclui() -> None:  # A-3
    from apps.operacao import tarefas

    assert not sentry_sdk.get_client().is_active()
    tarefas.verificar_operacao(timestamp=0)
    logging.getLogger("teste").error("um erro qualquer")
    assert not sentry_sdk.get_client().is_active()
    assert ExecucaoDaTarefa.objects.get(nome="verificar_operacao").ultima_conclusao_em is not None


# --- filtro de dados pessoais -------------------------------------------------------------------


@csrf_exempt
def _explode(request: Any) -> Any:
    raise RuntimeError(f"falha para {EMAIL}, tel {TELEFONE}")


urlpatterns: list[Any] = [path("explode/", _explode)]


@pytest.fixture
def com_rota(settings: Any) -> None:
    from config import urls

    # a rota extra vive só neste módulo de testes: ele herda as rotas reais
    urlpatterns[:0] = urls.urlpatterns
    settings.ROOT_URLCONF = "tests.tecnicos.test_observabilidade"


def _chamar_pelo_wsgi(caminho: str, dados: dict[str, str], cookies: str) -> str:
    """A aplicação WSGI de verdade (o Sentry se liga a ela; o cliente de testes não passa por
    ela e, por isso, o evento não teria nem o método nem a URL)."""
    from django.core.wsgi import get_wsgi_application
    from django.test import RequestFactory

    ambiente = RequestFactory().post(caminho, dados, HTTP_COOKIE=cookies).environ
    resposta: dict[str, str] = {}

    def iniciar(
        status: str, cabecalhos: list[tuple[str, str]], exc_info: Any = None
    ) -> Callable[[bytes], object]:
        resposta["status"] = status
        return lambda dado: None

    # como o cliente de testes: a requisição não pode fechar a conexão da transação do teste
    request_finished.disconnect(close_old_connections)
    try:
        b"".join(get_wsgi_application()(ambiente, iniciar))
    finally:
        request_finished.connect(close_old_connections)
    return resposta["status"]


def test_o_evento_de_uma_requisicao_sai_sem_dados_pessoais(
    tm: TransporteEmMemoria, com_rota: None
) -> None:  # A-4
    conta = ContaFactory.create(email_normalizado=EMAIL, nome="Ana Souza")
    conta.set_password("senha-forte-9271!")
    conta.save()
    cliente = Client()
    cliente.post("/entrar/", {"login": EMAIL, "password": "senha-forte-9271!"})
    cliente.cookies["outro"] = "valor-do-cookie-secreto"
    cookies = "; ".join(f"{k}={v.value}" for k, v in cliente.cookies.items())
    status = _chamar_pelo_wsgi(f"/explode/?email={EMAIL}", {"senha": "x"}, cookies)
    assert status.startswith("500")
    (evento,) = tm.eventos()
    requisicao = evento["request"]
    assert requisicao["method"] == "POST"
    assert requisicao["url"].endswith("/explode/")
    assert set(requisicao) <= {"method", "url", "headers"}
    assert set(evento.get("user", {})) <= {"id"}
    mensagem = evento["exception"]["values"][0]["value"]
    assert mensagem == "falha para [removido], tel [removido]"
    texto = tm.texto()
    for proibido in (EMAIL, "99999-0000", "senha=x", "valor-do-cookie-secreto", "Ana Souza"):
        assert proibido not in texto, proibido


def test_extras_e_tags_com_chave_sensivel_sao_removidos(tm: TransporteEmMemoria) -> None:  # A-5
    logging.getLogger("teste").error(
        "x",
        extra={"token": "abc", "email": "b@c.d", "pedido": 7, "chave_da_api": "k"},
    )
    (evento,) = tm.eventos()
    extras = evento["extra"]
    assert extras["token"] == "[removido]"  # noqa: S105
    assert extras["email"] == "[removido]"
    assert extras["chave_da_api"] == "[removido]"
    assert extras["pedido"] == 7


def test_filtro_que_falha_descarta_o_evento(
    tm: TransporteEmMemoria, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-6
    from config import observabilidade

    def quebra(evento: Any) -> Any:
        raise RuntimeError("falha do filtro")

    monkeypatch.setattr(observabilidade, "limpar_evento", quebra)
    sentry_sdk.capture_exception(RuntimeError("erro de teste"))
    assert tm.eventos() == []


def test_breadcrumb_de_sql_e_descartado(tm: TransporteEmMemoria) -> None:  # A-7
    with connection.cursor() as cursor:
        cursor.execute("SELECT %s", [EMAIL])
    try:
        raise RuntimeError("erro depois da consulta")
    except RuntimeError as erro:
        sentry_sdk.capture_exception(erro)
    (evento,) = tm.eventos()
    migalhas = evento.get("breadcrumbs", {}).get("values", [])
    assert not [m for m in migalhas if m.get("category") == "query"]
    assert EMAIL not in tm.texto()


def test_os_filtros_aplicados_diretamente() -> None:  # complementa A-4 e A-7
    from config.observabilidade import antes_de_enviar, antes_do_breadcrumb

    evento: Any = {
        "request": {
            "method": "GET",
            "url": f"http://x.exemplo/rota/?email={EMAIL}",
            "query_string": f"email={EMAIL}",
            "cookies": {"sessionid": "abc"},
            "headers": {"User-Agent": "navegador", "Cookie": "x=1", "Authorization": "Bearer y"},
            "env": {"REMOTE_ADDR": "10.0.0.1"},
            "data": {"senha": "x"},
        },
        "user": {"id": "5", "email": EMAIL, "username": "ana", "ip_address": "10.0.0.1"},
        "message": f"contato {TELEFONE}",
    }
    limpo = antes_de_enviar(evento, {})
    assert limpo is not None
    assert limpo["request"] == {
        "method": "GET",
        "url": "http://x.exemplo/rota/",
        "headers": {"User-Agent": "navegador"},
    }
    assert limpo["user"] == {"id": "5"}
    assert limpo["message"] == "contato [removido]"
    assert antes_do_breadcrumb({"category": "query", "message": "SELECT 1"}, {}) is None
    http = antes_do_breadcrumb(
        {"category": "httplib", "data": {"url": f"https://api.exemplo/x?email={EMAIL}"}}, {}
    )
    assert http is not None
    assert http["data"]["url"] == "https://api.exemplo/x"
    texto = antes_do_breadcrumb({"category": "log", "message": f"oi {EMAIL}"}, {})
    assert texto is not None
    assert texto["message"] == "oi [removido]"


# --- monitor de cron ----------------------------------------------------------------------------


def test_verificar_operacao_manda_os_checkins(tm: TransporteEmMemoria) -> None:  # A-8
    from apps.operacao import tarefas

    tarefas.verificar_operacao(timestamp=0)
    checkins = tm.checkins()
    assert [c["status"] for c in checkins] == ["in_progress", "ok"]
    assert {c["monitor_slug"] for c in checkins} == {"verificar-operacao"}
    assert len({c["check_in_id"] for c in checkins}) == 1
    configuracao = checkins[0]["monitor_config"]
    assert configuracao["schedule"] == {"type": "crontab", "value": "*/5 * * * *"}
    assert configuracao["checkin_margin"] == 10
    assert configuracao["max_runtime"] == 5
    assert configuracao["timezone"] == "UTC"


def test_falha_do_corpo_manda_error_e_repassa(
    tm: TransporteEmMemoria, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-9
    from apps.operacao import tarefas

    def quebra() -> None:
        raise RuntimeError("falha de teste")

    monkeypatch.setattr(tarefas, "verificar_operacao_agora", quebra)
    with pytest.raises(RuntimeError):
        tarefas.verificar_operacao(timestamp=0)
    assert [c["status"] for c in tm.checkins()] == ["in_progress", "error"]
    assert ExecucaoDaTarefa.objects.get(nome="verificar_operacao").ultimo_erro == "RuntimeError"


def test_falha_do_envio_do_checkin_nao_muda_a_tarefa(
    tm: TransporteEmMemoria, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:  # A-10
    import sentry_sdk.crons

    from apps.operacao import tarefas

    def sem_rede(*args: Any, **kwargs: Any) -> Any:
        raise ConnectionError("sem rede")

    monkeypatch.setattr(sentry_sdk.crons, "capture_checkin", sem_rede)
    with caplog.at_level(logging.ERROR):
        tarefas.verificar_operacao(timestamp=0)
    assert ExecucaoDaTarefa.objects.get(nome="verificar_operacao").ultima_conclusao_em is not None
    assert any("ConnectionError" in r.getMessage() for r in caplog.records)


def test_outras_tarefas_nao_mandam_checkin(tm: TransporteEmMemoria) -> None:  # A-11
    from apps.financeiro import tarefas as financeiro
    from apps.notificacoes.tarefas import processar_envios_pendentes

    processar_envios_pendentes(timestamp=0)
    financeiro.verificar_invariante(timestamp=0)
    assert tm.checkins() == []


def test_monitores_externos() -> None:  # A-12
    from apps.operacao.monitores_externos import MONITORES_EXTERNOS, slug_do_monitor

    monitor = MONITORES_EXTERNOS["verificar_operacao"]
    assert (monitor.schedule, monitor.checkin_margin, monitor.max_runtime) == ("*/5 * * * *", 10, 5)
    assert slug_do_monitor("verificar_operacao") == "verificar-operacao"
