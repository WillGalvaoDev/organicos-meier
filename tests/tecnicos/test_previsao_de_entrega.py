"""E13-05: a previsão de entrega, o ajuste e o aviso (acceptance A-1 a A-12 e A-19)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from threading import Event
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied

from apps.notificacoes.models import Envio, Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.pedido_formal import arranjo_af
from tests.apoio.pedidos import pedido_de
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
EVENTO = "previsao_de_entrega_alterada"
HOJE = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)  # 09:00 em Brasília
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _ajustar(autor: Any, rodada: Any, data: Any) -> Any:
    from apps.pedidos.previsao_de_entrega import ajustar_previsao_de_entrega

    return ajustar_previsao_de_entrega(autor, rodada, data)


def _af(relogio: RelogioControlado, sim: Any, **opcoes: Any) -> tuple[Any, Any, Any, Any]:
    af = arranjo_af(relogio, sim, **opcoes)
    relogio.congelar(HOJE)
    return af


def _previsoes() -> list[Any]:
    from apps.pedidos.models import PrevisaoDeEntrega

    return list(PrevisaoDeEntrega.objects.order_by("pk"))


def _avisos() -> list[Notificacao]:
    return list(Notificacao.objects.filter(evento=EVENTO).order_by("pk"))


def _foto() -> Any:
    return (len(_previsoes()), len(_avisos()), EntradaAuditoria.objects.count())


def test_o_ajuste_grava_a_nova_previsao_e_nao_muda_o_pedido_formal(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    from apps.pedidos.models import LinhaDoPedidoFormal, PedidoFormal
    from apps.pedidos.pedido_formal import previsao_vigente

    a, _x, _y, _pedido = _af(relogio, sim)
    antes = (
        list(PedidoFormal.objects.values()),
        list(LinhaDoPedidoFormal.objects.order_by("pk").values()),
    )
    previsao = _ajustar(a.admin, a.rodada, date(2026, 11, 14))
    assert (previsao.origem, previsao.autor_id, previsao.data) == (
        "ajuste",
        a.admin.pk,
        date(2026, 11, 14),
    )
    assert previsao_vigente(a.ciclo) == previsao
    assert len(_previsoes()) == 2
    assert (
        list(PedidoFormal.objects.values()),
        list(LinhaDoPedidoFormal.objects.order_by("pk").values()),
    ) == antes


def test_os_compradores_dos_pedidos_validos_sao_avisados(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    a, x, y, _pedido = _af(relogio, sim)
    previsao = _ajustar(a.admin, a.rodada, date(2026, 11, 14))
    avisos = {n.conta_id: n for n in _avisos()}
    assert set(avisos) == {a.a.pk, a.b.pk}
    for comprador, pedido in ((a.a, x), (a.b, y)):
        aviso = avisos[comprador.pk]
        assert aviso.titulo == "Previsão de entrega alterada: F"
        assert aviso.corpo == (
            f"A previsão de entrega do seu pedido {pedido.pk} da rodada de F passou de "
            "11/11/2026 para 14/11/2026."
        )
        assert aviso.link == f"/pedidos/{pedido.pk}/"
        assert aviso.chave == f"{EVENTO}:{previsao.pk}:{comprador.pk}"
    assert Envio.objects.filter(conta=a.a, tipo=EVENTO).exists()
    assert Envio.objects.filter(conta=a.b, tipo=EVENTO).exists()


def test_so_o_pedido_valido_e_avisado(relogio: RelogioControlado, sim: Any) -> None:  # A-3
    a, _x, _y, _pedido = _af(relogio, sim, pagar_y=False)
    _ajustar(a.admin, a.rodada, date(2026, 11, 14))
    assert {n.conta_id for n in _avisos()} == {a.a.pk}


def test_suspensa_recebe_e_removida_nao(relogio: RelogioControlado, sim: Any) -> None:  # A-4
    from apps.contas.moderacao import suspender

    a, _x, _y, _pedido = _af(relogio, sim)
    suspender(a.admin, a.b)
    _ajustar(a.admin, a.rodada, date(2026, 11, 14))
    assert {n.conta_id for n in _avisos()} == {a.a.pk, a.b.pk}


def test_removida_nao_recebe(relogio: RelogioControlado, sim: Any) -> None:  # A-4
    from apps.contas.moderacao import remover

    a, _x, _y, _pedido = _af(relogio, sim)
    remover(a.admin, a.b)
    _ajustar(a.admin, a.rodada, date(2026, 11, 14))
    assert {n.conta_id for n in _avisos()} == {a.a.pk}


def test_o_aviso_nao_traz_dado_de_outro_comprador(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    a, x, y, _pedido = _af(relogio, sim)
    _ajustar(a.admin, a.rodada, date(2026, 11, 14))
    avisos = {n.conta_id: n for n in _avisos()}
    corpo_a, corpo_b = avisos[a.a.pk].corpo, avisos[a.b.pk].corpo
    assert a.b.nome not in corpo_a
    assert a.b.email_normalizado not in corpo_a
    assert str(y.pk) not in corpo_a.replace(str(x.pk), "")
    assert a.a.nome not in corpo_b
    assert a.a.email_normalizado not in corpo_b


def test_data_passada_e_recusada(relogio: RelogioControlado, sim: Any) -> None:  # A-6
    from apps.pedidos.previsao_de_entrega import PrevisaoRecusada

    a, _x, _y, _pedido = _af(relogio, sim)
    antes = _foto()
    with pytest.raises(PrevisaoRecusada) as erro:
        _ajustar(a.admin, a.rodada, date(2026, 11, 4))
    assert erro.value.codigo == "data_passada"
    assert str(erro.value) == "A previsão não pode ser uma data passada."
    assert _foto() == antes


def test_hoje_em_brasilia_e_aceito(relogio: RelogioControlado, sim: Any) -> None:  # A-7
    a, _x, _y, _pedido = arranjo_af(relogio, sim)
    relogio.congelar(datetime(2026, 11, 5, 2, 30, tzinfo=UTC))  # 23:30 de 04/11 em Brasília
    previsao = _ajustar(a.admin, a.rodada, date(2026, 11, 4))
    assert previsao.data == date(2026, 11, 4)


def test_a_mesma_data_da_vigente_e_recusada(relogio: RelogioControlado, sim: Any) -> None:  # A-8
    from apps.pedidos.previsao_de_entrega import PrevisaoRecusada

    a, _x, _y, _pedido = _af(relogio, sim)
    antes = _foto()
    with pytest.raises(PrevisaoRecusada) as erro:
        _ajustar(a.admin, a.rodada, date(2026, 11, 11))
    assert erro.value.codigo == "sem_alteracao"
    assert str(erro.value) == "A data informada já é a previsão vigente."
    assert _foto() == antes


def test_fora_de_aguardando_fornecedor_e_recusado(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    from apps.pedidos.previsao_de_entrega import PrevisaoRecusada

    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    a, _x, _y, _pedido = _af(relogio, sim)
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    antes = _foto()
    with pytest.raises(PrevisaoRecusada) as erro:
        _ajustar(a.admin, a.rodada, date(2026, 11, 14))
    assert erro.value.codigo == "fora_de_aguardando_fornecedor"
    assert str(erro.value) == (
        "A previsão só pode ser ajustada com a rodada aguardando o fornecedor."
    )
    assert _foto() == antes


def test_rodada_em_pagamento_e_recusada(relogio: RelogioControlado) -> None:  # A-9
    from apps.pedidos.previsao_de_entrega import PrevisaoRecusada

    from tests.apoio.apuracao import arranjo_ap

    a, _x, _y = arranjo_ap(relogio)
    with pytest.raises(PrevisaoRecusada) as erro:
        _ajustar(a.admin, a.rodada, date(2026, 11, 14))
    assert erro.value.codigo == "fora_de_aguardando_fornecedor"
    assert not _previsoes()


@pytest.mark.parametrize("valor", [datetime(2026, 11, 14, 10, 0, tzinfo=UTC), "2026-11-14"])
def test_so_aceita_date(relogio: RelogioControlado, sim: Any, valor: Any) -> None:  # A-10
    from apps.pedidos.previsao_de_entrega import PrevisaoRecusada

    a, _x, _y, _pedido = _af(relogio, sim)
    antes = _foto()
    with pytest.raises(PrevisaoRecusada) as erro:
        _ajustar(a.admin, a.rodada, valor)
    assert erro.value.codigo == "data_invalida"
    assert _foto() == antes


def test_so_o_administrador_ajusta(relogio: RelogioControlado, sim: Any) -> None:  # A-11
    from tests.fabricas import ContaFactory

    a, _x, _y, _pedido = _af(relogio, sim)
    fornecedor = ContaFactory.create(
        nome="Conta de F", papel="fornecedor", fornecedor_id=a.fornecedor.pk
    )
    antes = _foto()
    for autor in (a.a, fornecedor, None):
        with pytest.raises(PermissionDenied):
            _ajustar(autor, a.rodada, date(2026, 11, 14))
    assert _foto() == antes


def test_a_auditoria_do_ajuste(relogio: RelogioControlado, sim: Any) -> None:  # A-12
    a, _x, _y, _pedido = _af(relogio, sim)
    _ajustar(a.admin, a.rodada, date(2026, 11, 14))
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.previsao_de_entrega")
    assert auditoria.autor_id == str(a.admin.pk)
    dados = auditoria.alteracoes
    assert (dados["rodada"], dados["ciclo"]) == (a.rodada.pk, a.ciclo.pk)
    assert (dados["anterior"], dados["nova"]) == ("2026-11-11", "2026-11-14")
    assert dados["compradores_avisados"] == 2
    assert pedido_de(a.a).pk


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_dois_ajustes_iguais_em_paralelo_gravam_um(
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-19
    from apps.pedidos import previsao_de_entrega as modulo
    from tests.apoio.concorrencia import executar_em_paralelo
    from tests.apoio.trava import esperar_outra_conexao_na_trava

    a, _x, _y, _pedido = _af(relogio, simulador_pagamentos)
    pausado = Event()
    original = modulo._avisar_os_compradores

    def pausar(*args: Any, **kwargs: Any) -> Any:
        resultado = original(*args, **kwargs)
        pausado.set()
        esperar_outra_conexao_na_trava()  # o segundo ajuste, parado na trava da rodada
        return resultado

    monkeypatch.setattr(modulo, "_avisar_os_compradores", pausar)

    def primeiro(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        return modulo.ajustar_previsao_de_entrega(a.admin, a.rodada, date(2026, 11, 14))

    def segundo(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        assert pausado.wait(15)
        return modulo.ajustar_previsao_de_entrega(a.admin, a.rodada, date(2026, 11, 14))

    resultados = executar_em_paralelo(primeiro, segundo, tempo_limite=60)
    assert resultados[0].excecao is None, repr(resultados[0].excecao)
    assert isinstance(resultados[1].excecao, modulo.PrevisaoRecusada)
    assert resultados[1].excecao.codigo == "sem_alteracao"
    assert len([p for p in _previsoes() if p.origem == "ajuste"]) == 1
    assert len(_avisos()) == 2
