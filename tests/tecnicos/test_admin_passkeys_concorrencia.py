"""E02-03, correção E02-R02: remoções simultâneas de passkey (acceptance A-16 e A-17).

O administrador nunca fica com zero passkeys, exceto pelo comando de recuperação. As sessões são
reais (autenticadas por passkey, dublê da cerimônia) e as requisições correm em threads com
conexões próprias (`executar_em_paralelo`, E01-05).
"""

import threading
from typing import Any

import pytest
from allauth.mfa.models import Authenticator
from django.test import Client

from apps.contas.adaptadores import AdaptadorMFA
from apps.contas.models import Conta
from tests.apoio.admin_fluxos import (
    administrador_com_passkey,
    cadastrar_passkey,
    entrar_com_passkey_direta,
)
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.webauthn_falso import instalar

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]

ULTIMA = "A última passkey não pode ser removida."


# Teste do revisor (E02-10/review.md, revalidação 8f4dc36), copiado sem alteração do corpo.
# Nome original: test_duas_remocoes_preservam_ultima_passkey
def test_duas_remocoes_preservam_ultima_passkey(monkeypatch):  # type: ignore[no-untyped-def]
    instalar(monkeypatch)
    primeiro = Client()
    conta, chave = administrador_com_passkey(primeiro)
    entrar_com_passkey_direta(primeiro, chave, conta)
    cadastrar_passkey(primeiro, nome="Segunda")
    segundo = Client()
    entrar_com_passkey_direta(segundo, chave, conta)
    ids = list(Authenticator.objects.filter(user=conta).values_list("pk", flat=True))
    assert len(ids) == 2
    sincronizar = threading.Barrier(2)
    original = AdaptadorMFA.can_delete_authenticator

    def checar_e_esperar(self, autenticador):  # type: ignore[no-untyped-def]
        permitido = original(self, autenticador)
        sincronizar.wait(timeout=5)
        return permitido

    monkeypatch.setattr(AdaptadorMFA, "can_delete_authenticator", checar_e_esperar)

    def apagar(cliente, pk):  # type: ignore[no-untyped-def]
        return lambda b: cliente.post(f"/seguranca/webauthn/keys/{pk}/remove/").status_code

    try:
        resultados = executar_em_paralelo(apagar(primeiro, ids[0]), apagar(segundo, ids[1]))
        assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
        assert Authenticator.objects.filter(user=conta).count() >= 1
    finally:
        sincronizar.abort()


def _sessoes(webauthn: Any, quantidade: int) -> tuple[Conta, list[Client]]:
    """Administrador com uma passkey e `quantidade` sessões reais autenticadas por passkey."""
    primeiro = Client()
    conta, chave = administrador_com_passkey(primeiro)
    sessoes = [primeiro]
    entrar_com_passkey_direta(primeiro, chave, conta)
    for _ in range(quantidade - 1):
        cliente = Client()
        entrar_com_passkey_direta(cliente, chave, conta)
        sessoes.append(cliente)
    return conta, sessoes


def _remover_em_paralelo(sessoes: list[Client], ids: list[int]) -> list[Any]:
    def remover(cliente: Client, pk: int) -> Any:
        def operacao(barreira: threading.Barrier) -> int:
            barreira.wait(timeout=5)
            return int(cliente.post(f"/seguranca/webauthn/keys/{pk}/remove/").status_code)

        return operacao

    resultados = executar_em_paralelo(*[remover(c, pk) for c, pk in zip(sessoes, ids, strict=True)])
    assert all(r.excecao is None for r in resultados), [r.excecao for r in resultados]
    assert [r.valor for r in resultados] == [302] * len(sessoes)
    return resultados


def _recusadas(sessoes: list[Client]) -> int:
    """Quantas sessões receberam a mensagem de recusa da última passkey."""
    return sum(
        ULTIMA in cliente.get("/seguranca/webauthn/").content.decode() for cliente in sessoes
    )


def test_duas_remocoes_simultaneas_deixam_exatamente_uma_passkey(webauthn: Any) -> None:  # A-16
    conta, sessoes = _sessoes(webauthn, 2)
    for repeticao in range(10):
        while Authenticator.objects.filter(user=conta).count() < 2:
            cadastrar_passkey(sessoes[0], nome=f"Chave {repeticao}")
        ids = sorted(Authenticator.objects.filter(user=conta).values_list("pk", flat=True))
        assert len(ids) == 2
        _remover_em_paralelo(sessoes, ids)
        assert Authenticator.objects.filter(user=conta).count() == 1, repeticao
        assert _recusadas(sessoes) == 1, repeticao


def test_tres_remocoes_simultaneas_deixam_exatamente_uma_passkey(webauthn: Any) -> None:  # A-17
    conta, sessoes = _sessoes(webauthn, 3)
    cadastrar_passkey(sessoes[0], nome="Segunda")
    cadastrar_passkey(sessoes[0], nome="Terceira")
    ids = sorted(Authenticator.objects.filter(user=conta).values_list("pk", flat=True))
    assert len(ids) == 3
    _remover_em_paralelo(sessoes, ids)
    assert Authenticator.objects.filter(user=conta).count() == 1
    assert _recusadas(sessoes) == 1  # duas remoções passam; só a que sobraria sozinha é recusada
