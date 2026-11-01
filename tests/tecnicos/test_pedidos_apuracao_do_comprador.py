"""E11-07: o que o comprador vê da apuração (acceptance A-13 a A-16)."""

import re
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _texto(resposta: Any) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", resposta.content.decode()).split())


def _como(conta: Any) -> Client:
    cliente = Client()
    cliente.force_login(conta)
    return cliente


def _apurada(relogio: RelogioControlado, sim: Any, **arranjo: Any) -> tuple[Any, Any, Any]:
    from apps.pedidos.apuracao import iniciar_apuracao

    a, x, y = arranjo_ap(relogio, **arranjo)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    return a, x, y


def test_pedido_cancelado_por_falta_de_pagamento(relogio: RelogioControlado, sim: Any) -> None:
    # A-13
    a, _x, y = _apurada(relogio, sim)
    resposta = _como(a.b).get(f"/pedidos/{y.pk}/")
    texto = _texto(resposta)
    assert "Cancelado por falta de pagamento" in texto
    assert "Nada foi cobrado neste pedido" in texto
    assert "O pagamento não foi identificado até o fim do prazo" in texto


def test_unidades_em_caixa_incompleta_com_o_estorno_e_a_fila(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-14
    a, x, _y = _apurada(relogio, sim)
    cliente = _como(a.a)
    texto = _texto(cliente.get(f"/pedidos/{x.pk}/"))
    assert "4 un em caixa que ficou incompleta" in texto
    assert "estorno proporcional e unidades na fila de pendentes do fornecedor" in texto
    assert "R$ 23,59" in texto
    assert "Caixa incompleta" in texto
    carrinho = _texto(cliente.get("/carrinho/"))
    assert "Pendente: 4" in carrinho


def test_pedido_pago_de_rodada_que_voltou_para_interesse(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-15
    a, x, _y = _apurada(relogio, sim, minimo="100.00")
    texto = _texto(_como(a.a).get(f"/pedidos/{x.pk}/"))
    assert "A rodada voltou para interesse. O valor pago será devolvido integralmente" in texto
    assert "seus interesses continuam reservados na rodada" in texto


def test_o_comprador_nao_ve_dados_de_outro_nem_o_minimo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-16
    a, x, y = _apurada(relogio, sim)
    cliente = _como(a.a)
    texto = _texto(cliente.get(f"/pedidos/{x.pk}/"))
    assert "Comprador B" not in texto
    assert "50,00" not in texto
    assert cliente.get(f"/pedidos/{y.pk}/").status_code == 404


# --- E11-R01 e E11-R02: o texto segue o registro da apuração -----------------------------------


def _r_viavel(relogio: RelogioControlado, sim: Any, *, suspenso: bool) -> tuple[Any, Any]:
    """O arranjo R: A paga, remove a sobra pendente e (ou não) é suspenso; apuração viável."""
    from apps.contas.moderacao import suspender
    from apps.interesses.servicos import remover_pendente
    from apps.pedidos.apuracao import iniciar_apuracao
    from tests.apoio.apuracao import arranjo_r

    a, x, _y = arranjo_r(relogio)
    pagar(relogio, sim, x)
    remover_pendente(a.a, a.p2, D("2"))
    if suspenso:
        suspender(a.admin, a.a)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    return a, x


def test_retorno_com_a_conta_suspensa_nao_promete_interesses_reservados(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-18 (R02)
    from apps.contas.moderacao import suspender
    from apps.pedidos.apuracao import iniciar_apuracao

    a, x, _y = arranjo_ap(relogio, minimo="100.00")
    pagar(relogio, sim, x)
    suspender(a.admin, a.a)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    texto = _texto(_como(a.a).get(f"/pedidos/{x.pk}/"))
    assert "A rodada voltou para interesse. O valor pago será devolvido integralmente." in texto
    assert "seus interesses continuam reservados" not in texto


def test_retorno_com_a_sobra_removida_mantem_o_texto_e_a_reserva_no_carrinho(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-19 (R01)
    from apps.interesses.servicos import remover_pendente
    from apps.pedidos.apuracao import iniciar_apuracao

    a, x, _y = arranjo_ap(relogio, minimo="100.00", pendente_a_p1=2, limites=(11, 12))
    pagar(relogio, sim, x)
    remover_pendente(a.a, a.p1, D("2"))
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    cliente = _como(a.a)
    assert "seus interesses continuam reservados" in _texto(cliente.get(f"/pedidos/{x.pk}/"))
    carrinho = _texto(cliente.get("/carrinho/"))
    assert "Reservado: 6" in carrinho
    assert "Pendente: 0" in carrinho


def test_caixa_incompleta_com_a_sobra_removida_menciona_a_fila(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-20 (R01)
    from apps.notificacoes.models import Notificacao

    a, x = _r_viavel(relogio, sim, suspenso=False)
    cliente = _como(a.a)
    texto = _texto(cliente.get(f"/pedidos/{x.pk}/"))
    assert "4 un em caixa que ficou incompleta" in texto
    assert "unidades na fila de pendentes do fornecedor" in texto
    assert "Pendente: 4" in _texto(cliente.get("/carrinho/"))
    aviso = Notificacao.objects.get(conta=a.a, chave__startswith="itens_cancelados:caixa:")
    assert "fila de pendentes" in aviso.corpo


def test_caixa_incompleta_sem_restauracao_nao_promete_a_fila(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-21 (E11-04 regra 4)
    from apps.notificacoes.models import Notificacao

    a, x = _r_viavel(relogio, sim, suspenso=True)
    texto = _texto(_como(a.a).get(f"/pedidos/{x.pk}/"))
    assert "4 un em caixa que ficou incompleta: estorno proporcional" in texto
    assert "fila de pendentes" not in texto
    aviso = Notificacao.objects.get(conta=a.a, chave__startswith="itens_cancelados:caixa:")
    assert "estorno" in aviso.corpo
    assert "fila de pendentes" not in aviso.corpo


# --- E11-R02 residual: a tela segue `retorno.contas_impedidas` ------------------------------------


def _rr(relogio: RelogioControlado, sim: Any, *, impedir: str | None) -> tuple[Any, Any]:
    """O arranjo RR da E11-05: a única parcela de A, `pendente`, com 6 pagas no pedido X."""
    from apps.contas.moderacao import remover, suspender
    from apps.pedidos.apuracao import iniciar_apuracao

    a, x, _y = arranjo_ap(
        relogio,
        minimo="100.00",
        pendente_a_p1=2,
        parcelas_de_p1=(("a", 6), ("b", 5)),
        parcelas_de_p2=(("b", 12),),
    )
    pagar(relogio, sim, x)
    if impedir == "suspensa":
        suspender(a.admin, a.a)
    elif impedir == "removida":
        remover(a.admin, a.a)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    return a, x


def _efeito(x: Any) -> dict[str, Any]:
    from apps.pedidos.apuracao_tela import efeitos_da_apuracao_no_pedido
    from apps.pedidos.models import Pedido

    return efeitos_da_apuracao_no_pedido(Pedido.objects.get(pk=x.pk))


def _sem_promessa(a: Any, x: Any) -> None:
    texto = _texto(_como(a.a).get(f"/pedidos/{x.pk}/"))
    assert "A rodada voltou para interesse. O valor pago será devolvido integralmente." in texto
    assert "continuam reservados" not in texto


def test_conta_suspensa_com_a_parcela_ja_removida_nao_promete_reservas(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-22
    a, x = _rr(relogio, sim, impedir="suspensa")
    assert _efeito(x)["interesses_reservados"] is False
    _sem_promessa(a, x)


def test_conta_removida_com_a_parcela_ja_removida_nao_promete_reservas(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-23
    _a, x = _rr(relogio, sim, impedir="removida")
    assert _efeito(x)["interesses_reservados"] is False


def test_reativar_depois_da_apuracao_nao_faz_a_tela_prometer_reservas(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-24
    from apps.contas.moderacao import reativar

    a, x = _rr(relogio, sim, impedir="suspensa")
    reativar(a.admin, a.a)
    assert _efeito(x)["interesses_reservados"] is False
    _sem_promessa(a, x)


def test_suspender_depois_da_apuracao_nao_muda_o_que_a_tela_diz(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-25
    from apps.contas.moderacao import suspender

    a, x = _rr(relogio, sim, impedir=None)
    suspender(a.admin, a.a)
    assert _efeito(x)["interesses_reservados"] is True
