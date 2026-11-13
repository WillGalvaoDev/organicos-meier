"""E13-02: o ciclo automático de envio do pedido formal (acceptance A-1 a A-17)."""

import logging
from datetime import timedelta
from threading import Event
from typing import Any

import pytest
from django.core import mail
from django.db import IntegrityError, transaction

from apps.financeiro.models import MovimentoFinanceiro
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from tests.apoio.pedido_formal import EMAIL_DO_PEDIDO, PRAZO, arranjo_af
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

M = timedelta(minutes=1)
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)
FALHA = "tests.apoio.email_falho.BackendQueFalha"
COM_FALHAS = "tests.apoio.email_falho.BackendComFalhas"
EVENTO = "falha_no_pedido_formal"


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _processar(relogio: RelogioControlado, instante: Any) -> int:
    from apps.pedidos.envio_do_pedido_formal import processar_pedidos_formais

    relogio.congelar(instante)
    return processar_pedidos_formais()


def _envio() -> Any:
    from apps.pedidos.models import EnvioDoPedidoFormal

    return EnvioDoPedidoFormal.objects.get()


def _tentativas() -> list[Any]:
    from apps.pedidos.models import TentativaDeEnvioDoPedidoFormal

    return list(TentativaDeEnvioDoPedidoFormal.objects.order_by("numero"))


def _tres_falhas(relogio: RelogioControlado, settings: Any, sim: Any) -> tuple[Any, Any]:
    settings.EMAIL_BACKEND = FALHA
    a, _x, _y, pedido = arranjo_af(relogio, sim)
    for instante in (PRAZO, PRAZO + 5 * M, PRAZO + 35 * M):
        _processar(relogio, instante)
    return a, pedido


def test_o_primeiro_envio_aceito_conclui_o_ciclo(relogio: RelogioControlado, sim: Any) -> None:
    mail.outbox.clear()
    _a, _x, _y, pedido = arranjo_af(relogio, sim)
    assert _processar(relogio, PRAZO) == 1  # A-1
    (tentativa,) = _tentativas()
    assert (tentativa.tipo, tentativa.ordem_automatica, tentativa.numero) == ("automatica", 1, 1)
    assert tentativa.resultado == "sucesso"
    assert tentativa.resposta == "aceito pelo serviço de e-mail"
    assert tentativa.destino == EMAIL_DO_PEDIDO
    assert (tentativa.autor_id, tentativa.token) == (None, None)
    envio = _envio()
    assert (envio.situacao, envio.automaticas) == ("concluido_com_sucesso", 1)
    assert envio.proxima_tentativa_em is None
    assert envio.concluido_em == PRAZO
    (enviado,) = [m for m in mail.outbox if m.to == [EMAIL_DO_PEDIDO]]
    assert (enviado.subject, enviado.body) == (pedido.assunto, pedido.corpo)


