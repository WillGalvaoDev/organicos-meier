"""E10-07: avisos de estorno ao comprador (acceptance A-15 a A-20)."""

from typing import Any

import pytest

from apps.financeiro.devolucoes import autorizar_devolucao
from apps.notificacoes.models import Notificacao
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import ChamadaAoProvedor
from tests.apoio.devolucoes import (
    Arranjo,
    arranjo_da_devolucao,
    duplicidade,
    levar_a_elegivel,
    sem_pedido,
)
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db


@pytest.fixture
def a(relogio: RelogioControlado, simulador_pagamentos: Any) -> Arranjo:
    return arranjo_da_devolucao(simulador_pagamentos, relogio)


def _avisos(a: Arranjo) -> list[Notificacao]:
    return list(Notificacao.objects.filter(conta=a.comprador, evento="estorno").order_by("pk"))


def test_autorizada_e_concluida_gera_dois_avisos(a: Arranjo) -> None:  # A-15
    autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    avisos = _avisos(a)
    assert [n.titulo for n in avisos] == ["Estorno solicitado", "Estorno concluído"]
    assert "R$ 31,25" in avisos[0].corpo
    assert "Ocorrência na entrega" in avisos[1].corpo
    assert all(n.link == f"/pedidos/{a.pedido.pk}/" for n in avisos)


def test_elegivel_avisa_o_comprador_e_a_falha_nao(a: Arranjo) -> None:  # A-16
    a.sim.falhar_proximas(1, operacao="estornar")
    levar_a_elegivel(a)
    avisos = _avisos(a)
    assert [n.titulo for n in avisos] == ["Estorno solicitado", "Estorno em andamento"]
    corpo = avisos[1].corpo
    assert "O administrador fará a devolução diretamente por Pix ou transferência" in corpo
    assert "prazo_vencido" not in corpo


def test_duplo_envio_gera_uma_parcela_e_um_aviso(a: Arranjo) -> None:  # A-17
    autorizar_devolucao(a.o1, autor=a.admin)
    autorizar_devolucao(a.o1, autor=a.admin)
    assert len(_avisos(a)) == 1


def test_duplicidade_concluida_cita_o_motivo(a: Arranjo) -> None:  # A-18
    _, obrigacao = duplicidade(a)
    autorizar_devolucao(obrigacao, autor=a.admin)
    processar_chamadas()
    avisos = _avisos(a)
    assert avisos[-1].titulo == "Estorno concluído"
    assert "Pagamento em duplicidade" in avisos[-1].corpo


def test_pagamento_sem_pedido_nao_gera_aviso(a: Arranjo) -> None:  # A-19
    _, obrigacao = sem_pedido(a)
    antes = Notificacao.objects.filter(evento="estorno").count()
    autorizar_devolucao(obrigacao, autor=a.admin)
    processar_chamadas()
    assert Notificacao.objects.filter(evento="estorno").count() == antes


def test_falha_depois_da_emissao_desfaz_o_aviso_e_a_conclusao(
    a: Arranjo, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-20
    from apps.financeiro.obrigacoes import liquidar_obrigacao as original

    chamadas = {"n": 0}

    def estoura(*args: Any, **kwargs: Any) -> Any:
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise RuntimeError("falha de teste")
        return original(*args, **kwargs)

    monkeypatch.setattr("apps.financeiro.devolucoes.liquidar_obrigacao", estoura)
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "solicitada"
    assert [n.titulo for n in _avisos(a)] == ["Estorno solicitado"]
    assert ChamadaAoProvedor.objects.filter(operacao="estornar", situacao="pendente").exists()
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert [n.titulo for n in _avisos(a)] == ["Estorno solicitado", "Estorno concluído"]
