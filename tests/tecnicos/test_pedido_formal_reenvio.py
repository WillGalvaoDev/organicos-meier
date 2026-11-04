"""E13-03: o reenvio manual do pedido formal (acceptance A-1 a A-17)."""

import uuid
from threading import Event
from typing import Any

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.pedido_formal import (
    EMAIL_DO_PEDIDO,
    FALHA,
    LOCMEM,
    PRAZO,
    M,
    af_falhas,
    af_meio,
    af_sucesso,
    arranjo_af,
    processar,
)
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)
EVENTO = "falha_no_pedido_formal"


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _reenviar(autor: Any, pedido: Any, token: Any = None) -> Any:
    from apps.pedidos.reenvio_do_pedido_formal import reenviar_pedido_formal

    return reenviar_pedido_formal(autor, pedido, token=token if token is not None else uuid.uuid4())


def _tentativas() -> list[Any]:
    from apps.pedidos.models import TentativaDeEnvioDoPedidoFormal

    return list(TentativaDeEnvioDoPedidoFormal.objects.order_by("numero"))


def _envio() -> Any:
    from apps.pedidos.models import EnvioDoPedidoFormal

    return EnvioDoPedidoFormal.objects.get()


def _enviados() -> list[Any]:
    return [m for m in mail.outbox if m.to == [EMAIL_DO_PEDIDO]]


def _foto_do_pedido(pedido: Any) -> Any:
    from apps.pedidos.models import LinhaDoPedidoFormal, PedidoFormal

    return (
        list(PedidoFormal.objects.order_by("pk").values()),
        list(LinhaDoPedidoFormal.objects.order_by("pk").values()),
    )


def _estado() -> Any:
    from apps.pedidos.models import EnvioDoPedidoFormal

    return (
        len(_tentativas()),
        list(EnvioDoPedidoFormal.objects.values()),
        len(_enviados()),
        EntradaAuditoria.objects.count(),
    )


