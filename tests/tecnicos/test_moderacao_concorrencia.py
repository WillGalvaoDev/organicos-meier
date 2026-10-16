"""E02-08: moderação em paralelo (acceptance A-15 e A-16)."""

from typing import Any

import pytest

from apps.contas.models import Conta, EmailBanido, Situacao
from apps.contas.moderacao import ModeracaoInvalida, remover, suspender
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ContaFactory

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]


def test_duas_remocoes_simultaneas_da_mesma_conta() -> None:  # A-15
    admin = ContaFactory.create(administrador=True)
    for repeticao in range(10):
        email = f"ana{repeticao}@x.com"
        conta = ContaFactory.create(email_normalizado=email)

        def remocao(barreira: Any, conta_id: int = conta.pk) -> None:
            barreira.wait(timeout=5)
            remover(admin, Conta.objects.get(pk=conta_id))

        resultados = executar_em_paralelo(remocao, remocao)
        sucessos = [r for r in resultados if r.excecao is None]
        recusas = [r.excecao for r in resultados if r.excecao is not None]
        assert len(sucessos) == 1, resultados
        assert len(recusas) == 1
        assert isinstance(recusas[0], ModeracaoInvalida)
        assert EmailBanido.objects.filter(email_normalizado=email).count() == 1
        assert (
            EntradaAuditoria.objects.filter(acao="conta.remover", objeto_id=str(conta.pk)).count()
            == 1
        )
        conta.refresh_from_db()
        assert conta.situacao == Situacao.REMOVIDA


def test_suspender_e_remover_simultaneos() -> None:  # A-16
    admin = ContaFactory.create(administrador=True)
    for repeticao in range(10):
        email = f"bia{repeticao}@x.com"
        conta = ContaFactory.create(email_normalizado=email)

        def suspensao(barreira: Any, conta_id: int = conta.pk) -> None:
            barreira.wait(timeout=5)
            suspender(admin, Conta.objects.get(pk=conta_id))

        def remocao(barreira: Any, conta_id: int = conta.pk) -> None:
            barreira.wait(timeout=5)
            remover(admin, Conta.objects.get(pk=conta_id))

        resultados = executar_em_paralelo(suspensao, remocao)
        erros = [r.excecao for r in resultados if r.excecao is not None]
        assert all(isinstance(e, ModeracaoInvalida) for e in erros), erros
        assert resultados[1].excecao is None  # a remoção sempre conclui
        conta.refresh_from_db()
        assert conta.situacao == Situacao.REMOVIDA
        assert EmailBanido.objects.filter(email_normalizado=email).count() == 1
        assert (
            EntradaAuditoria.objects.filter(acao="conta.remover", objeto_id=str(conta.pk)).count()
            == 1
        )
