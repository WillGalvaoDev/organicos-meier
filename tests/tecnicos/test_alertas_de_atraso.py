"""E15-03: os alertas de atraso de processamento (acceptance A-1 a A-16)."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from django.urls import reverse

from tests.apoio.operacao import (
    INSTANTE,
    MIN,
    Ao,
    alertas,
    arranjo_ao,
    concluir_todas,
    notificacoes,
    verificar,
)
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

SEGUNDO = timedelta(seconds=1)


@pytest.fixture
def ao(relogio: RelogioControlado) -> Ao:
    return arranjo_ao(relogio)


def _verificar(relogio: RelogioControlado, instante: datetime) -> tuple[int, int]:
    """Todas as tarefas em dia no instante, para só os alertas de domínio aparecerem."""
    concluir_todas(instante)
    return verificar(relogio, instante)


def _abertos(tipo: str) -> list[Any]:
    return alertas(tipo, abertos=True)


def _rodada_em_fechamento(prazo: datetime, nome: str = "Fazenda G") -> Any:
    from tests.apoio.ciclos import dar_prazo_de_teste
    from tests.fabricas import FornecedorFactory, RodadaFactory

    rodada = RodadaFactory.create(
        fornecedor=FornecedorFactory.create(nome=nome), etapa="fechamento"
    )
    dar_prazo_de_teste(rodada, prazo)
    return rodada


# --- fechamento ---------------------------------------------------------------------------------


def test_fechamento_nao_encerrado(relogio: RelogioControlado, ao: Ao) -> None:  # A-1
    rodada = _rodada_em_fechamento(INSTANTE)
    assert _verificar(relogio, INSTANTE + 5 * MIN) == (0, 0)
    assert _abertos("fechamento_nao_encerrado") == []
    assert _verificar(relogio, INSTANTE + 5 * MIN + SEGUNDO) == (1, 0)
    (alerta,) = _abertos("fechamento_nao_encerrado")
    assert alerta.chave == f"rodada:{rodada.pk}"
    assert alerta.gravidade == "aviso"
    assert alerta.dados == {
        "rodada": rodada.pk,
        "fornecedor": "Fazenda G",
        "prazo": INSTANTE.isoformat(),
    }
    (notificacao,) = notificacoes(ao.adm1)
    assert notificacao.titulo == "Fechamento não encerrado"
    assert notificacao.corpo == (
        "O fechamento da rodada de Fazenda G terminou em 20/11/2026 09:00 e ainda não foi "
        "encerrado."
    )
    assert notificacao.link == reverse("rodadas_estoque", args=[rodada.pk])


def test_o_encerramento_resolve_o_alerta(relogio: RelogioControlado, ao: Ao) -> None:  # A-2
    from apps.rodadas.fechamento import encerrar_fechamentos_vencidos

    _rodada_em_fechamento(INSTANTE)
    _verificar(relogio, INSTANTE + 6 * MIN)
    assert len(_abertos("fechamento_nao_encerrado")) == 1
    assert encerrar_fechamentos_vencidos() == 1
    assert _verificar(relogio, INSTANTE + 6 * MIN) == (0, 1)
    assert _abertos("fechamento_nao_encerrado") == []


def test_fechamento_prorrogado_nao_acusa(relogio: RelogioControlado, ao: Ao) -> None:  # A-3
    _rodada_em_fechamento(INSTANTE + 60 * MIN)
    assert _verificar(relogio, INSTANTE + 10 * MIN) == (0, 0)
    assert alertas("fechamento_nao_encerrado") == []


# --- pedido formal ------------------------------------------------------------------------------


def _af(relogio: RelogioControlado, sim: Any) -> tuple[Any, Any]:
    from apps.pedidos.models import EnvioDoPedidoFormal
    from tests.apoio.pedido_formal import arranjo_af

    a, _x, _y, pedido_formal = arranjo_af(relogio, sim)
    return a, EnvioDoPedidoFormal.objects.get(pedido_formal=pedido_formal)


def test_pedido_formal_atrasado(relogio: RelogioControlado, simulador_pagamentos: Any) -> None:
    # A-4
    a, envio = _af(relogio, simulador_pagamentos)
    assert envio.situacao == "em_andamento"
    prevista = envio.proxima_tentativa_em
    _verificar(relogio, prevista + 6 * MIN)
    (alerta,) = _abertos("pedido_formal_atrasado")
    assert alerta.chave == f"pedido_formal:{envio.pedido_formal_id}"
    assert alerta.dados["pedido_formal"] == envio.pedido_formal_id
    assert alerta.dados["rodada"] == a.rodada.pk
    assert alerta.dados["prevista_para"] == prevista.isoformat()
    (notificacao,) = [
        n for n in notificacoes(a.admin) if n.titulo == "Envio do pedido formal atrasado"
    ]
    assert "estava prevista para" in notificacao.corpo
    assert notificacao.link == reverse("rodadas_pedido_formal", args=[a.rodada.pk])


def test_o_envio_concluido_resolve_o_alerta(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # A-5
    from tests.apoio.pedido_formal import processar

    _a, envio = _af(relogio, simulador_pagamentos)
    instante = envio.proxima_tentativa_em + 6 * MIN
    _verificar(relogio, instante)
    assert len(_abertos("pedido_formal_atrasado")) == 1
    processar(relogio, instante)
    assert _verificar(relogio, instante) == (0, 1)
    assert _abertos("pedido_formal_atrasado") == []


def test_pedido_formal_ja_encerrado_nao_acusa(
    relogio: RelogioControlado, simulador_pagamentos: Any, settings: Any
) -> None:  # A-6
    from apps.pedidos.models import EnvioDoPedidoFormal
    from tests.apoio.pedido_formal import af_falhas

    _a, _x, _y, pedido_formal = af_falhas(relogio, simulador_pagamentos, settings)
    envio = EnvioDoPedidoFormal.objects.get(pedido_formal=pedido_formal)
    assert envio.situacao == "concluido_com_falhas"
    _verificar(relogio, envio.concluido_em + 10 * MIN)
    EnvioDoPedidoFormal.objects.filter(pk=envio.pk).update(
        situacao="interrompido", motivo_da_interrupcao="rodada_cancelada"
    )
    _verificar(relogio, envio.concluido_em + 20 * MIN)
    assert alertas("pedido_formal_atrasado") == []


# --- conciliação --------------------------------------------------------------------------------


def _conciliar(dia: date) -> None:
    from apps.financeiro.models import ConciliacaoDiaria

    ConciliacaoDiaria.objects.create(data=dia, resultado="ok")


def test_conciliacao_atrasada(relogio: RelogioControlado, ao: Ao) -> None:  # A-7
    _conciliar(date(2026, 11, 17))
    limite = datetime(2026, 11, 20, 3, 0, tzinfo=UTC)
    assert _verificar(relogio, limite) == (0, 0)
    assert _verificar(relogio, limite + SEGUNDO) == (1, 0)
    (alerta,) = _abertos("conciliacao_atrasada")
    assert alerta.chave == "dia:2026-11-18"
    assert alerta.dados == {"dia": "2026-11-18", "ultima_conciliada": "2026-11-17"}
    (notificacao,) = notificacoes(ao.adm1)
    assert notificacao.titulo == "Conciliação atrasada"
    assert notificacao.corpo == (
        "O dia 18/11/2026 terminou há mais de 24 horas e ainda não foi conciliado. "
        "A última conciliação é de 17/11/2026."
    )
    assert notificacao.link == reverse("financeiro_conciliacoes")


def test_a_chave_troca_quando_a_conciliacao_avanca(
    relogio: RelogioControlado, ao: Ao
) -> None:  # A-8
    _conciliar(date(2026, 11, 17))
    _verificar(relogio, datetime(2026, 11, 20, 3, 0, 1, tzinfo=UTC))
    _conciliar(date(2026, 11, 18))
    _verificar(relogio, datetime(2026, 11, 21, 3, 0, 1, tzinfo=UTC))
    assert [a.chave for a in _abertos("conciliacao_atrasada")] == ["dia:2026-11-19"]
    assert [a.chave for a in alertas("conciliacao_atrasada")] == [
        "dia:2026-11-18",
        "dia:2026-11-19",
    ]


def test_sem_nenhuma_conciliacao_nao_acusa(relogio: RelogioControlado, ao: Ao) -> None:  # A-9
    _verificar(relogio, INSTANTE + timedelta(days=60))
    assert alertas("conciliacao_atrasada") == []


# --- chamadas ao provedor -----------------------------------------------------------------------


def _chamada(alvo: str, **campos: Any) -> Any:
    from apps.pagamentos.models import ChamadaAoProvedor

    padrao: dict[str, Any] = {
        "operacao": "cancelar_cobranca",
        "alvo": alvo,
        "chave_idempotencia": f"k-{alvo}",
        "provedor": "simulador",
        "ambiente": "teste",
        "situacao": "pendente",
    }
    return ChamadaAoProvedor.objects.create(**{**padrao, **campos})


def test_chamadas_atrasadas(relogio: RelogioControlado, ao: Ao) -> None:  # A-10
    _chamada("a1", proxima_em=INSTANTE, criada_em=INSTANTE - 60 * MIN)
    antiga = INSTANTE - timedelta(hours=25, seconds=1)
    _chamada("a2", proxima_em=INSTANTE + timedelta(days=1), criada_em=antiga)
    _verificar(relogio, INSTANTE + 5 * MIN + SEGUNDO)
    (alerta,) = _abertos("chamadas_ao_provedor_atrasadas")
    assert alerta.chave == "geral"
    assert alerta.dados == {"quantidade": 2, "mais_antiga": antiga.isoformat()}
    (notificacao,) = notificacoes(ao.adm1)
    assert notificacao.titulo == "Chamadas ao provedor atrasadas"
    assert notificacao.corpo.startswith("2 chamada(s) ao provedor de pagamentos estão pendentes")
    assert notificacao.link == reverse("painel_administracao")


def test_chamadas_concluidas_resolvem_o_alerta(relogio: RelogioControlado, ao: Ao) -> None:  # A-11
    from apps.pagamentos.models import ChamadaAoProvedor

    _chamada("a1", proxima_em=INSTANTE, criada_em=INSTANTE - 60 * MIN)
    _chamada("a2", proxima_em=INSTANTE, criada_em=INSTANTE - 60 * MIN)
    _verificar(relogio, INSTANTE + 6 * MIN)
    ChamadaAoProvedor.objects.update(situacao="concluida", concluida_em=INSTANTE + 6 * MIN)
    assert _verificar(relogio, INSTANTE + 6 * MIN) == (0, 1)


def test_chamada_futura_nao_acusa(relogio: RelogioControlado, ao: Ao) -> None:  # A-12
    _chamada("a1", proxima_em=INSTANTE + MIN, criada_em=INSTANTE - 120 * MIN)
    assert _verificar(relogio, INSTANTE) == (0, 0)
    assert alertas("chamadas_ao_provedor_atrasadas") == []


# --- envios -------------------------------------------------------------------------------------


def _envio(n: int, proxima: datetime) -> Any:
    from tests.fabricas import EnvioFactory

    envio = EnvioFactory.create(proxima_tentativa_em=proxima)
    return envio


def test_envios_atrasados(relogio: RelogioControlado, ao: Ao) -> None:  # A-13
    _envio(1, INSTANTE)
    _envio(2, INSTANTE + MIN)
    _verificar(relogio, INSTANTE + 6 * MIN + SEGUNDO)
    (alerta,) = _abertos("envios_atrasados")
    assert alerta.chave == "geral"
    assert alerta.dados == {"quantidade": 2, "mais_antigo": INSTANTE.isoformat()}
    (notificacao,) = notificacoes(ao.adm1)
    assert notificacao.titulo == "Notificações atrasadas"
    assert notificacao.corpo == (
        "2 notificação(ões) aguardam envio além do previsto, desde 20/11/2026 09:00."
    )
    assert notificacao.link == reverse("envios_lista")


def test_os_dados_do_alerta_geral_ficam_congelados(relogio: RelogioControlado, ao: Ao) -> None:
    # A-14
    _envio(1, INSTANTE)
    _envio(2, INSTANTE + MIN)
    _verificar(relogio, INSTANTE + 7 * MIN)
    _envio(3, INSTANTE + 2 * MIN)
    assert _verificar(relogio, INSTANTE + 8 * MIN) == (0, 0)
    (alerta,) = _abertos("envios_atrasados")
    assert alerta.dados["quantidade"] == 2
    assert len(notificacoes(ao.adm1)) == 1


# --- invariantes --------------------------------------------------------------------------------


def _foto() -> tuple[Any, ...]:
    """As linhas de domínio já existentes, sem os e-mails que os próprios alertas criam."""
    from apps.financeiro.models import ConciliacaoDiaria
    from apps.notificacoes.models import Envio
    from apps.pagamentos.models import ChamadaAoProvedor
    from apps.rodadas.models import Rodada

    return tuple(
        (m.__name__, tuple(sorted(str(linha) for linha in m.objects.values())))
        for m in (Rodada, ConciliacaoDiaria, ChamadaAoProvedor, Envio)
    )


def test_as_verificacoes_so_leem(relogio: RelogioControlado, ao: Ao) -> None:  # A-15
    _rodada_em_fechamento(INSTANTE)
    _conciliar(date(2026, 11, 17))
    _chamada("a1", proxima_em=INSTANTE, criada_em=INSTANTE - 60 * MIN)
    _envio(1, INSTANTE)
    from apps.notificacoes.models import Envio

    antes = _foto()
    ultimo_envio = Envio.objects.order_by("-pk").first()
    _verificar(relogio, INSTANTE + timedelta(days=3))
    assert len(alertas()) >= 4
    depois = _foto()
    assert depois[:3] == antes[:3]
    # os envios que já existiam seguem iguais; só nascem os e-mails dos avisos
    anteriores = Envio.objects.filter(pk__lte=ultimo_envio.pk if ultimo_envio else 0)
    assert tuple(sorted(str(e) for e in anteriores.values())) == antes[3][1]


def test_nada_de_comprador_nos_alertas(relogio: RelogioControlado, ao: Ao) -> None:  # A-16
    from tests.fabricas import ContaFactory, EnvioFactory, NotificacaoFactory

    comprador = ContaFactory.create(nome="Maria Compradora", email_normalizado="maria@exemplo.com")
    EnvioFactory.create(
        notificacao=NotificacaoFactory.create(conta=comprador), proxima_tentativa_em=INSTANTE
    )
    _rodada_em_fechamento(INSTANTE)
    _conciliar(date(2026, 11, 17))
    _chamada("a1", proxima_em=INSTANTE, criada_em=INSTANTE - 60 * MIN)
    _verificar(relogio, INSTANTE + timedelta(days=3))
    assert len(alertas()) >= 4
    texto = " ".join(f"{a.dados} {a.chave}" for a in alertas())
    texto += " ".join(n.corpo + n.titulo for n in notificacoes(ao.adm1))
    assert "Maria" not in texto
    assert "maria@exemplo.com" not in texto
