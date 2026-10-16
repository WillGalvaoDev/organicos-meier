"""E02-07, correção E02-R01: o vínculo com o Google não restaura a situação (acceptance A-21).

Uma thread trava a linha da conta e a suspende (ou remove) e só confirma quando vê a outra
esperando por trava no Postgres; a outra thread é o retorno do Google (rota de teste que entrega o
`SocialLogin` ao `complete_social_login` do allauth, sem rede).
"""

import json
import threading
import time
from typing import Any

import pytest
from allauth.socialaccount.models import SocialAccount
from django.db import connection, transaction
from django.test import Client

from apps.contas.models import Conta, EmailBanido, Situacao
from apps.contas.moderacao import remover, suspender
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ContaFactory

pytestmark = [
    pytest.mark.concorrencia,
    pytest.mark.django_db(transaction=True),
    pytest.mark.urls("tests.apoio.urls"),
]

DADOS = {"sub": "g-concorrencia", "email": "ana@x.com", "email_verified": True, "name": "Ana"}


def _outra_esperando_por_trava() -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' "
            "AND application_name LIKE 'concorrencia-%%' AND pid <> pg_backend_pid()"
        )
        (total,) = cursor.fetchone()
    return int(total) > 0


@pytest.mark.parametrize("acao", ["suspender", "remover"])
def test_vinculo_do_google_nao_desfaz_suspensao_nem_remocao(acao: str) -> None:
    admin = ContaFactory.create(administrador=True)
    conta = ContaFactory.create(email_normalizado="ana@x.com", nome="Ana")
    travada = threading.Event()
    google: dict[str, Any] = {}

    def moderar(barreira: threading.Barrier) -> None:
        with transaction.atomic():
            atual = Conta.objects.select_for_update().get(pk=conta.pk)
            (suspender if acao == "suspender" else remover)(admin, atual)
            travada.set()  # a moderação segura a trava até o Google estar esperando por ela
            limite = time.monotonic() + 10
            while not _outra_esperando_por_trava():
                assert time.monotonic() < limite, "o retorno do Google não esperou pela trava"
                time.sleep(0.02)

    def retorno_do_google(barreira: threading.Barrier) -> None:
        assert travada.wait(timeout=10)
        cliente = Client()
        resposta = cliente.post("/teste/retorno-google/", {"extra_data": json.dumps(DADOS)})
        google["resposta"] = resposta
        google["autenticado"] = "_auth_user_id" in cliente.session

    resultados = executar_em_paralelo(moderar, retorno_do_google, tempo_limite=30)
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]

    conta.refresh_from_db()
    if acao == "suspender":
        assert conta.situacao == Situacao.SUSPENSA  # a suspensa entra: login e vínculo acontecem
        assert google["autenticado"] is True
        assert SocialAccount.objects.filter(user=conta).count() == 1
    else:
        assert conta.situacao == Situacao.REMOVIDA
        assert google["resposta"]["Location"] == "/entrar/"
        assert google["autenticado"] is False
        assert SocialAccount.objects.count() == 0
        assert EmailBanido.objects.filter(email_normalizado="ana@x.com").exists()
