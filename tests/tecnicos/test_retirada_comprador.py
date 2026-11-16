"""E14-07: o que o comprador vê da entrega e da retirada, e as recusas por acesso direto
(acceptance A-1 a A-12)."""

import re
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from tests.apoio.apuracao import H
from tests.apoio.entrega import (
    ae_liberada,
    arranjo_ae,
    descartar,
    item_de,
    liberar,
    ocorrer,
    receber,
    registrar_endereco,
    retirar,
)
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
L = T0 + 72 * H
PRAZO_FINAL = L + timedelta(days=7)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _como(conta: Any) -> Client:
    cliente = Client()
    cliente.force_login(conta)
    return cliente


def _pagina(conta: Any, pedido: Any) -> Any:
    return _como(conta).get(f"/pedidos/{pedido.pk}/")


def test_a_ocorrencia_no_pedido_do_comprador(relogio: RelogioControlado, sim: Any) -> None:  # A-1
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    texto = _texto(_pagina(a.a, x))
    assert "Ocorrências de entrega" in texto
    assert re.search(r"04/11/2026 10:00 · P1 · Faltante · 2 unidade", texto)
    assert "Reembolso de R$ 23,59" in texto
    assert "Devida" in texto
    assert a.admin.nome not in texto


def test_a_devolucao_concluida_aparece_como_concluida(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    from apps.financeiro.devolucoes import autorizar_devolucao
    from apps.pagamentos.chamadas import processar_chamadas

    a, x, _y, _pf = arranjo_ae(relogio, sim)
    resultado = ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    autorizar_devolucao(resultado.reembolso.obrigacao, autor=a.admin)
    processar_chamadas()
    sim.entregar_avisos()
    processar_chamadas()
    assert "Concluída" in _texto(_pagina(a.a, x))


def test_a_retirada_liberada_no_pedido(relogio: RelogioControlado, sim: Any) -> None:  # A-3
    a, x, _y, _pf = ae_liberada(relogio, sim)
    retirar(a.admin, item_de(x, a.p1), D("4"))
    texto = _texto(_pagina(a.a, x))
    frase = (
        "Retirada liberada em 05/11/2026 10:00. Retire até 12/11/2026 10:00 (horário de Brasília)."
    )
    assert frase in texto
    assert "Endereço: Rua das Hortas, 100" in texto
    assert re.search(r"P1 6 0 4 0 2", texto)
    assert re.search(r"P2 4 0 0 0 4", texto)


def test_depois_do_prazo_sem_descarte(relogio: RelogioControlado, sim: Any) -> None:  # A-4
    a, x, _y, _pf = ae_liberada(relogio, sim)
    retirar(a.admin, item_de(x, a.p1), D("4"))
    relogio.congelar(L + timedelta(days=8))
    texto = _texto(_pagina(a.a, x))
    assert "Prazo de retirada encerrado em 12/11/2026 10:00." in texto
    assert "Fale com o administrador sobre os itens não retirados." in texto
    assert re.search(r"P1 6 0 4 0 2", texto)
    assert re.search(r"P2 4 0 0 0 4", texto)


def test_o_descarte_aparece_depois_de_registrado(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    a, x, _y, _pf = ae_liberada(relogio, sim)
    retirar(a.admin, item_de(x, a.p1), D("4"))
    relogio.congelar(PRAZO_FINAL)
    descartar(a.admin, item_de(x, a.p1), D("2"))
    assert re.search(r"P1 6 0 4 2 0", _texto(_pagina(a.a, x)))


def test_o_reembolso_entra_na_coluna_de_reembolsado(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    registrar_endereco(a.admin)
    receber(a.admin, a.rodada, a.p1, D("9"))
    receber(a.admin, a.rodada, a.p2, D("12"))
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    liberar(relogio, a)
    assert re.search(r"P1 6 2 0 0 4", _texto(_pagina(a.a, x)))


def test_antes_da_liberacao_sem_a_secao_de_retirada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    texto = _texto(_pagina(a.a, x))
    assert "Retirada liberada" not in texto
    assert "Previsão de entrega: 11/11/2026." in texto


def test_o_comprador_suspenso_ve_a_retirada(relogio: RelogioControlado, sim: Any) -> None:  # A-8
    from apps.contas.models import Conta

    a, x, _y, _pf = ae_liberada(relogio, sim)
    Conta.objects.filter(pk=a.a.pk).update(situacao="suspensa")
    a.a.refresh_from_db()
    resposta = _pagina(a.a, x)
    assert resposta.status_code == 200
    assert "Retirada liberada em" in _texto(resposta)


def test_a_pagina_nao_tem_formulario_de_falta(relogio: RelogioControlado, sim: Any) -> None:  # A-9
    base, x0, _y0, _pf0 = arranjo_ae(relogio, sim)
    antes = _pagina(base.a, x0).content.decode()
    a, x, _y, _pf = ae_liberada(relogio, sim)
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "incorreto")
    depois = _pagina(a.a, x).content.decode()
    assert len(re.findall(r"<form", depois)) == len(re.findall(r"<form", antes))
    assert len(re.findall(r"<button", depois)) == len(re.findall(r"<button", antes))
    for campo in ('name="tipo"', 'name="item"', 'name="quantidade"'):
        assert campo not in depois


def test_a_pagina_de_outro_comprador_e_recusada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-10
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    resposta = _pagina(a.b, x)
    assert resposta.status_code == 404
    assert "Faltante" not in resposta.content.decode()


ROTAS_DA_E14 = (
    "recebimento/registrar",
    "retirada/liberar",
    "ocorrencias/registrar",
    "retiradas/registrar",
    "descartes/registrar",
)


def _total_de_registros() -> Any:
    from apps.financeiro.models import Reembolso
    from apps.pedidos.models import (
        DescarteDeItem,
        EnderecoDeRetirada,
        OcorrenciaDeEntrega,
        RecebimentoDoFornecedor,
        RetiradaDeItem,
    )

    modelos = (
        OcorrenciaDeEntrega,
        RecebimentoDoFornecedor,
        RetiradaDeItem,
        DescarteDeItem,
        Reembolso,
        EnderecoDeRetirada,
    )
    return tuple(m.objects.count() for m in modelos)


@pytest.mark.parametrize("estado", ["ae", "liberada"])
def test_o_comprador_nao_alcanca_escrita_da_e14(
    relogio: RelogioControlado, sim: Any, estado: str
) -> None:  # A-11
    construir = arranjo_ae if estado == "ae" else ae_liberada
    a, x, _y, _pf = construir(relogio, sim)
    cliente = _como(a.a)
    campos = {
        "item": item_de(x, a.p1).pk,
        "produto": a.p1.pk,
        "tipo": "faltante",
        "quantidade": "1",
        "acionamento": str(uuid.uuid4()),
        "texto": "Rua Falsa, 1",
    }
    antes = _total_de_registros()
    for rota in ROTAS_DA_E14:
        resposta = cliente.post(f"/administracao/rodadas/{a.rodada.pk}/{rota}/", campos)
        assert resposta.status_code == 403
    assert cliente.post("/administracao/retirada/endereco/", campos).status_code == 403
    assert _total_de_registros() == antes


def test_as_rotas_do_comprador_nao_criam_ocorrencia(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    from apps.pedidos.models import ItemDoPedido, Pedido

    a, x, _y, _pf = arranjo_ae(relogio, sim)
    cliente = _como(a.a)
    campos = {"item": item_de(x, a.p1).pk, "tipo": "faltante", "quantidade": "2"}
    antes = (list(Pedido.objects.values()), list(ItemDoPedido.objects.values()))
    registros = _total_de_registros()
    detalhe = cliente.post(f"/pedidos/{x.pk}/", campos)
    pagar = cliente.post(f"/pedidos/{x.pk}/pagar/", campos)
    assert detalhe.status_code == 405
    assert pagar.status_code in (302, 409)
    assert _total_de_registros() == registros
    assert (list(Pedido.objects.values()), list(ItemDoPedido.objects.values())) == antes


# --- E14-R02: a página do pedido depois do cancelamento da rodada (A-15 e A-16) -----------------


def _cancelar(a: Any, *, com_reembolso: bool) -> None:
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    cancelar_rodada(a.admin, a.rodada, com_reembolso=com_reembolso)


def _intacto() -> tuple[int, int]:
    from apps.financeiro.models import ObrigacaoComComprador, Reembolso
    from apps.pedidos.models import OcorrenciaDeEntrega

    return (
        OcorrenciaDeEntrega.objects.count() + Reembolso.objects.count(),
        ObrigacaoComComprador.objects.count(),
    )


def test_cancelada_sem_reembolso_sem_secao_de_ocorrencias(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-15
    a, x, _y, _pf = arranjo_ae(relogio, sim)
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    antes = _intacto()
    _cancelar(a, com_reembolso=False)
    resposta = _pagina(a.a, x)
    html = resposta.content.decode()
    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "<h2>Ocorrências de entrega</h2>" not in html
    assert "<h2>Retirada</h2>" not in html
    assert "A rodada foi cancelada pelo administrador." in texto
    assert "<h2>Estornos</h2>" in html
    assert "R$ 23,59" in texto
    assert _intacto() == antes


def test_cancelada_com_reembolso_sem_secao_de_ocorrencias(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-16
    from apps.pagamentos.chamadas import processar_chamadas

    a, x, y, _pf = arranjo_ae(relogio, sim)
    ocorrer(a.admin, item_de(x, a.p1), D("2"), "faltante")
    from apps.pedidos.models import OcorrenciaDeEntrega

    antes = list(OcorrenciaDeEntrega.objects.values_list("pk", "reembolso_id", "quantidade"))
    _cancelar(a, com_reembolso=True)
    processar_chamadas()
    assert (
        list(OcorrenciaDeEntrega.objects.values_list("pk", "reembolso_id", "quantidade")) == antes
    )
    resposta = _pagina(a.a, x)
    html = resposta.content.decode()
    texto = _texto(resposta)
    assert "<h2>Ocorrências de entrega</h2>" not in html
    assert "<h2>Estornos</h2>" in html
    assert "R$ 23,59" in texto
    assert "R$ 70,76" in texto
    resposta_y = _pagina(a.b, y)
    assert "<h2>Ocorrências de entrega</h2>" not in resposta_y.content.decode()
    assert "<h2>Retirada</h2>" not in resposta_y.content.decode()
