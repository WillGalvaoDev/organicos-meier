"""E02-06: uso simultâneo do mesmo link (acceptance A-13)."""

import re
from typing import Any

import pytest
from django.core import mail
from django.test import Client

from apps.contas.link_de_acesso import LinkInvalido, usar_link
from apps.contas.models import Conta, LinkDeAcesso
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ContaFactory

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]


def test_mesmo_link_em_paralelo_autentica_uma_vez() -> None:  # A-13
    for repeticao in range(20):
        email = f"ana{repeticao}@x.com"
        ContaFactory.create(email_normalizado=email)
        Client().post("/entrar/link/", {"email": email})
        token = re.findall(r"/entrar/link/([A-Za-z0-9_-]+)/", str(mail.outbox[-1].body))[0]

        def usar(barreira: Any, token: str = token) -> Conta:
            barreira.wait(timeout=5)
            return usar_link(token)

        resultados = executar_em_paralelo(usar, usar)
        sucessos = [r for r in resultados if r.excecao is None]
        recusas = [r.excecao for r in resultados if r.excecao is not None]
        assert len(sucessos) == 1, resultados
        assert len(recusas) == 1
        assert isinstance(recusas[0], LinkInvalido)
        assert sucessos[0].valor.email_normalizado == email
        assert LinkDeAcesso.objects.filter(conta__email_normalizado=email).count() == 1
        assert LinkDeAcesso.objects.get(conta__email_normalizado=email).usado_em is not None
