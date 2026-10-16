"""E02-05: consumo de convites em paralelo (acceptance A-13 e A-14)."""

import secrets
from typing import Any

import pytest
from django.db import IntegrityError

from apps.contas.convites import ConviteInvalido, MetodoCadastro, consumir_convite
from apps.contas.models import Conta, Convite, EmailEmUso
from tests.apoio.concorrencia import executar_em_paralelo
from tests.fabricas import ConviteFactory, FornecedorFactory

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]

SENHA = "senha-forte-9271!"


def _convite(**campos: Any) -> tuple[Convite, str]:
    token = secrets.token_urlsafe(32)
    return ConviteFactory.create(token_hash=Convite.hash_do_token(token), **campos), token


def test_mesmo_convite_em_paralelo_cria_uma_conta_e_um_consumo() -> None:  # A-13
    for repeticao in range(20):
        email = f"bia{repeticao}@x.com"
        convite, token = _convite(email_normalizado=email)

        def consumir(barreira: Any, token: str = token) -> Conta:
            barreira.wait(timeout=5)
            return consumir_convite(token, "Bia", SENHA, metodo=MetodoCadastro.SENHA)

        resultados = executar_em_paralelo(consumir, consumir)
        sucessos = [r for r in resultados if r.excecao is None]
        recusas = [r.excecao for r in resultados if r.excecao is not None]
        assert len(sucessos) == 1, resultados
        assert len(recusas) == 1
        assert isinstance(recusas[0], ConviteInvalido)
        assert recusas[0].codigo == "consumido"
        assert Conta.objects.filter(email_normalizado=email).count() == 1
        convite.refresh_from_db()
        assert convite.consumido_em is not None
        assert convite.conta_criada is not None


@pytest.mark.tecnico
def test_dois_convites_com_mesmo_email_normalizado_em_paralelo() -> None:  # A-14, T-34
    fornecedor = FornecedorFactory.create()
    for repeticao in range(10):
        email = f"ana{repeticao}@x.com"
        comprador, token_a = _convite(email_normalizado=email)
        de_fornecedor, token_b = _convite(
            email_normalizado=email, fornecedor=True, fornecedor_id=fornecedor.pk
        )

        def consumir_a(barreira: Any, token: str = token_a) -> Conta:
            barreira.wait(timeout=5)
            return consumir_convite(token, "A", SENHA, metodo=MetodoCadastro.SENHA)

        def consumir_b(barreira: Any, token: str = token_b) -> Conta:
            barreira.wait(timeout=5)
            return consumir_convite(token, "B", SENHA, metodo=MetodoCadastro.SENHA)

        resultados = executar_em_paralelo(consumir_a, consumir_b)
        erros = [r.excecao for r in resultados if r.excecao is not None]
        assert len([r for r in resultados if r.excecao is None]) == 1
        assert len(erros) == 1
        erro = erros[0]
        assert isinstance(erro, ConviteInvalido | IntegrityError | EmailEmUso)
        if isinstance(erro, ConviteInvalido):
            assert erro.codigo == "email_em_uso"
        assert Conta.objects.filter(email_normalizado=email).count() == 1

        comprador.refresh_from_db()
        de_fornecedor.refresh_from_db()
        consumidos = [c for c in (comprador, de_fornecedor) if c.consumido_em is not None]
        assert len(consumidos) == 1  # o recusado continua não consumido
