"""T-7 com as duas ordens forçadas sob concorrência (E16-07 regra 2-J).

A operação A obtém a trava do pagamento e pausa dentro da sincronização, ainda na transação; a
operação B começa e fica comprovadamente esperando por essa trava (`corrida.b_esperou`) antes de A
confirmar. Cada teste roda as duas ordens (quem é A e quem é B) e confere o mesmo resultado final de
pagamento, destino e situação do pedido, dentro do grupo de equivalência da regra 2-J: o mesmo
pedido, o mesmo pagamento, o mesmo horário de aprovação e a mesma informação no provedor.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from apps.financeiro.models import AlertaFinanceiro, ObrigacaoComComprador
from apps.notificacoes.models import Notificacao
from apps.pagamentos import chamadas, consulta
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.models import PagamentoNoProvedor
from apps.pedidos import apuracao, operacoes
from apps.pedidos.models import ApuracaoFinal, DestinoDoPagamento, Pedido, SituacaoDoPedido
from apps.pedidos.tarefas import bloquear_tentativas_vencidas_agora
from tests.apoio.apuracao import H, arranjo_ap, cobranca, pagar
from tests.apoio.corrida import Corrida
from tests.apoio.pedidos import T0, pedido_aberto, tentativa_criada
from tests.conftest import RelogioControlado

pytestmark = [
    pytest.mark.concorrencia,
    pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"]),
]

D = Decimal
PRAZO = T0 + 48 * H
ORDENS = ["aviso_primeiro", "outra_primeiro"]
ORDENS_DO_BLOQUEIO_E_DA_APURACAO = ["bloqueio_primeiro", "apuracao_primeiro"]


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _pausar_na_sincronizacao_de(
    corrida: Corrida, monkeypatch: pytest.MonkeyPatch, referencia: str
) -> None:
    """A pausa só depois de sincronizar o pagamento da `referencia`, ainda na transação, com a
    trava do pagamento: a primeira vez, e só na operação A. Cobre os três pontos em que o código
    sincroniza (aviso e consulta pela tarefa, cancelamento e consulta antes de decidir)."""
    for modulo in (chamadas, consulta, operacoes):
        original = modulo.sincronizar_pagamento

        def com_pausa(consultado: Any, *args: Any, _original: Any = original, **kwargs: Any) -> Any:
            resultado = _original(consultado, *args, **kwargs)
            if consultado.referencia_externa == referencia:
                corrida.pausar_a()
            return resultado

        monkeypatch.setattr(modulo, "sincronizar_pagamento", com_pausa)


def _receber_o_aviso(sim: Any) -> None:
    sim.entregar_avisos()
    processar_chamadas()


def _bloquear_e_processar() -> None:
    bloquear_tentativas_vencidas_agora()
    processar_chamadas()


def _rodar_nas_duas_ordens(corrida: Corrida, ordem: str, aviso: Any, outra: Any) -> tuple[Any, Any]:
    """A primeira operação da ordem é A (pausa com a trava); a outra é B e espera."""
    primeira, segunda = (aviso, outra) if ordem == "aviso_primeiro" else (outra, aviso)
    return corrida.rodar(primeira, segunda, a_atomica=False, b_atomica=False)


# --- webhook e bloqueio de T0 + 24h --------------------------------------------------------------


def _aprovada_as_23h59(relogio: RelogioControlado, sim: Any) -> tuple[Any, Pedido, str]:
    arranjo, x = pedido_aberto(relogio)
    p = tentativa_criada(x).id_externo
    assert p is not None
    relogio.congelar(T0 + timedelta(hours=23, minutes=59))
    sim.aprovar(p)
    relogio.congelar(T0 + timedelta(hours=24))
    return arranjo, x, p


@pytest.mark.parametrize("ordem", ORDENS)
def test_aviso_aprovado_antes_de_24h_e_bloqueio_quitam_uma_vez_nas_duas_ordens(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch, ordem: str
) -> None:  # T-7, grupo: aprovado em T0 + 23h59, o mesmo pagamento nas duas ordens
    arranjo, x, _ = _aprovada_as_23h59(relogio, sim)
    corrida = Corrida()
    _pausar_na_sincronizacao_de(corrida, monkeypatch, x.referencia_externa)
    ra, rb = _rodar_nas_duas_ordens(
        corrida, ordem, lambda: _receber_o_aviso(sim), _bloquear_e_processar
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    processar_chamadas()  # o que a corrida deixou pendente, na próxima execução da tarefa
    situacao = SituacaoDoPedido.objects.get(pedido=x)
    assert (situacao.situacao, situacao.quitado_em) == (
        "pago",
        T0 + timedelta(hours=23, minutes=59),
    )
    assert DestinoDoPagamento.objects.filter(pedido=x, destino="quita").count() == 1
    assert DestinoDoPagamento.objects.exclude(destino="quita").count() == 0
    assert Notificacao.objects.filter(conta=arranjo.a, evento="pagamento_confirmado").count() == 1


@pytest.mark.parametrize("ordem", ORDENS)
def test_aviso_sem_aprovacao_e_bloqueio_cancelam_a_cobranca_nas_duas_ordens(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch, ordem: str
) -> None:  # T-7, grupo: cobrança pendente, aviso de outra mudança, nenhuma aprovação
    _, x = pedido_aberto(relogio)
    p = tentativa_criada(x).id_externo
    assert p is not None
    sim.reemitir_aviso(p)
    relogio.congelar(T0 + timedelta(hours=24))
    corrida = Corrida()
    _pausar_na_sincronizacao_de(corrida, monkeypatch, x.referencia_externa)
    ra, rb = _rodar_nas_duas_ordens(
        corrida, ordem, lambda: _receber_o_aviso(sim), _bloquear_e_processar
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    processar_chamadas()
    assert PagamentoNoProvedor.objects.get(id_externo=p).situacao == "cancelado"
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "aguardando_pagamento"
    assert DestinoDoPagamento.objects.count() == 0


# --- webhook e apuração (E11-01 A-15: aprovação identificável na reconsulta) --------------------


def _y_aprovado_em_47h_sem_aviso(
    relogio: RelogioControlado, sim: Any
) -> tuple[Any, Pedido, Pedido]:
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    pagar(relogio, sim, y, quando=T0 + 47 * H, entregar=False)
    relogio.congelar(PRAZO)
    return a, x, y


@pytest.mark.parametrize("ordem", ORDENS)
def test_aviso_e_apuracao_com_a_aprovacao_identificavel_quitam_y_nas_duas_ordens(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch, ordem: str
) -> None:  # T-7, E11-01 A-15: Y aprovado em T0 + 47h, a reconsulta vê a aprovação
    a, _x, y = _y_aprovado_em_47h_sem_aviso(relogio, sim)
    corrida = Corrida()
    _pausar_na_sincronizacao_de(corrida, monkeypatch, y.referencia_externa)
    ra, rb = _rodar_nas_duas_ordens(
        corrida,
        ordem,
        lambda: _receber_o_aviso(sim),
        lambda: apuracao.iniciar_apuracao(a.admin, a.rodada),
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    situacao = SituacaoDoPedido.objects.get(pedido=y)
    assert (situacao.situacao, situacao.motivo_do_cancelamento) == ("pago", "")
    assert ApuracaoFinal.objects.get().pedidos_pagos == 2
    assert list(DestinoDoPagamento.objects.filter(pedido=y).values_list("destino", "motivo")) == [
        ("quita", "")
    ]
    assert not ObrigacaoComComprador.objects.filter(pedido=y).exists()
    assert not AlertaFinanceiro.objects.filter(tipo="aprovado_no_prazo_depois_da_apuracao").exists()


# --- bloqueio e apuração (os dois atuam em T0 + 48h, com a rodada em pagamento) -----------------


@pytest.mark.parametrize("ordem", ORDENS_DO_BLOQUEIO_E_DA_APURACAO)
def test_bloqueio_e_apuracao_cancelam_a_cobranca_de_y_nas_duas_ordens(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch, ordem: str
) -> None:  # T-7: Y sem pagar, cobrança pendente; o bloqueio e a apuração cancelam
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    relogio.congelar(PRAZO)
    corrida = Corrida()
    _pausar_na_sincronizacao_de(corrida, monkeypatch, y.referencia_externa)
    primeira, segunda = (
        (_bloquear_e_processar, lambda: apuracao.iniciar_apuracao(a.admin, a.rodada))
        if ordem == "bloqueio_primeiro"
        else (lambda: apuracao.iniciar_apuracao(a.admin, a.rodada), _bloquear_e_processar)
    )
    ra, rb = corrida.rodar(primeira, segunda, a_atomica=False, b_atomica=False)
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    processar_chamadas()
    cancelado = SituacaoDoPedido.objects.get(pedido=y)
    assert (cancelado.situacao, cancelado.motivo_do_cancelamento) == ("cancelado", "inadimplencia")
    assert PagamentoNoProvedor.objects.get(id_externo=id_y).situacao == "cancelado"
    assert ApuracaoFinal.objects.get().pedidos_pagos == 1
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "pago"
