"""T-9: a devolução excepcional respeita as recusas e bloqueia novas tentativas (E10-06, A-3 a
A-5)."""

from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.financeiro.devolucoes import (
    DevolucaoRecusada,
    autorizar_devolucao,
    confirmar_devolucao_excepcional,
    tentar_devolucao_de_novo,
)
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor
from apps.simulador_pagamentos.models import EstornoSimulado
from tests.apoio.devolucoes import arranjo_da_devolucao, levar_a_elegivel
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db


def _confirmar(a: Any, parcela: Any) -> Any:
    return confirmar_devolucao_excepcional(
        parcela,
        autor=a.admin,
        meio="pix",
        identificacao="E2E-1",
        justificativa="Pix direto",
        comprovante=SimpleUploadedFile("c.pdf", b"%PDF-1.4 x"),
    )


def test_confirmacao_recusada_com_devolucao_pendente_e_bloqueio_depois(
    relogio: RelogioControlado, simulador_pagamentos: Any, settings: Any, tmp_path: Path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    solicitada = autorizar_devolucao(a.o1, autor=a.admin)
    with pytest.raises(DevolucaoRecusada, match="pendente"):
        _confirmar(a, solicitada)
    processar_chamadas()  # a parcela conclui pela plataforma
    solicitada.refresh_from_db()
    assert solicitada.situacao == "concluida"
    with pytest.raises(DevolucaoRecusada, match="já devolvida"):
        _confirmar(a, solicitada)


def test_depois_da_confirmacao_nenhuma_tentativa_chega_ao_provedor(
    relogio: RelogioControlado, simulador_pagamentos: Any, settings: Any, tmp_path: Path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    parcela = levar_a_elegivel(a)
    _confirmar(a, parcela)
    parcela.refresh_from_db()
    with pytest.raises(DevolucaoRecusada):
        tentar_devolucao_de_novo(parcela, autor=a.admin)
    assert autorizar_devolucao(a.o1, autor=a.admin).pk == parcela.pk
    assert not ChamadaAoProvedor.objects.filter(operacao="estornar", situacao="pendente")
    assert EstornoSimulado.objects.count() == 0
