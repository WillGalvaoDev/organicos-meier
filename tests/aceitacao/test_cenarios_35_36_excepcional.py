"""Cenários 35 e 36 da especificação funcional: a devolução excepcional confirmada pelo
administrador e as recusas (E10-06, pelo serviço)."""

from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.financeiro.devolucoes import (
    DevolucaoRecusada,
    autorizar_devolucao,
    confirmar_devolucao_excepcional,
)
from apps.financeiro.livro import conta_da_obrigacao
from apps.financeiro.obrigacoes import _liquidado
from apps.notificacoes.models import Notificacao
from apps.pagamentos.chamadas import processar_chamadas
from tests.apoio.devolucoes import (
    Arranjo,
    arranjo_da_devolucao,
    entrar_de_novo,
    levar_a_elegivel,
    montar_tela,
)
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


# --- pelo fluxo da tela (E10-07, A-2, A-9 e A-10) ------------------------------------------------

BASE = "/administracao/financeiro/devolucoes/"


@pytest.fixture
def tela(
    client: Any,
    webauthn: Any,
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    settings: Any,
    tmp_path: Path,
) -> tuple[Arranjo, bytes]:
    settings.MEDIA_ROOT = tmp_path
    return montar_tela(client, simulador_pagamentos, relogio)


def test_cenario_35_pela_tela(client: Any, tela: tuple[Arranjo, bytes]) -> None:
    a, credencial = tela
    levar_a_elegivel(a)
    entrar_de_novo(client, credencial, a.admin)
    resposta = client.post(
        f"{BASE}{a.o1.pk}/excepcional/",
        {
            "meio": "transferencia",
            "identificacao": "TED-9",
            "justificativa": "Devolvido por transferência",
            "comprovante": SimpleUploadedFile("c.pdf", b"%PDF-1.4 comprovante"),
        },
    )
    assert resposta.status_code == 302
    assert Notificacao.objects.filter(conta=a.comprador, titulo="Devolução realizada").count() == 1


def test_cenario_36_pela_tela(client: Any, tela: tuple[Arranjo, bytes]) -> None:
    a, _ = tela
    a.sim.estornos_em_processamento(a.pagamento.id_externo)
    autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas(limite=1)
    resposta = client.post(f"{BASE}{a.o1.pk}/excepcional/", {"meio": "pix"})
    assert resposta.status_code == 409
    assert "há devolução pendente na plataforma" in resposta.content.decode()