def test_sucesso_depois_de_uma_falha(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-2
    from tests.apoio.email_falho import BackendComFalhas

    settings.EMAIL_BACKEND = COM_FALHAS
    BackendComFalhas.configurar(falhas=1)
    arranjo_af(relogio, sim)
    assert _processar(relogio, PRAZO) == 1
    primeira = _envio()
    assert primeira.situacao == "em_andamento"
    assert primeira.proxima_tentativa_em == PRAZO + 5 * M
    assert _processar(relogio, PRAZO + 5 * M) == 1
    um, dois = _tentativas()
    assert (um.resultado, um.resposta, um.ordem_automatica) == ("falha", "ConnectionError", 1)
    assert (dois.resultado, dois.ordem_automatica) == ("sucesso", 2)
    assert _envio().situacao == "concluido_com_sucesso"
    assert not Notificacao.objects.filter(evento=EVENTO).exists()


def test_exatamente_tres_tentativas_automaticas(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-3
    _tres_falhas(relogio, settings, sim)
    tentativas = _tentativas()
    assert [(t.ordem_automatica, t.resultado) for t in tentativas] == [
        (1, "falha"),
        (2, "falha"),
        (3, "falha"),
    ]
    envio = _envio()
    assert (envio.situacao, envio.automaticas) == ("concluido_com_falhas", 3)
    assert envio.proxima_tentativa_em is None
    assert envio.concluido_em == PRAZO + 35 * M
    assert _processar(relogio, PRAZO + 120 * M) == 0
    assert _processar(relogio, PRAZO + timedelta(days=1)) == 0
    assert len(_tentativas()) == 3


def test_o_aviso_vai_aos_administradores_ativos(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-4
    from tests.fabricas import ContaFactory

    segundo = ContaFactory.create(nome="Segundo admin", administrador=True)
    a, pedido = _tres_falhas(relogio, settings, sim)
    avisos = list(Notificacao.objects.filter(evento=EVENTO).order_by("conta_id"))
    assert {n.conta_id for n in avisos} == {a.admin.pk, segundo.pk}
    for aviso in avisos:
        assert aviso.chave == f"falha_no_pedido_formal:{pedido.pk}:{aviso.conta_id}"
        assert aviso.titulo == "Falha no envio do pedido formal: F"
        assert aviso.link == f"/administracao/rodadas/{a.rodada.pk}/pedido-formal/"
        assert f"O pedido formal nº {pedido.pk} da rodada {a.rodada.pk} de F" in aviso.corpo
        assert "3 tentativas automáticas" in aviso.corpo
        for n in (1, 2, 3):
            assert f"Tentativa {n} em " in aviso.corpo
        assert aviso.corpo.count(": ConnectionError.") == 3
        assert "Use Reenviar pedido" in aviso.corpo
    assert not Notificacao.objects.filter(evento=EVENTO, conta__in=[a.a, a.b]).exists()


def test_a_segunda_execucao_antes_do_intervalo_nao_tenta(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-5
    settings.EMAIL_BACKEND = FALHA
    arranjo_af(relogio, sim)
    assert _processar(relogio, PRAZO) == 1
    assert _processar(relogio, PRAZO + 4 * M) == 0
    assert len(_tentativas()) == 1
    assert _envio().proxima_tentativa_em == PRAZO + 5 * M


def test_a_quarta_tentativa_automatica_e_recusada_pelo_banco(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-6
    from apps.pedidos.models import TentativaDeEnvioDoPedidoFormal

    _a, pedido = _tres_falhas(relogio, settings, sim)

    def criar(numero: int, ordem: int) -> None:
        with transaction.atomic():
            TentativaDeEnvioDoPedidoFormal.objects.create(
                pedido_formal=pedido,
                numero=numero,
                tipo="automatica",
                ordem_automatica=ordem,
                iniciada_em=PRAZO,
                concluida_em=PRAZO,
                resultado="falha",
                resposta="x",
                destino=EMAIL_DO_PEDIDO,
            )

    with pytest.raises(IntegrityError):
        criar(4, 4)
    with pytest.raises(IntegrityError):
        criar(5, 3)


def test_consulta_que_falha_nao_conta_como_tentativa(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    mail.outbox.clear()
    arranjo_af(relogio, sim)
    sim.falhar_proximas(1, operacao="buscar_por_referencia")
    assert _processar(relogio, PRAZO) == 0
    envio = _envio()
    assert (envio.automaticas, envio.situacao) == (0, "em_andamento")
    assert envio.proxima_tentativa_em == PRAZO + 5 * M
    assert not _tentativas()
    assert not [m for m in mail.outbox if m.to == [EMAIL_DO_PEDIDO]]
    assert _processar(relogio, PRAZO + 5 * M) == 1
    (tentativa,) = _tentativas()
    assert (tentativa.ordem_automatica, tentativa.resultado) == (1, "sucesso")


def test_a_consulta_vem_antes_do_envio(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-8
    from apps.pedidos import envio_do_pedido_formal as modulo

    _a, x, y, _pedido = arranjo_af(relogio, sim)
    eventos: list[str] = []
    consultar, enviar = modulo.consultar_antes_de_decidir, modulo.enviar_email

    def espiar_consulta(referencia: str) -> Any:
        eventos.append(f"consulta:{referencia}")
        return consultar(referencia)

    def espiar_envio(*args: Any) -> None:
        eventos.append("envio")
        enviar(*args)

    monkeypatch.setattr(modulo, "consultar_antes_de_decidir", espiar_consulta)
    monkeypatch.setattr(modulo, "enviar_email", espiar_envio)
    _processar(relogio, PRAZO)
    assert eventos == [
        f"consulta:{x.referencia_externa}",
        f"consulta:{y.referencia_externa}",
        "envio",
    ]


def test_rodada_cancelada_antes_da_primeira_execucao_interrompe(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    mail.outbox.clear()
    a, _x, _y, _pedido = arranjo_af(relogio, sim)
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    assert _processar(relogio, PRAZO + M) == 0
    envio = _envio()
    assert (envio.situacao, envio.motivo_da_interrupcao) == ("interrompido", "rodada_cancelada")
    assert envio.proxima_tentativa_em is None
    assert envio.concluido_em == PRAZO + M
    assert not _tentativas()
    assert not [m for m in mail.outbox if m.to == [EMAIL_DO_PEDIDO]]
    assert EntradaAuditoria.objects.filter(acao="pedido_formal.interromper").count() == 1


def test_rodada_cancelada_depois_da_primeira_falha(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-10
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    settings.EMAIL_BACKEND = FALHA
    a, _x, _y, _pedido = arranjo_af(relogio, sim)
    _processar(relogio, PRAZO)
    cancelar_rodada(a.admin, a.rodada, com_reembolso=False)
    assert _processar(relogio, PRAZO + 5 * M) == 0
    assert _envio().situacao == "interrompido"
    assert len(_tentativas()) == 1
    assert not Notificacao.objects.filter(evento=EVENTO).exists()


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_duas_execucoes_ao_mesmo_tempo_enviam_uma_vez(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-11
    from apps.pedidos import envio_do_pedido_formal as modulo
    from tests.apoio.concorrencia import executar_em_paralelo

    mail.outbox.clear()
    arranjo_af(relogio, simulador_pagamentos)
    pausado, liberar = Event(), Event()
    enviar = modulo.enviar_email

    def pausar(*args: Any) -> None:
        pausado.set()
        assert liberar.wait(20)
        enviar(*args)

    monkeypatch.setattr(modulo, "enviar_email", pausar)

    def primeira(barreira: Any) -> int:
        barreira.wait(timeout=10)
        return modulo.processar_pedidos_formais()

    def segunda(barreira: Any) -> int:
        barreira.wait(timeout=10)
        assert pausado.wait(15)
        try:
            return modulo.processar_pedidos_formais()
        finally:
            liberar.set()

    resultados = executar_em_paralelo(primeira, segunda, tempo_limite=60)
    assert [r.excecao for r in resultados] == [None, None], [repr(r.excecao) for r in resultados]
    assert [r.valor for r in resultados] == [1, 0]
    assert len(_tentativas()) == 1
    assert len([m for m in mail.outbox if m.to == [EMAIL_DO_PEDIDO]]) == 1


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_o_cancelamento_espera_a_tentativa_em_curso(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-12
    from apps.pedidos import envio_do_pedido_formal as modulo
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
    from tests.apoio.concorrencia import executar_em_paralelo
    from tests.apoio.trava import esperar_outra_conexao_na_trava

    a, _x, _y, _pedido = arranjo_af(relogio, simulador_pagamentos)
    pausado = Event()
    enviar = modulo.enviar_email

    def pausar(*args: Any) -> None:
        pausado.set()
        esperar_outra_conexao_na_trava()  # o cancelamento parado na trava da rodada
        enviar(*args)

    monkeypatch.setattr(modulo, "enviar_email", pausar)

    def tentativa(barreira: Any) -> int:
        barreira.wait(timeout=10)
        return modulo.processar_pedidos_formais()

    def cancelamento(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        assert pausado.wait(15)
        return cancelar_rodada(a.admin, a.rodada, com_reembolso=False)

    resultados = executar_em_paralelo(tentativa, cancelamento, tempo_limite=60)
    assert [r.excecao for r in resultados] == [None, None], [repr(r.excecao) for r in resultados]
    assert resultados[0].valor == 1
    assert len(_tentativas()) == 1
    assert _envio().situacao == "concluido_com_sucesso"


def test_excecao_inesperada_do_servico_e_falha_da_tentativa(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-13
    from apps.pedidos import envio_do_pedido_formal as modulo

    arranjo_af(relogio, sim)

    def quebrar(*args: Any) -> None:
        raise RuntimeError("falha inesperada")

    monkeypatch.setattr(modulo, "enviar_email", quebrar)
    assert _processar(relogio, PRAZO) == 1
    (tentativa,) = _tentativas()
    assert (tentativa.resultado, tentativa.resposta) == ("falha", "RuntimeError")
    envio = _envio()
    assert envio.situacao == "em_andamento"
    assert envio.proxima_tentativa_em == PRAZO + 5 * M


def test_a_falha_do_canal_nao_muda_dinheiro_nem_pedido(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-14
    from apps.pedidos.models import Pedido, SituacaoDoPedido
    from apps.rodadas.models import Rodada

    settings.EMAIL_BACKEND = FALHA
    arranjo_af(relogio, sim)

    def foto() -> tuple[Any, ...]:
        return (
            MovimentoFinanceiro.objects.count(),
            list(Rodada.objects.values_list("pk", "etapa")),
            list(SituacaoDoPedido.objects.order_by("pk").values()),
            list(Pedido.objects.order_by("pk").values()),
        )

    antes = foto()
    for instante in (PRAZO, PRAZO + 5 * M, PRAZO + 35 * M):
        _processar(relogio, instante)
    assert foto() == antes


def test_o_destino_e_lido_a_cada_tentativa(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-15
    from apps.fornecedores.models import Fornecedor
    from tests.apoio.email_falho import BackendComFalhas

    settings.EMAIL_BACKEND = COM_FALHAS
    BackendComFalhas.configurar(falhas=1)
    a, _x, _y, pedido = arranjo_af(relogio, sim)
    _processar(relogio, PRAZO)
    Fornecedor.objects.filter(pk=a.fornecedor.pk).update(email_pedido="novo@f.example")
    _processar(relogio, PRAZO + 5 * M)
    um, dois = _tentativas()
    assert (um.destino, dois.destino) == (EMAIL_DO_PEDIDO, "novo@f.example")
    (enviado,) = [m for m in mail.outbox if m.to == ["novo@f.example"]]
    assert (enviado.subject, enviado.body) == (pedido.assunto, pedido.corpo)


def test_a_auditoria_da_conclusao_do_ciclo(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> None:  # A-16
    _a, pedido = _tres_falhas(relogio, settings, sim)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="pedido_formal.ciclo_concluido")
    assert (auditoria.autor_tipo, auditoria.autor_id) == ("sistema", None)
    dados = auditoria.alteracoes
    assert dados["pedido_formal"] == pedido.pk
    assert dados["estado"] == "concluido_com_falhas"
    assert dados["tentativas"] == [
        {"numero": n, "resultado": "falha", "resposta": "ConnectionError"} for n in (1, 2, 3)
    ]


def test_o_log_nao_leva_destino_assunto_nem_corpo(
    relogio: RelogioControlado,
    sim: Any,
    settings: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:  # A-17
    caplog.set_level(logging.DEBUG)
    settings.EMAIL_BACKEND = FALHA
    _a, _x, _y, pedido = arranjo_af(relogio, sim)
    sim.falhar_proximas(1, operacao="buscar_por_referencia")
    for instante in (PRAZO, PRAZO + 5 * M, PRAZO + 35 * M, PRAZO + 65 * M):
        _processar(relogio, instante)
    assert caplog.records
    for registro in caplog.records:
        texto = registro.getMessage()
        assert EMAIL_DO_PEDIDO not in texto
        assert pedido.assunto not in texto
        assert pedido.corpo not in texto


def _af_meio_concorrente(
    relogio: RelogioControlado, sim: Any, settings: Any
) -> tuple[Any, Any, Any, Any]:
    """AF-meio-concorrente: a primeira tentativa falhou em `PRAZO`, a próxima está em
    `PRAZO + 5 min`, o e-mail continua falhando e o relógio fica em `PRAZO + 5 min`."""
    settings.EMAIL_BACKEND = FALHA
    af = arranjo_af(relogio, sim)
    _processar(relogio, PRAZO)
    relogio.congelar(PRAZO + 5 * M)
    return af


def _duas_execucoes(
    relogio: RelogioControlado,
    monkeypatch: pytest.MonkeyPatch,
    *,
    consulta_de_b_falha: bool,
    antes_de_liberar_b: Any = None,
) -> tuple[list[Any], list[str]]:
    """B lê o envio vencido e para na consulta; A roda inteira; só então a consulta de B termina
    (falhando ou com sucesso). Só a consulta de B é um dublê. Devolve os resultados e as
    referências consultadas, na ordem."""
    from threading import local

    from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
    from apps.pedidos import envio_do_pedido_formal as modulo
    from tests.apoio.concorrencia import executar_em_paralelo

    consultar = modulo.consultar_antes_de_decidir
    consultadas: list[str] = []
    eh_b = local()
    b_consultando, liberar_b = Event(), Event()

    def consulta(referencia: str) -> Any:
        if getattr(eh_b, "valor", False):
            b_consultando.set()
            assert liberar_b.wait(30)
            if consulta_de_b_falha:
                raise ConsultaAoProvedorFalhou(referencia, "indisponivel")
        consultadas.append(referencia)
        return consultar(referencia)

    monkeypatch.setattr(modulo, "consultar_antes_de_decidir", consulta)

    def execucao_b(barreira: Any) -> int:
        barreira.wait(timeout=10)
        eh_b.valor = True
        return modulo.processar_pedidos_formais()

    def execucao_a(barreira: Any) -> int:
        barreira.wait(timeout=10)
        assert b_consultando.wait(15)
        try:
            return modulo.processar_pedidos_formais()
        finally:
            if antes_de_liberar_b is not None:
                antes_de_liberar_b()
            liberar_b.set()

    resultados = executar_em_paralelo(execucao_b, execucao_a, tempo_limite=60)
    assert [r.excecao for r in resultados] == [None, None], [repr(r.excecao) for r in resultados]
    return resultados, consultadas


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_consulta_atrasada_que_falha_nao_encurta_o_intervalo_da_terceira(
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-18
    _af_meio_concorrente(relogio, simulador_pagamentos, settings)
    resultados, _consultadas = _duas_execucoes(relogio, monkeypatch, consulta_de_b_falha=True)
    assert (resultados[0].valor, resultados[1].valor) == (0, 1)  # B, A
    envio = _envio()
    assert envio.automaticas == 2
    assert envio.proxima_tentativa_em == PRAZO + 35 * M
    assert envio.situacao == "em_andamento"
    assert [(t.ordem_automatica, t.resultado) for t in _tentativas()] == [
        (1, "falha"),
        (2, "falha"),
    ]


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_consulta_atrasada_que_termina_bem_nao_autoriza_a_terceira(
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # A-19
    from apps.pedidos.models import EnvioDoPedidoFormal

    a, x, y, _pedido = _af_meio_concorrente(relogio, simulador_pagamentos, settings)
    resultados, consultadas = _duas_execucoes(
        relogio,
        monkeypatch,
        consulta_de_b_falha=False,
        antes_de_liberar_b=lambda: relogio.congelar(PRAZO + 36 * M),
    )
    assert (resultados[0].valor, resultados[1].valor) == (0, 1)  # B, A
    envio = _envio()
    assert (envio.automaticas, envio.proxima_tentativa_em) == (2, PRAZO + 35 * M)
    assert len(_tentativas()) == 2
    consultadas_ate_aqui = len(consultadas)
    assert _processar(relogio, PRAZO + 36 * M) == 1
    refs = {x.referencia_externa, y.referencia_externa}
    assert refs <= set(consultadas[consultadas_ate_aqui:])
    terceira = _tentativas()[2]
    assert (terceira.ordem_automatica, terceira.resultado) == (3, "falha")
    assert EnvioDoPedidoFormal.objects.get().situacao == "concluido_com_falhas"
    admins = Notificacao.objects.filter(evento=EVENTO)
    assert admins.count() == admins.values("destinatario").distinct().count() >= 1
