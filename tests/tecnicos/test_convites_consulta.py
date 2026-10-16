"""E02-04: situação derivada e lista de convites (acceptance A-13 a A-15)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.test import Client

from tests.apoio.admin_fluxos import administrador_logado
from tests.fabricas import ConviteFactory

pytestmark = pytest.mark.django_db

T = datetime(2026, 10, 14, 15, 0, 0, tzinfo=UTC)
MS = timedelta(milliseconds=1)


@pytest.mark.parametrize(
    ("deslocamento", "esperada"),
    [(-MS, "pendente"), (timedelta(0), "expirado"), (MS, "expirado")],
    ids=["um_ms_antes", "no_limite", "um_ms_depois"],
)
def test_fronteira_de_expiracao_do_convite(
    relogio: Any, deslocamento: timedelta, esperada: str
) -> None:  # A-13
    convite = ConviteFactory.create(emitido_em=T)
    relogio.congelar(T + timedelta(hours=24) + deslocamento)
    assert convite.situacao == esperada


def test_convite_consumido_tem_situacao_consumido_mesmo_depois_do_prazo(
    relogio: Any,
) -> None:  # A-14
    convite = ConviteFactory.create(emitido_em=T, consumido=True)
    relogio.congelar(T + timedelta(days=5))
    assert convite.situacao == "consumido"
    assert convite.conta_criada is not None


def test_lista_mostra_os_convites_do_mais_recente_para_o_mais_antigo(
    client: Client, webauthn: Any, relogio: Any
) -> None:  # A-14 e A-15
    administrador_logado(client)
    relogio.congelar(T + timedelta(hours=30))
    consumido = ConviteFactory.create(
        email_normalizado="consumido@x.com", emitido_em=T - timedelta(hours=60), consumido=True
    )
    expirado = ConviteFactory.create(
        email_normalizado="expirado@x.com", emitido_em=T - timedelta(hours=40)
    )
    pendente = ConviteFactory.create(
        email_normalizado="pendente@x.com", emitido_em=T + timedelta(hours=20), fornecedor=True
    )
    html = client.get("/administracao/convites/").content.decode()
    posicoes = [html.index(c.email_normalizado) for c in (pendente, expirado, consumido)]
    assert posicoes == sorted(posicoes)  # mais recente primeiro
    assert "pendente" in html
    assert "expirado" in html
    assert "consumido" in html
    assert pendente.fornecedor is not None
    assert pendente.fornecedor.nome in html
    # emissão e expiração do pendente em America/Sao_Paulo (UTC-3)
    assert "15/10/2026 08:00" in html  # T + 20h = 15/10 11:00 UTC = 08:00
    assert "16/10/2026 08:00" in html
    assert consumido.conta_criada is not None
    assert consumido.conta_criada.nome in html


def test_lista_vazia_funciona(client: Client, webauthn: Any) -> None:
    administrador_logado(client)
    assert client.get("/administracao/convites/").status_code == 200
