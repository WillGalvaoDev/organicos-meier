"""E11-05: rodada que volta para interesse por pagamentos insuficientes (acceptance A-1 a A-17)."""

from decimal import Decimal
from typing import Any

import pytest

from apps.catalogo.servicos import alterar_multiplo
from apps.contas.moderacao import suspender
from apps.financeiro.apuracao import frete_do_ciclo
from apps.financeiro.models import ApuracaoNoLivro, ObrigacaoComComprador, Reembolso
from apps.fornecedores.servicos import alterar_minimo
from apps.interesses.consultas import total_reservado
from apps.interesses.models import ParcelaDeInteresse
from apps.interesses.servicos import adicionar_interesse
from apps.notificacoes.models import Notificacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.provedor import NovaCobranca, obter_provedor
from apps.pedidos.models import DestinoDoPagamento, Pedido, SituacaoDoPedido
from apps.rodadas.estoque import alterar_estoque
from apps.rodadas.fechamento import TransicaoRecusada, voltar_para_interesse
from apps.rodadas.models import EstoqueDaRodada
from tests.apoio.apuracao import H, arranjo_ap, pagar
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory, ParcelaFactory

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H
INSUFICIENTE = "100.00"


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _iniciar(a: Any) -> Any:
    from apps.pedidos.apuracao import iniciar_apuracao

    return iniciar_apuracao(a.admin, a.rodada)


def _retorno(
    relogio: RelogioControlado, sim: Any, **arranjo: Any
) -> tuple[Any, Pedido, Pedido, Any]:
    """AP-insuficiente com X pago e Y sem pagamento, apurado em `T0 + 48h`."""
    a, x, y = arranjo_ap(relogio, minimo=INSUFICIENTE, **arranjo)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    return a, x, y, _iniciar(a)


def _parcelas(comprador: Any, produto: Any) -> list[ParcelaDeInteresse]:
    return list(
        ParcelaDeInteresse.objects.filter(comprador=comprador, produto=produto).order_by(
            "sequencia"
        )
    )


def test_pagamentos_insuficientes_devolvem_a_rodada_ao_interesse(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-1
    a, _x, _y, _ = _retorno(relogio, sim)
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "interesse"
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.voltar_para_interesse")
    assert auditoria.alteracoes["motivo"] == "pagamentos_insuficientes"


def test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-2
    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE, limites=(11, 12))
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    antes = {p.pk: p.sequencia for p in ParcelaDeInteresse.objects.all()}
    _iniciar(a)
    de_p1 = _parcelas(a.a, a.p1)
    de_p2 = _parcelas(a.a, a.p2)
    assert [(p.situacao, p.quantidade_reservada) for p in de_p1] == [("ativa", D("6.000"))]
    assert [(p.situacao, p.quantidade_reservada) for p in de_p2] == [("ativa", D("4.000"))]
    assert {p.situacao for p in ParcelaDeInteresse.objects.filter(comprador=a.b)} == {"removida"}
    assert {e.produto_id: e.limite for e in EstoqueDaRodada.objects.filter(rodada=a.rodada)} == {
        a.p1.pk: D("11.000"),
        a.p2.pk: D("12.000"),
    }
    assert total_reservado(a.p1) == D("6.000")
    assert total_reservado(a.p2) == D("4.000")
    assert {p.pk: p.sequencia for p in ParcelaDeInteresse.objects.all()} == antes


