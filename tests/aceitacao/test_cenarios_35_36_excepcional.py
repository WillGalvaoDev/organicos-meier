"""Cenários 35 e 36 da especificação funcional: a devolução excepcional confirmada pelo
administrador e as recusas (E10-06, pelo serviço)."""

from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.financeiro.devolucoes import DevolucaoRecusada, confirmar_devolucao_excepcional
from apps.financeiro.livro import conta_da_obrigacao
from apps.financeiro.obrigacoes import _liquidado
from tests.apoio.devolucoes import Arranjo, arranjo_da_devolucao, levar_a_elegivel
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db


@pytest.fixture
def a(
    relogio: RelogioControlado, simulador_pagamentos: Any, settings: Any, tmp_path: Path
) -> Arranjo:
    settings.MEDIA_ROOT = tmp_path
    return arranjo_da_devolucao(simulador_pagamentos, relogio)


def _confirmar(a: Arranjo, parcela: Any) -> Any:
    return confirmar_devolucao_excepcional(
        parcela,
        autor=a.admin,
        meio="transferencia",
        identificacao="TED-9",
        justificativa="Devolvido por transferência",
        comprovante=SimpleUploadedFile("c.pdf", b"%PDF-1.4 comprovante"),
    )


def test_cenario_35_confirmacao_da_devolucao_excepcional(a: Arranjo) -> None:
    parcela = levar_a_elegivel(a)
    assert a.o1.devido - _liquidado(conta_da_obrigacao(a.o1)) == a.o1.devido  # integral até aqui
    confirmacao = _confirmar(a, parcela)
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida_fora_da_plataforma"
    assert (confirmacao.pedido_id, confirmacao.comprador_id) == (a.pedido.pk, a.comprador.pk)
    assert _liquidado(conta_da_obrigacao(a.o1)) == a.o1.devido


def test_cenario_36_recusas_da_confirmacao(a: Arranjo) -> None:
    parcela = levar_a_elegivel(a)
    _confirmar(a, parcela)
    with pytest.raises(DevolucaoRecusada, match="já confirmada"):
        _confirmar(a, parcela)