def test_reenvio_depois_das_tres_falhas(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-1
    a, _x, _y, pedido = af_falhas(relogio, sim, settings)
    mail.outbox.clear()
    antes = _foto_do_pedido(pedido)
    token = uuid.uuid4()
    registrado = _reenviar(a.admin, pedido, token)
    assert registrado.nova is True
    tentativa = registrado.tentativa
    assert (tentativa.tipo, tentativa.numero, tentativa.ordem_automatica) == ("manual", 4, None)
    assert (tentativa.resultado, tentativa.autor_id) == ("sucesso", a.admin.pk)
    assert (tentativa.token, tentativa.destino) == (token, EMAIL_DO_PEDIDO)
    (enviado,) = _enviados()
    assert (enviado.subject, enviado.body) == (pedido.assunto, pedido.corpo)
    envio = _envio()
    assert (envio.situacao, envio.automaticas) == ("concluido_com_falhas", 3)
    assert envio.proxima_tentativa_em is None
    assert _foto_do_pedido(pedido) == antes


def test_reenvio_depois_do_sucesso_automatico(relogio: RelogioControlado, sim: Any) -> None:  # A-2
    a, _x, _y, pedido = af_sucesso(relogio, sim)
    registrado = _reenviar(a.admin, pedido)
    assert (registrado.tentativa.numero, registrado.tentativa.resultado) == (2, "sucesso")
    assert _envio().situacao == "concluido_com_sucesso"
    assert processar(relogio, PRAZO + 24 * 60 * M) == 0
    assert len(_tentativas()) == 2


def test_reenvio_que_falha_e_registrado_e_o_botao_continua(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-3
    from apps.pedidos.reenvio_do_pedido_formal import pode_reenviar

    a, _x, _y, pedido = af_falhas(relogio, sim, settings)
    avisos = Notificacao.objects.filter(evento=EVENTO).count()
    settings.EMAIL_BACKEND = FALHA
    registrado = _reenviar(a.admin, pedido)
    assert (registrado.tentativa.tipo, registrado.tentativa.resultado) == ("manual", "falha")
    assert registrado.tentativa.resposta == "ConnectionError"
    assert processar(relogio, PRAZO + 24 * 60 * M) == 0
    assert [t.tipo for t in _tentativas()] == ["automatica"] * 3 + ["manual"]
    assert Notificacao.objects.filter(evento=EVENTO).count() == avisos
    assert pode_reenviar(pedido)[0] is True


def test_durante_o_ciclo_automatico_o_reenvio_e_recusado(
    relogio: RelogioControlado, sim: Any, settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-4
    from apps.pedidos import reenvio_do_pedido_formal as modulo

    a, _x, _y, pedido = af_meio(relogio, sim, settings)
    consultas: list[str] = []
    monkeypatch.setattr(modulo, "consultar_antes_de_decidir", consultas.append)
    antes = _estado()
    with pytest.raises(modulo.ReenvioRecusado) as erro:
        _reenviar(a.admin, pedido)
    assert erro.value.codigo == "ciclo_em_andamento"
    assert str(erro.value) == (
        "O envio automático ainda está em andamento; o reenvio fica disponível quando ele terminar."
    )
    assert not consultas
    assert _estado() == antes


def test_antes_da_primeira_tentativa_automatica_o_reenvio_e_recusado(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    from apps.pedidos.reenvio_do_pedido_formal import ReenvioRecusado

    a, _x, _y, pedido = arranjo_af(relogio, sim)
    antes = _estado()
    with pytest.raises(ReenvioRecusado) as erro:
        _reenviar(a.admin, pedido)
    assert erro.value.codigo == "ciclo_em_andamento"
    assert _estado() == antes


def test_o_mesmo_token_gera_um_so_envio(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-6
    a, _x, _y, pedido = af_falhas(relogio, sim, settings)
    mail.outbox.clear()
    token = uuid.uuid4()
    primeira = _reenviar(a.admin, pedido, token)
    antes = _estado()
    segunda = _reenviar(a.admin, pedido, str(token))
    assert (primeira.nova, segunda.nova) == (True, False)
    assert primeira.tentativa.pk == segunda.tentativa.pk
    assert _estado() == antes
    assert len(_enviados()) == 1
    assert len([t for t in _tentativas() if t.tipo == "manual"]) == 1


def test_um_token_novo_faz_uma_tentativa_nova(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-7
    a, _x, _y, pedido = af_falhas(relogio, sim, settings)
    mail.outbox.clear()
    _reenviar(a.admin, pedido)
    segunda = _reenviar(a.admin, pedido)
    assert segunda.tentativa.numero == 5
    um, dois = _enviados()
    assert (um.subject, um.body) == (dois.subject, dois.body) == (pedido.assunto, pedido.corpo)


@pytest.mark.parametrize("token", ["abc", "", None])
def test_token_que_nao_e_uuid_e_recusado(
    relogio: RelogioControlado, sim: Any, settings: Any, token: Any
) -> None:  # A-8
    from apps.pedidos.reenvio_do_pedido_formal import ReenvioRecusado, reenviar_pedido_formal

    a, _x, _y, pedido = af_falhas(relogio, sim, settings)
    antes = _estado()
    with pytest.raises(ReenvioRecusado) as erro:
        reenviar_pedido_formal(a.admin, pedido, token=token)
    assert erro.value.codigo == "token_invalido"
    assert _estado() == antes


def test_o_token_de_outro_pedido_formal_e_recusado(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-9
    from apps.pedidos.reenvio_do_pedido_formal import ReenvioRecusado

    from apps.pedidos.models import PedidoFormal, TentativaDeEnvioDoPedidoFormal

    a, _x, _y, primeiro = af_falhas(relogio, sim, settings)
    _a2, _x2, _y2, segundo = af_falhas(relogio, sim, settings)
    assert PedidoFormal.objects.count() == 2
    token = uuid.uuid4()
    _reenviar(a.admin, primeiro, token)
    with pytest.raises(ReenvioRecusado) as erro:
        _reenviar(a.admin, segundo, token)
    assert erro.value.codigo == "token_invalido"
    assert not TentativaDeEnvioDoPedidoFormal.objects.filter(
        pedido_formal=segundo, tipo="manual"
    ).exists()


def test_rodada_cancelada_nao_permite_reenviar(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-10
    from apps.pedidos import reenvio_do_pedido_formal as modulo
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    a, _x, _y, pedido = af_sucesso(relogio, sim)
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    antes = _estado()
    with pytest.raises(modulo.ReenvioRecusado) as erro:
        _reenviar(a.admin, pedido)
    assert erro.value.codigo == "rodada_cancelada"
    assert str(erro.value) == "A rodada foi cancelada; o pedido formal não é reenviado."
    assert _estado() == antes


def test_so_o_administrador_reenvia(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-11
    from tests.fabricas import ContaFactory

    a, _x, _y, pedido = af_falhas(relogio, sim, settings)
    fornecedor = ContaFactory.create(nome="Conta de F", fornecedor=True)
    antes = _estado()
    for autor in (a.a, fornecedor, None):
        with pytest.raises(PermissionDenied):
            _reenviar(autor, pedido)
    assert _estado() == antes


def test_dentro_de_transacao_e_recusado(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-12
    a, _x, _y, pedido = af_falhas(relogio, sim, settings)
    antes = _estado()
    with pytest.raises(RuntimeError), transaction.atomic():
        _reenviar(a.admin, pedido)
    assert _estado() == antes


def test_consulta_que_falha_bloqueia_o_reenvio(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-13
    from apps.pagamentos.consulta import ConsultaAoProvedorFalhou

    a, _x, _y, pedido = af_falhas(relogio, sim, settings)
    mail.outbox.clear()
    token = uuid.uuid4()
    sim.falhar_proximas(1, operacao="buscar_por_referencia")
    antes = _estado()
    with pytest.raises(ConsultaAoProvedorFalhou):
        _reenviar(a.admin, pedido, token)
    assert _estado() == antes
    assert _reenviar(a.admin, pedido, token).nova is True
    assert len(_enviados()) == 1


def test_a_auditoria_do_reenvio(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-14
    a, _x, _y, pedido = af_falhas(relogio, sim, settings)
    token = uuid.uuid4()
    _reenviar(a.admin, pedido, token)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="pedido_formal.reenviar")
    assert auditoria.autor_id == str(a.admin.pk)
    assert auditoria.alteracoes == {
        "pedido_formal": pedido.pk,
        "numero": 4,
        "resultado": "sucesso",
        "token": str(token),
    }


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_o_mesmo_token_em_paralelo_envia_uma_vez(
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-15
    from apps.pedidos import reenvio_do_pedido_formal as modulo
    from tests.apoio.concorrencia import executar_em_paralelo
    from tests.apoio.trava import esperar_outra_conexao_na_trava

    a, _x, _y, pedido = af_falhas(relogio, simulador_pagamentos, settings)
    mail.outbox.clear()
    token = uuid.uuid4()
    enviar = modulo.enviar_email
    pausado = Event()

    def pausar(*args: Any) -> None:
        pausado.set()
        esperar_outra_conexao_na_trava()
        enviar(*args)

    monkeypatch.setattr(modulo, "enviar_email", pausar)

    def primeira(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        return modulo.reenviar_pedido_formal(a.admin, pedido, token=token)

    def segunda(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        assert pausado.wait(15)
        return modulo.reenviar_pedido_formal(a.admin, pedido, token=token)

    resultados = executar_em_paralelo(primeira, segunda, tempo_limite=60)
    assert [r.excecao for r in resultados] == [None, None], [repr(r.excecao) for r in resultados]
    assert resultados[0].valor.tentativa.pk == resultados[1].valor.tentativa.pk
    assert (resultados[0].valor.nova, resultados[1].valor.nova) == (True, False)
    assert len(_enviados()) == 1
    assert len([t for t in _tentativas() if t.tipo == "manual"]) == 1


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_tokens_distintos_em_paralelo_se_executam_em_sequencia(
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-16
    from apps.pedidos import reenvio_do_pedido_formal as modulo
    from tests.apoio.concorrencia import executar_em_paralelo
    from tests.apoio.trava import esperar_outra_conexao_na_trava

    a, _x, _y, pedido = af_falhas(relogio, simulador_pagamentos, settings)
    mail.outbox.clear()
    enviar = modulo.enviar_email
    pausado = Event()
    chamadas: list[int] = []

    def pausar(*args: Any) -> None:
        chamadas.append(1)
        if len(chamadas) == 1:
            pausado.set()
            esperar_outra_conexao_na_trava()  # o segundo parado na trava do envio
        enviar(*args)

    monkeypatch.setattr(modulo, "enviar_email", pausar)

    def primeira(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        return modulo.reenviar_pedido_formal(a.admin, pedido, token=uuid.uuid4())

    def segunda(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        assert pausado.wait(15)
        return modulo.reenviar_pedido_formal(a.admin, pedido, token=uuid.uuid4())

    resultados = executar_em_paralelo(primeira, segunda, tempo_limite=60)
    assert [r.excecao for r in resultados] == [None, None], [repr(r.excecao) for r in resultados]
    quarta, quinta = [t for t in _tentativas() if t.tipo == "manual"]
    assert (quarta.numero, quinta.numero) == (4, 5)
    assert quinta.iniciada_em >= quarta.concluida_em
    um, dois = _enviados()
    assert (um.body, dois.body) == (pedido.corpo, pedido.corpo)


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar(
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-17
    from apps.pedidos import envio_do_pedido_formal as envio
    from apps.pedidos import reenvio_do_pedido_formal as modulo
    from tests.apoio.concorrencia import executar_em_paralelo

    settings.EMAIL_BACKEND = FALHA
    a, _x, _y, pedido = arranjo_af(relogio, simulador_pagamentos)
    processar(relogio, PRAZO)
    processar(relogio, PRAZO + 5 * M)
    relogio.congelar(PRAZO + 35 * M)
    pausado, liberar = Event(), Event()
    enviar = envio.enviar_email

    def pausar(*args: Any) -> None:
        pausado.set()
        assert liberar.wait(20)
        enviar(*args)

    monkeypatch.setattr(envio, "enviar_email", pausar)
    monkeypatch.setattr(modulo, "enviar_email", pausar)

    def automatica(barreira: Any) -> int:
        barreira.wait(timeout=10)
        return envio.processar_pedidos_formais()

    def reenvio(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        assert pausado.wait(15)
        try:
            return modulo.reenviar_pedido_formal(a.admin, pedido, token=uuid.uuid4())
        finally:
            liberar.set()

    resultados = executar_em_paralelo(automatica, reenvio, tempo_limite=60)
    assert resultados[0].excecao is None
    assert isinstance(resultados[1].excecao, modulo.ReenvioRecusado)
    assert resultados[1].excecao.codigo == "ciclo_em_andamento"
    assert [t.tipo for t in _tentativas()] == ["automatica"] * 3
    settings.EMAIL_BACKEND = LOCMEM