def test_parcela_com_pendente_volta_a_ativa_com_a_parte_congelada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-3
    from django.db import transaction

    from apps.pedidos import apuracao as modulo
    from apps.pedidos.models import AberturaDoPagamento

    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE, pendente_a_p1=2)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    (parcela,) = _parcelas(a.a, a.p1)
    assert (parcela.situacao, parcela.quantidade_reservada) == ("pendente", D("0.000"))
    sequencia = parcela.sequencia
    # a restauração, sozinha: a reserva é a parte congelada e a pendência não muda
    with transaction.atomic():
        restauradas, _ = modulo._restaurar_as_reservas_dos_pagantes(
            AberturaDoPagamento.objects.get(), [x.pk]
        )
        parcela.refresh_from_db()
        assert (parcela.situacao, parcela.quantidade_reservada, parcela.quantidade_pendente) == (
            "ativa",
            D("6.000"),
            D("2.000"),
        )
        assert [parcela.pk, "6.000"] in restauradas
        assert parcela.sequencia == sequencia
        transaction.set_rollback(True)
    # o retorno inteiro atende a fila com o estoque liberado por B: o pendente de A (anterior a
    # qualquer reserva nova, R-5) recebe a reserva; ver o ponto para o especificador no review.md
    _iniciar(a)
    parcela.refresh_from_db()
    assert (parcela.situacao, parcela.quantidade_reservada, parcela.quantidade_pendente) == (
        "ativa",
        D("8.000"),
        D("0.000"),
    )
    assert parcela.quantidade_reservada + parcela.quantidade_pendente <= parcela.quantidade_original


def test_unidades_de_caixa_invalidada_ficam_reservadas_sem_passar_pela_fila(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    from apps.pedidos.models import RestauracaoDeCaixa

    a, _x, _y, _ = _retorno(relogio, sim)
    (parcela,) = _parcelas(a.a, a.p2)
    assert (parcela.situacao, parcela.quantidade_reservada) == ("ativa", D("4.000"))
    assert RestauracaoDeCaixa.objects.count() == 0


def test_devolucao_integral_dos_pedidos_pagos(relogio: RelogioControlado, sim: Any) -> None:
    # A-5
    from apps.financeiro.models import ParcelaDeDevolucao
    from apps.financeiro.reserva import sem_cobertura_da_obrigacao

    _a, x, _y, apuracao = _retorno(relogio, sim)
    reembolso = Reembolso.objects.get(pedido=x)
    assert reembolso.chave == f"minimo:{apuracao.pk}:{x.pk}"
    assert (reembolso.motivo, reembolso.tipo) == ("minimo_nao_atingido", "integral")
    assert (reembolso.produtos, reembolso.servico, reembolso.frete) == (
        D("80.00"),
        D("4.00"),
        D("10.35"),
    )
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x)
    assert obrigacao.devido == D("94.35")
    assert sem_cobertura_da_obrigacao(obrigacao) == D("0.00")
    assert ParcelaDeDevolucao.objects.count() == 0


def test_o_retorno_nao_apura_no_livro_nem_gera_frete_efetivo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    a, _x, _y, _ = _retorno(relogio, sim)
    assert ApuracaoNoLivro.objects.count() == 0
    frete = frete_do_ciclo(a.ciclo)
    assert (frete.efetivo, frete.arrecadado, frete.devolvido, frete.deficit) == (
        None,
        None,
        None,
        None,
    )


def test_aviso_de_retorno_so_aos_pagantes_com_chave_propria(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    a, x, _y, apuracao = _retorno(relogio, sim)
    (aviso,) = Notificacao.objects.filter(conta=a.a, evento="retorno_para_interesse")
    assert aviso.titulo == "Rodada de volta ao interesse: F"
    assert aviso.chave == f"retorno_para_interesse:apuracao:{apuracao.pk}:{a.a.pk}"
    assert aviso.link == f"/pedidos/{x.pk}/"
    assert "os pagamentos confirmados não atingiram o mínimo" in aviso.corpo
    assert "continuam reservados" in aviso.corpo
    assert "R$ 94,35" in aviso.corpo
    assert "100,00" not in aviso.corpo
    assert not Notificacao.objects.filter(conta=a.b, evento="retorno_para_interesse").exists()
    assert Notificacao.objects.filter(conta=a.b, evento="itens_cancelados").count() == 1
    assert not Notificacao.objects.filter(chave=f"retorno_para_interesse:{a.ciclo.pk}").exists()


def test_pendente_antigo_recebe_o_estoque_liberado_antes_de_qualquer_reserva_nova(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE, limites=(11, 12))
    c = ContaFactory.create(nome="Comprador C")
    antigo = ParcelaFactory.create(
        comprador=c,
        produto=a.p1,
        quantidade_original=D("3"),
        quantidade_reservada=D("0"),
        quantidade_pendente=D("3"),
        situacao="pendente",
    )
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    _iniciar(a)
    antigo.refresh_from_db()
    assert (antigo.situacao, antigo.quantidade_reservada, antigo.quantidade_pendente) == (
        "ativa",
        D("3.000"),
        D("0.000"),
    )


def test_total_reservado_cabe_no_estoque_sem_reserva_duplicada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE, limites=(11, 12))
    c = ContaFactory.create(nome="Comprador C")
    ParcelaFactory.create(
        comprador=c,
        produto=a.p1,
        quantidade_original=D("3"),
        quantidade_reservada=D("0"),
        quantidade_pendente=D("3"),
        situacao="pendente",
    )
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    _iniciar(a)
    assert total_reservado(a.p1) == D("9.000")
    assert total_reservado(a.p2) == D("4.000")
    for parcela in ParcelaDeInteresse.objects.all():
        assert parcela.quantidade_reservada + parcela.quantidade_pendente <= (
            parcela.quantidade_original
        )


