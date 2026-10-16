"""E03-02: só o administrador abre rodada e altera o mínimo (acceptance A-17)."""

from decimal import Decimal

import pytest
from django.test import Client

from apps.nucleo.auditoria import EntradaAuditoria
from apps.rodadas.models import EstoqueDaRodada, Etapa, Rodada
from tests.fabricas import (
    ContaFactory,
    EstoqueDaRodadaFactory,
    FornecedorFactory,
    ProdutoFactory,
    RodadaFactory,
)

pytestmark = pytest.mark.django_db


def _rotas(pk: int) -> list[str]:
    return [
        f"/administracao/fornecedores/{pk}/rodadas/abrir/",
        f"/administracao/fornecedores/{pk}/minimo/",
    ]


@pytest.mark.parametrize("fornecedor", [False, True], ids=["comprador", "fornecedor"])
def test_autenticados_que_nao_sao_administrador_recebem_403(
    client: Client, fornecedor: bool
) -> None:
    rodada = RodadaFactory.create(fornecedor=FornecedorFactory.create(minimo=Decimal("150.00")))
    sem_rodada = FornecedorFactory.create()
    client.force_login(ContaFactory.create(fornecedor=fornecedor))
    for rota in [*_rotas(rodada.fornecedor_id), *_rotas(sem_rodada.pk)]:
        assert client.get(rota).status_code == 403, rota
        assert client.post(rota, {"minimo": "999"}).status_code == 403, rota
    rodada.fornecedor.refresh_from_db()
    assert rodada.fornecedor.minimo == Decimal("150.00")
    assert Rodada.objects.count() == 1
    assert rodada.etapa == Etapa.INTERESSE
    assert EntradaAuditoria.objects.count() == 0


def test_visitante_anonimo_vai_para_o_login() -> None:
    alvo = FornecedorFactory.create()
    anonimo = Client()
    for rota in _rotas(alvo.pk):
        for resposta in (anonimo.get(rota), anonimo.post(rota, {"minimo": "9"})):
            assert resposta.status_code == 302, rota
            assert resposta["Location"].startswith("/entrar/"), rota
    assert Rodada.objects.count() == 0


def _rotas_de_estoque(rodada_pk: int, estoque_pk: int) -> list[str]:
    return [
        f"/administracao/rodadas/{rodada_pk}/estoque/",
        f"/administracao/rodadas/{rodada_pk}/estoque/incluir/",
        f"/administracao/estoque/{estoque_pk}/alterar/",
    ]


@pytest.mark.parametrize("fornecedor", [False, True], ids=["comprador", "fornecedor"])
def test_estoque_so_para_administrador(client: Client, fornecedor: bool) -> None:  # A-18
    estoque = EstoqueDaRodadaFactory.create(limite=Decimal("10"))
    outro = ProdutoFactory.create(fornecedor=estoque.rodada.fornecedor)
    client.force_login(ContaFactory.create(fornecedor=fornecedor))
    dados = {"produto": str(outro.pk), "limite": "1"}
    for rota in _rotas_de_estoque(estoque.rodada_id, estoque.pk):
        assert client.get(rota).status_code == 403, rota
        assert client.post(rota, dados).status_code == 403, rota
    estoque.refresh_from_db()
    assert estoque.limite == Decimal("10.000")
    assert EstoqueDaRodada.objects.count() == 1
    assert EntradaAuditoria.objects.count() == 0


def test_estoque_visitante_anonimo_vai_para_o_login() -> None:  # A-18
    estoque = EstoqueDaRodadaFactory.create()
    anonimo = Client()
    for rota in _rotas_de_estoque(estoque.rodada_id, estoque.pk):
        for resposta in (anonimo.get(rota), anonimo.post(rota, {"limite": "1"})):
            assert resposta.status_code == 302, rota
            assert resposta["Location"].startswith("/entrar/"), rota
    assert EstoqueDaRodada.objects.count() == 1