def test_estoque_abaixo_da_reserva_congelada_desfaz_a_apuracao(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-10
    from apps.pedidos.models import ApuracaoFinal

    a, x, y = arranjo_ap(relogio, minimo=INSUFICIENTE, limites=(11, 12))
    pagar(relogio, sim, x)
    EstoqueDaRodada.objects.filter(rodada=a.rodada, produto=a.p1).update(limite=D("5"))
    relogio.congelar(PRAZO)
    antes = [(p.pk, p.situacao) for p in ParcelaDeInteresse.objects.order_by("pk")]
    with pytest.raises(RuntimeError):
        _iniciar(a)
    assert ApuracaoFinal.objects.count() == 0
    assert SituacaoDoPedido.objects.get(pedido=y).situacao == "aguardando_pagamento"
    assert [(p.pk, p.situacao) for p in ParcelaDeInteresse.objects.order_by("pk")] == antes
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "pagamento"


def _novo_fechamento(relogio: RelogioControlado, a: Any, c: Any) -> None:
    """C pede 5 de P1 e o administrador inicia o fechamento com o mínimo atingido."""
    from apps.rodadas.fechamento import iniciar_fechamento

    adicionar_interesse(c, a.p1, D("5"))
    iniciar_fechamento(a.admin, a.rodada)


def test_novo_fechamento_com_estorno_pendente(relogio: RelogioControlado, sim: Any) -> None:
    # A-11
    from apps.financeiro.models import ParcelaDeDevolucao
    from apps.rodadas.models import Ciclo

    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE, limites=(11, 12))
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    _iniciar(a)
    c = ContaFactory.create(nome="Comprador C")
    _novo_fechamento(relogio, a, c)
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "fechamento"
    ultimo = Ciclo.objects.filter(rodada=a.rodada).order_by("-numero").first()
    assert ultimo is not None
    assert ultimo.numero == 2
    assert ParcelaDeDevolucao.objects.count() == 0
    assert ObrigacaoComComprador.objects.filter(pedido=x).count() == 1


def test_novo_pagamento_cria_pedidos_novos_sem_tocar_o_ciclo_antigo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-12
    from apps.pedidos.abertura import abrir_pagamento
    from apps.rodadas.fechamento import encerrar_fechamento

    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE, limites=(11, 12))
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    _iniciar(a)
    c = ContaFactory.create(nome="Comprador C")
    _novo_fechamento(relogio, a, c)
    relogio.congelar(PRAZO + 25 * H)
    encerrar_fechamento(a.rodada)
    a.rodada.refresh_from_db()
    abrir_pagamento(a.admin, a.rodada, D("10.00"))
    novos = Pedido.objects.exclude(abertura__ciclo=a.ciclo)
    assert novos.count() >= 1
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "pago"
    assert Reembolso.objects.filter(pedido=x, tipo="integral").count() == 1
    assert total_reservado(a.p1) <= D("11")


def test_pagamento_antigo_pela_referencia_do_ciclo_antigo_vira_devolucao(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-13
    from apps.pedidos.abertura import abrir_pagamento
    from apps.rodadas.fechamento import encerrar_fechamento

    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE, limites=(11, 12))
    pagar(relogio, sim, x)
    relogio.congelar(T0 + H)
    duplicado = obter_provedor().criar_cobranca(
        NovaCobranca("dup-x", x.referencia_externa, x.total, "Pedido", T0 + 25 * H)
    )
    sim.aprovar(duplicado.pagamento.id_externo, em=T0 + 3 * H)
    relogio.congelar(PRAZO)
    _iniciar(a)
    c = ContaFactory.create(nome="Comprador C")
    _novo_fechamento(relogio, a, c)
    relogio.congelar(PRAZO + 25 * H)
    encerrar_fechamento(a.rodada)
    a.rodada.refresh_from_db()
    abrir_pagamento(a.admin, a.rodada, D("10.00"))
    novos = {
        p.pk: SituacaoDoPedido.objects.get(pedido=p).situacao
        for p in Pedido.objects.exclude(abertura__ciclo=a.ciclo)
    }
    relogio.congelar(PRAZO + 30 * H)
    sim.entregar_avisos()
    from apps.pagamentos.chamadas import processar_chamadas

    processar_chamadas()
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=duplicado.pagamento.id_externo)
    assert (destino.pedido_id, destino.destino, destino.motivo) == (
        x.pk,
        "devolucao",
        "duplicidade",
    )
    assert {
        p.pk: SituacaoDoPedido.objects.get(pedido=p).situacao
        for p in Pedido.objects.exclude(abertura__ciclo=a.ciclo)
    } == novos


def test_condicoes_voltam_a_ser_alteraveis(relogio: RelogioControlado, sim: Any) -> None:  # A-14
    a, _x, _y, _ = _retorno(relogio, sim, limites=(11, 12))
    alterar_minimo(a.admin, a.fornecedor, D("120.00"))
    alterar_multiplo(a.admin, a.p2, D("2"))
    alterar_estoque(a.admin, EstoqueDaRodada.objects.get(rodada=a.rodada, produto=a.p1), D("20"))
    a.fornecedor.refresh_from_db()
    assert a.fornecedor.minimo == D("120.00")


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])
def test_adicao_espera_o_retorno_e_recebe_o_estoque_livre(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-15
    from apps.pedidos import apuracao
    from tests.apoio.corrida import Corrida

    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE, limites=(11, 12))
    pagar(relogio, simulador_pagamentos, x)
    relogio.congelar(PRAZO)
    c = ContaFactory.create(nome="Comprador C")
    corrida = Corrida()
    corrida.depois_de(monkeypatch, apuracao, "_restaurar_as_reservas_dos_pagantes")
    ra, rb = corrida.rodar(
        lambda: apuracao.iniciar_apuracao(a.admin, a.rodada),
        lambda: adicionar_interesse(c, a.p1, D("5")),
        a_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    (da_c,) = _parcelas(c, a.p1)
    assert (da_c.situacao, da_c.quantidade_reservada) == ("ativa", D("5.000"))
    assert total_reservado(a.p1) <= D("11")


def test_motivo_da_e06_continua_exigindo_o_fechamento_encerrado(
    relogio: RelogioControlado,
) -> None:  # A-16
    a, _x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE)
    from django.db import transaction

    with pytest.raises(TransicaoRecusada) as recusa, transaction.atomic():
        voltar_para_interesse(a.rodada, motivo="minimo_nao_atingido")
    assert recusa.value.codigo == "fora_de_fechamento_encerrado"


def _retorno_com_a_conta_impedida(
    relogio: RelogioControlado, sim: Any, *, remover: bool = False, com_c: bool = False
) -> tuple[Any, Pedido]:
    """AP-insuficiente, limites 11 e 12; X pago; A suspenso (ou removido) antes da apuração."""
    from apps.contas.moderacao import remover as remover_conta

    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE, limites=(11, 12))
    if com_c:
        ParcelaFactory.create(
            comprador=ContaFactory.create(nome="Comprador C"),
            produto=a.p1,
            quantidade_original=D("4"),
            quantidade_reservada=D("0"),
            quantidade_pendente=D("4"),
            situacao="pendente",
        )
    pagar(relogio, sim, x)
    (remover_conta if remover else suspender)(a.admin, a.a)
    relogio.congelar(PRAZO)
    _iniciar(a)
    return a, x


def _conferir_a_conta_impedida(a: Any, x: Pedido, motivo: str) -> None:
    assert {p.situacao for p in ParcelaDeInteresse.objects.filter(comprador=a.a)} == {"removida"}
    for parcela in ParcelaDeInteresse.objects.filter(comprador=a.a):
        assert (parcela.quantidade_reservada, parcela.quantidade_pendente) == (D("0"), D("0"))
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "pago"
    assert Reembolso.objects.filter(pedido=x, motivo="minimo_nao_atingido").count() == 1
    assert not Notificacao.objects.filter(conta=a.a, evento="retorno_para_interesse").exists()
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.apuracao_final")
    removidas = auditoria.alteracoes["retorno"]["removidas_por_conta_impedida"]
    assert {r["motivo"] for r in removidas} == {motivo}
    assert sorted((r["reservada"], r["pendente"]) for r in removidas) == [
        ("4.000", "0.000"),
        ("6.000", "0.000"),
    ]


def test_conta_suspensa_nao_prende_estoque_no_retorno(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-19 (R02)
    a, x = _retorno_com_a_conta_impedida(relogio, sim)
    _conferir_a_conta_impedida(a, x, "conta_suspensa")
    assert total_reservado(a.p1) == D("0")
    assert total_reservado(a.p2) == D("0")
    assert Reembolso.objects.get(pedido=x).produtos + Reembolso.objects.get(
        pedido=x
    ).servico + Reembolso.objects.get(pedido=x).frete == D("94.35")


def test_estoque_liberado_pela_conta_impedida_atende_o_pendente_antigo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-20 (R02, R-5)
    a, _x = _retorno_com_a_conta_impedida(relogio, sim, com_c=True)
    (da_c,) = ParcelaDeInteresse.objects.filter(produto=a.p1, quantidade_original=D("4"))
    assert (da_c.situacao, da_c.quantidade_reservada, da_c.quantidade_pendente) == (
        "ativa",
        D("4.000"),
        D("0.000"),
    )


def test_conta_removida_no_retorno_tem_o_mesmo_efeito(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-21 (R02)
    a, x = _retorno_com_a_conta_impedida(relogio, sim, remover=True)
    _conferir_a_conta_impedida(a, x, "conta_removida")
    assert total_reservado(a.p1) == D("0")


def test_dois_pagantes_recebem_a_devolucao_integral_na_mesma_apuracao(
    relogio: RelogioControlado, sim: Any
) -> None:  # achado pela E11-08: as contas do livro-razão de todas as devoluções, travadas juntas
    a, x, _y = arranjo_ap(
        relogio, minimo=INSUFICIENTE, parcelas_de_p2=(("a", 4), ("c", 2), ("b", 6))
    )
    assert a.c is not None
    z = Pedido.objects.get(comprador=a.c)
    pagar(relogio, sim, x)
    pagar(relogio, sim, z)
    relogio.congelar(PRAZO)
    apuracao = _iniciar(a)
    assert apuracao.resultado == "retorno_para_interesse"
    assert Reembolso.objects.filter(motivo="minimo_nao_atingido").count() == 2
    assert ObrigacaoComComprador.objects.filter(pedido__in=[x, z]).count() == 2


# --- E11-R04: nenhuma trava mais forte que FOR NO KEY UPDATE na apuração ----------------------


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])
def test_retorno_concorre_com_tarifa_tardia_sem_impasse(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-22 (a prova do parecer)
    from dataclasses import replace
    from threading import Event

    from django.db import transaction

    from apps.financeiro import entradas
    from apps.pagamentos.sincronizacao import sincronizar_pagamento
    from apps.pedidos import apuracao
    from tests.apoio.apuracao import cobranca
    from tests.apoio.concorrencia import executar_em_paralelo

    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE)
    simulador_pagamentos.definir_tarifa("pix", percentual=D("1"), fixa=D("0"))
    externo = cobranca(relogio, x)
    simulador_pagamentos.aprovar(externo)
    completa = obter_provedor().consultar_pagamento(externo)
    with transaction.atomic():
        sincronizar_pagamento(replace(completa, tarifa=None), origem="tarefa")
    relogio.congelar(PRAZO)
    consultas, tarifa, retorno = Event(), Event(), Event()
    original_travar = apuracao._travar
    original_tarifa = entradas.registrar_tarifa
    original_devolver = apuracao._devolver_integralmente

    def travar(*args: Any, **kwargs: Any) -> Any:
        consultas.set()
        assert tarifa.wait(15)
        return original_travar(*args, **kwargs)

    def registrar(*args: Any, **kwargs: Any) -> Any:
        resultado = original_tarifa(*args, **kwargs)
        tarifa.set()
        assert retorno.wait(15)
        return resultado

    def devolver(*args: Any, **kwargs: Any) -> Any:
        retorno.set()
        return original_devolver(*args, **kwargs)

    monkeypatch.setattr(apuracao, "_travar", travar)
    monkeypatch.setattr(entradas, "registrar_tarifa", registrar)
    monkeypatch.setattr(apuracao, "_devolver_integralmente", devolver)

    def apurar(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        return apuracao.iniciar_apuracao(a.admin, a.rodada)

    def registrar_pendentes(barreira: Any) -> Any:
        barreira.wait(timeout=10)
        assert consultas.wait(15)
        return entradas.registrar_tarifas_pendentes_agora()

    resultados = executar_em_paralelo(apurar, registrar_pendentes)
    assert all(r.excecao is None for r in resultados), [repr(r.excecao) for r in resultados]
    a.rodada.refresh_from_db()
    assert a.rodada.etapa == "interesse"
    from apps.financeiro.models import Despesa

    assert Despesa.objects.filter(tipo="tarifa").count() == 1


@pytest.mark.concorrencia
@pytest.mark.django_db(transaction=True, databases=["default", "simulador_pagamentos"])
def test_registro_com_chave_para_a_rodada_nao_espera_o_fim_do_retorno(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-23
    from apps.financeiro.models import Despesa
    from apps.pedidos import apuracao
    from tests.apoio.corrida import Corrida

    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE)
    pagar(relogio, simulador_pagamentos, x)
    relogio.congelar(PRAZO)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, apuracao, "voltar_para_interesse")
    ra, rb = corrida.rodar(
        lambda: apuracao.iniciar_apuracao(a.admin, a.rodada),
        lambda: Despesa.objects.create(
            tipo="deficit_frete", valor=D("1.00"), rodada=a.rodada, ciclo=a.ciclo
        ),
        a_atomica=False,
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert not corrida.b_esperou, "a inserção esperou a apuração: a trava foi promovida"


# --- E11-R01: remover a sobra pendente não impede restaurar a reserva paga ----------------------


def test_sobra_removida_nao_impede_a_reserva_paga_no_retorno(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-18 (R01)
    from apps.interesses.servicos import remover_pendente

    a, x, _y = arranjo_ap(relogio, minimo=INSUFICIENTE, pendente_a_p1=2, limites=(11, 12))
    pagar(relogio, sim, x)
    remover_pendente(a.a, a.p1, D("2"))
    (parcela,) = ParcelaDeInteresse.objects.filter(comprador=a.a, produto=a.p1)
    assert parcela.situacao == "removida"
    sequencia = parcela.sequencia
    relogio.congelar(PRAZO)
    _iniciar(a)
    parcela.refresh_from_db()
    assert (parcela.situacao, parcela.quantidade_reservada, parcela.quantidade_pendente) == (
        "ativa",
        D("6.000"),
        D("0.000"),
    )
    assert parcela.sequencia == sequencia


# --- E11-R02 residual: a situação da conta fica registrada na apuração ---------------------------


def _retorno_rr(relogio: RelogioControlado, sim: Any, *, impedir: str | None) -> tuple[Any, Pedido]:
    """O arranjo RR: A só com a parcela de P1 (6 pagas e 2 pendentes), B sem pagar; a conta de A
    é suspensa ou removida (a parcela fica `removida` pela E05-07) antes da apuração."""
    from apps.contas.moderacao import remover as remover_conta

    a, x, _y = arranjo_ap(
        relogio,
        minimo=INSUFICIENTE,
        pendente_a_p1=2,
        parcelas_de_p1=(("a", 6), ("b", 5)),
        parcelas_de_p2=(("b", 12),),
    )
    pagar(relogio, sim, x)
    if impedir == "suspensa":
        suspender(a.admin, a.a)
    elif impedir == "removida":
        remover_conta(a.admin, a.a)
    relogio.congelar(PRAZO)
    _iniciar(a)
    return a, x


def _auditoria_do_retorno() -> dict[str, Any]:
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.apuracao_final")
    retorno: dict[str, Any] = auditoria.alteracoes["retorno"]
    return retorno


@pytest.mark.parametrize(
    ("impedir", "motivo"), [("suspensa", "conta_suspensa"), ("removida", "conta_removida")]
)
def test_conta_impedida_sem_parcela_removivel_fica_registrada_e_sem_aviso(
    relogio: RelogioControlado, sim: Any, impedir: str, motivo: str
) -> None:  # A-25 e A-26 (R02 residual)
    a, x = _retorno_rr(relogio, sim, impedir=impedir)
    assert {p.situacao for p in ParcelaDeInteresse.objects.filter(comprador=a.a)} == {"removida"}
    assert SituacaoDoPedido.objects.get(pedido=x).situacao == "pago"
    assert total_reservado(a.p1) == D("0")
    assert not Notificacao.objects.filter(conta=a.a, evento="retorno_para_interesse").exists()
    retorno = _auditoria_do_retorno()
    assert retorno["contas_impedidas"] == [{"comprador": a.a.pk, "motivo": motivo}]
    assert not [r for r in retorno["removidas_por_conta_impedida"] if r["comprador"] == a.a.pk]
    (parcela_de_a,) = ParcelaDeInteresse.objects.filter(comprador=a.a)
    assert retorno["nao_restauradas"] == [{"parcela": parcela_de_a.pk, "motivo": motivo}]
    assert Reembolso.objects.filter(pedido=x, motivo="minimo_nao_atingido").count() == 1


def test_a_conta_impedida_fica_registrada_com_as_remocoes_efetivas(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-27 (R02, preservação)
    a, _x = _retorno_com_a_conta_impedida(relogio, sim)
    retorno = _auditoria_do_retorno()
    assert retorno["contas_impedidas"] == [{"comprador": a.a.pk, "motivo": "conta_suspensa"}]
    removidas = retorno["removidas_por_conta_impedida"]
    assert sorted((r["reservada"], r["pendente"]) for r in removidas) == [
        ("4.000", "0.000"),
        ("6.000", "0.000"),
    ]


def test_conta_ativa_nao_entra_nas_contas_impedidas_e_recebe_o_aviso(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-28 (regressão)
    a, _x = _retorno_rr(relogio, sim, impedir=None)
    retorno = _auditoria_do_retorno()
    assert retorno["contas_impedidas"] == []
    assert Notificacao.objects.filter(conta=a.a, evento="retorno_para_interesse").count() == 1
    (parcela,) = ParcelaDeInteresse.objects.filter(comprador=a.a)
    assert (parcela.situacao, parcela.quantidade_reservada) == ("ativa", D("6.000"))


def test_reativar_depois_da_apuracao_nao_muda_o_registro(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-29 (regra 2-A)
    from apps.contas.moderacao import reativar

    a, _x = _retorno_rr(relogio, sim, impedir="suspensa")
    antes = _auditoria_do_retorno()
    reativar(a.admin, a.a)
    assert _auditoria_do_retorno() == antes
    assert not Notificacao.objects.filter(conta=a.a, evento="retorno_para_interesse").exists()
    assert {p.situacao for p in ParcelaDeInteresse.objects.filter(comprador=a.a)} == {"removida"}
