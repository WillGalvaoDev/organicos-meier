"""E12-03: cancelamento da rodada com reembolso integral (acceptance A-1 a A-18)."""

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.financeiro.models import ObrigacaoComComprador, ParcelaDeDevolucao, Reembolso
from apps.financeiro.reserva import sem_cobertura_da_obrigacao
from apps.nucleo.auditoria import EntradaAuditoria
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
from apps.pagamentos.models import ChamadaAoProvedor
from apps.pedidos.models import CancelamentoDaRodada, Pedido, SituacaoDoPedido
from apps.rodadas.models import Rodada
from tests.apoio.apuracao import H, arranjo_ap, cobranca, pagar
from tests.apoio.pedidos import T0
from tests.conftest import RelogioControlado

pytestmark = pytest.mark.django_db

D = Decimal
PRAZO = T0 + 48 * H
COM_DOIS_BANCOS = pytest.mark.django_db(
    transaction=True, databases=["default", "simulador_pagamentos"]
)
MOTIVO = "cancelamento_da_rodada"


@pytest.fixture
def sim(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    return simulador_pagamentos


def _cancelar(a: Any, **kwargs: Any) -> Any:
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada

    kwargs.setdefault("com_reembolso", True)
    return cancelar_rodada(a.admin, a.rodada, **kwargs)


def _do_cancelamento(pedido: Pedido) -> Reembolso:
    return Reembolso.objects.get(pedido=pedido, motivo=MOTIVO)


def _x_pago_e_cancelado(relogio: RelogioControlado, sim: Any) -> tuple[Any, Pedido, Pedido]:
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    _cancelar(a)
    return a, x, y


def test_reembolso_integral_do_pedido_pago(relogio: RelogioControlado, sim: Any) -> None:
    # A-1
    a, x, y = _x_pago_e_cancelado(relogio, sim)
    reembolso = _do_cancelamento(x)
    assert (reembolso.tipo, reembolso.autor, reembolso.chave) == (
        "integral",
        a.admin,
        f"cancelamento:{a.rodada.pk}:{a.a.pk}:{x.pk}",
    )
    assert (reembolso.produtos, reembolso.servico, reembolso.frete) == (
        D("80.00"),
        D("4.00"),
        D("10.35"),
    )
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo=MOTIVO)
    assert obrigacao.devido == D("94.35")
    assert sem_cobertura_da_obrigacao(obrigacao) == D("0.00")
    assert not Reembolso.objects.filter(pedido=y).exists()


def test_a_devolucao_nasce_autorizada_pelo_sistema(relogio: RelogioControlado, sim: Any) -> None:
    # A-2
    _a, x, _y = _x_pago_e_cancelado(relogio, sim)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo=MOTIVO)
    parcela = ParcelaDeDevolucao.objects.get(obrigacao=obrigacao)
    assert (parcela.situacao, parcela.valor, parcela.autorizada_por) == (
        "solicitada",
        D("94.35"),
        None,
    )
    assert parcela.pagamento == SituacaoDoPedido.objects.get(pedido=x).quitado_por
    assert ChamadaAoProvedor.objects.filter(
        operacao="estornar", alvo=f"parcela:{parcela.pk}"
    ).exists()
    assert EntradaAuditoria.objects.filter(acao="financeiro.devolucao_autorizada").exists()


def test_o_estorno_conclui_e_liquida_a_obrigacao(relogio: RelogioControlado, sim: Any) -> None:
    # A-3
    from django.db.models import Sum

    from apps.financeiro.livro import conta_da_obrigacao
    from apps.financeiro.models import ItemReembolsado
    from apps.financeiro.obrigacoes import _liquidado
    from apps.pedidos.models import ItemDoPedido

    _a, x, _y = _x_pago_e_cancelado(relogio, sim)
    processar_chamadas()
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo=MOTIVO)
    parcela = ParcelaDeDevolucao.objects.get(obrigacao=obrigacao)
    assert parcela.situacao == "concluida"
    assert obrigacao.devido - _liquidado(conta_da_obrigacao(obrigacao)) == D("0.00")
    itens = ItemDoPedido.objects.filter(pedido=x).aggregate(total=Sum("subtotal"))["total"]
    reembolsado = ItemReembolsado.objects.filter(reembolso=_do_cancelamento(x)).aggregate(
        total=Sum("valor")
    )["total"]
    assert reembolsado == itens


def test_consulta_que_falha_bloqueia_o_cancelamento_inteiro(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-4
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    etapa = Rodada.objects.get(pk=a.rodada.pk).etapa
    chamadas = ChamadaAoProvedor.objects.count()
    sim.falhar_proximas(1, operacao="buscar_por_referencia")
    with pytest.raises(ConsultaAoProvedorFalhou):
        _cancelar(a)
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == etapa
    assert SituacaoDoPedido.objects.get(pedido=y).situacao == "aguardando_pagamento"
    assert CancelamentoDaRodada.objects.count() == 0
    assert Reembolso.objects.filter(motivo=MOTIVO).count() == 0
    assert ObrigacaoComComprador.objects.filter(motivo=MOTIVO).count() == 0
    assert ChamadaAoProvedor.objects.count() == chamadas


def test_pagamento_descoberto_na_consulta_quita_e_entra_no_reembolso(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-5
    a, x, y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    id_y = cobranca(relogio, y)
    sim.aprovar(id_y, em=T0 + H + H // 2)
    relogio.congelar(T0 + 2 * H)
    _cancelar(a)
    assert SituacaoDoPedido.objects.get(pedido=y).situacao == "pago"
    assert _do_cancelamento(y).produtos + _do_cancelamento(y).servico + _do_cancelamento(
        y
    ).frete == D("106.15")
    assert Reembolso.objects.filter(motivo=MOTIVO).count() == 2


def test_o_reembolso_anterior_pendente_nao_e_substituido(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-6
    from apps.pedidos.apuracao import iniciar_apuracao

    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    de_caixa = ObrigacaoComComprador.objects.get(pedido=x, motivo="caixa_invalidada")
    assert de_caixa.devido == D("23.59")
    _cancelar(a)
    reembolso = _do_cancelamento(x)
    assert (reembolso.produtos, reembolso.servico, reembolso.frete) == (
        D("60.00"),
        D("3.00"),
        D("7.76"),
    )
    assert not ParcelaDeDevolucao.objects.filter(obrigacao=de_caixa).exists()
    total = sum(
        (r.produtos + r.servico + r.frete for r in Reembolso.objects.filter(pedido=x)), D("0.00")
    )
    assert total == D("94.35")


def test_integral_depois_de_parcial_completa_exatamente(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-7
    from apps.pagamentos.chamadas import processar_chamadas as _processar  # noqa: F401
    from apps.pedidos.cancelamento_da_rodada import cancelar_rodada
    from tests.apoio.devolucoes import K, itens_do_pedido, parcial
    from tests.apoio.financeiro import pedido_composto
    from tests.apoio.pedidos import administrador, sincronizar, tentativa_criada
    from tests.fabricas import ContaFactory

    relogio.congelar(T0 + H)
    pedido = pedido_composto(ContaFactory.create(), "7.99", "0.40", "1.60")
    id_externo = tentativa_criada(pedido).id_externo
    assert id_externo is not None
    sim.aprovar(id_externo)
    sincronizar(id_externo)
    (item,) = itens_do_pedido(pedido, K[3])
    assert parcial(item, "0.25").reembolso.produtos == D("2.00")
    relogio.congelar(T0 + 2 * H)
    cancelar_rodada(administrador(), pedido.abertura.rodada, com_reembolso=True)
    reembolso = _do_cancelamento(pedido)
    assert (reembolso.produtos, reembolso.servico, reembolso.frete) == (
        D("5.99"),
        D("0.30"),
        D("1.20"),
    )


def test_pedido_ja_devolvido_por_inteiro_nao_gera_reembolso_novo(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-8
    from apps.interesses.servicos import adicionar_interesse
    from apps.pedidos.apuracao import iniciar_apuracao
    from apps.rodadas.fechamento import iniciar_fechamento
    from tests.fabricas import ContaFactory

    a, x, _y = arranjo_ap(relogio, minimo="100.00", limites=(11, 12))
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    assert Reembolso.objects.filter(pedido=x, motivo="minimo_nao_atingido").count() == 1
    adicionar_interesse(ContaFactory.create(nome="Comprador C"), a.p1, "5")
    iniciar_fechamento(a.admin, a.rodada)
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "fechamento"
    _cancelar(a)
    assert Reembolso.objects.filter(motivo=MOTIVO).count() == 0
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.cancelar")
    assert auditoria.alteracoes["pagos_sem_reembolso"] == [x.pk]
    assert auditoria.alteracoes["reembolsos"] == []


def _aprovada(relogio: RelogioControlado, sim: Any, **arranjo: Any) -> tuple[Any, Pedido]:
    from apps.pedidos.apuracao import aprovar_resultado, iniciar_apuracao

    a, x, _y = arranjo_ap(relogio, **arranjo)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    aprovar_resultado(a.admin, a.rodada)
    return a, x


def test_depois_da_apuracao_a_obrigacao_e_financiada_pelas_fontes_da_rodada(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-9
    from apps.financeiro.livro import saldo
    from tests.apoio.financeiro import frete_de, obrigacao_de, receita_de

    a, x = _aprovada(relogio, sim)
    fontes = (
        obrigacao_de(a.rodada.fornecedor, a.rodada),
        receita_de(a.rodada),
        frete_de(a.rodada),
    )
    antes = [saldo(c) for c in fontes]
    _cancelar(a)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo=MOTIVO)
    assert obrigacao.depois_da_apuracao is True
    assert sem_cobertura_da_obrigacao(obrigacao) == D("0.00")
    reembolso = _do_cancelamento(x)
    depois = [saldo(c) for c in fontes]
    assert [a_ - d for a_, d in zip(antes, depois, strict=True)] == [
        reembolso.produtos,
        reembolso.servico,
        reembolso.frete,
    ]


def test_sem_cobertura_a_tarefa_espera_e_depois_autoriza(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-10
    from django.db import transaction

    from apps.financeiro.livro import saldo
    from apps.financeiro.reserva import designar_reserva, registrar_aporte
    from apps.pedidos.cancelamento_da_rodada import autorizar_devolucoes_do_cancelamento_agora
    from tests.apoio.financeiro import chave_nova, despesas, mover, receita_de

    a, x = _aprovada(relogio, sim)
    # a receita de serviço é consumida por despesas (cobertura de despesa) antes do cancelamento
    with transaction.atomic():
        mover(
            "cobertura_de_despesa",
            receita_de(a.rodada),
            despesas(),
            saldo(receita_de(a.rodada)),
            chave=chave_nova(),
        )
    id_deposito = sim.depositar(D("1000.00"))
    with transaction.atomic():
        registrar_aporte(a.admin, D("1000.00"), id_deposito, "Aporte")
    _cancelar(a)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo=MOTIVO)
    falta = sem_cobertura_da_obrigacao(obrigacao)
    assert falta > 0
    assert not ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).exists()
    with transaction.atomic():
        designar_reserva(a.admin, obrigacao, falta, "Cobrir a devolução do cancelamento")
    autorizar_devolucoes_do_cancelamento_agora()
    assert ParcelaDeDevolucao.objects.get(obrigacao=obrigacao).situacao == "solicitada"


def test_falha_na_autorizacao_nao_desfaz_o_cancelamento(
    relogio: RelogioControlado, sim: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-11
    from apps.pagamentos.consulta import consultar_antes_de_decidir as original
    from apps.pedidos.cancelamento_da_rodada import autorizar_devolucoes_do_cancelamento_agora

    falhas = [True]

    def consultar(referencia: str) -> Any:
        if falhas:
            falhas.pop()
            raise ConsultaAoProvedorFalhou(referencia, "indisponivel")
        return original(referencia)

    monkeypatch.setattr("apps.financeiro.devolucoes.consultar_antes_de_decidir", consultar)
    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    _cancelar(a)
    assert Rodada.objects.get(pk=a.rodada.pk).etapa == "cancelada"
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo=MOTIVO)
    assert not ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).exists()
    autorizar_devolucoes_do_cancelamento_agora()
    assert ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).count() == 1


def test_a_tarefa_repetida_nao_duplica(relogio: RelogioControlado, sim: Any) -> None:  # A-12
    from apps.pedidos.cancelamento_da_rodada import autorizar_devolucoes_do_cancelamento_agora

    _a, _x, _y = _x_pago_e_cancelado(relogio, sim)
    parcelas = ParcelaDeDevolucao.objects.count()
    chamadas = ChamadaAoProvedor.objects.count()
    autorizar_devolucoes_do_cancelamento_agora()
    autorizar_devolucoes_do_cancelamento_agora()
    assert ParcelaDeDevolucao.objects.count() == parcelas
    assert ChamadaAoProvedor.objects.count() == chamadas


def test_a_tarefa_so_autoriza_as_obrigacoes_do_cancelamento(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-13
    from apps.pedidos.apuracao import iniciar_apuracao
    from apps.pedidos.cancelamento_da_rodada import autorizar_devolucoes_do_cancelamento_agora

    a, x, _y = arranjo_ap(relogio)
    pagar(relogio, sim, x)
    relogio.congelar(PRAZO)
    iniciar_apuracao(a.admin, a.rodada)
    de_caixa = ObrigacaoComComprador.objects.get(pedido=x, motivo="caixa_invalidada")
    autorizar_devolucoes_do_cancelamento_agora()
    assert not ParcelaDeDevolucao.objects.filter(obrigacao=de_caixa).exists()


def test_sem_pagamento_nao_ha_reembolso(relogio: RelogioControlado, sim: Any) -> None:  # A-14
    a, x, y = arranjo_ap(relogio)
    _cancelar(a)
    assert Reembolso.objects.count() == 0
    assert ObrigacaoComComprador.objects.filter(motivo=MOTIVO).count() == 0
    assert ParcelaDeDevolucao.objects.count() == 0
    for pedido in (x, y):
        situacao = SituacaoDoPedido.objects.get(pedido=pedido)
        assert (situacao.situacao, situacao.motivo_do_cancelamento) == ("cancelado", MOTIVO)


def test_falha_definitiva_segue_para_a_devolucao_excepcional(
    relogio: RelogioControlado, sim: Any, settings: Any, tmp_path: Path
) -> None:  # A-15
    from apps.financeiro.devolucoes import DevolucaoRecusada, confirmar_devolucao_excepcional
    from apps.financeiro.livro import conta_da_obrigacao
    from apps.financeiro.obrigacoes import _liquidado

    settings.MEDIA_ROOT = tmp_path
    a, x, _y = arranjo_ap(relogio)
    id_x = pagar(relogio, sim, x)
    sim.recusar_estornos(id_x, "prazo_vencido")
    _cancelar(a)
    processar_chamadas()
    obrigacao = ObrigacaoComComprador.objects.get(pedido=x, motivo=MOTIVO)
    parcela = ParcelaDeDevolucao.objects.get(obrigacao=obrigacao)
    assert parcela.situacao == "elegivel_excepcional"

    def confirmar() -> Any:
        return confirmar_devolucao_excepcional(
            parcela,
            autor=a.admin,
            meio="pix",
            identificacao="E2E-1",
            justificativa="Pix direto",
            comprovante=SimpleUploadedFile("c.pdf", b"%PDF-1.4 x"),
        )

    confirmar()
    assert obrigacao.devido - _liquidado(conta_da_obrigacao(obrigacao)) == D("0.00")
    with pytest.raises(DevolucaoRecusada):
        confirmar()
    assert ParcelaDeDevolucao.objects.filter(obrigacao=obrigacao).count() == 1


def test_a_auditoria_traz_o_reembolso_com_a_chave_e_os_componentes(
    relogio: RelogioControlado, sim: Any
) -> None:  # A-16
    a, x, _y = _x_pago_e_cancelado(relogio, sim)
    (auditoria,) = EntradaAuditoria.objects.filter(acao="rodada.cancelar")
    assert auditoria.alteracoes["com_reembolso"] is True
    assert auditoria.alteracoes["reembolsos"] == [
        {
            "chave": f"cancelamento:{a.rodada.pk}:{a.a.pk}:{x.pk}",
            "pedido": x.pk,
            "comprador": a.a.pk,
            "produtos": "80.00",
            "servico": "4.00",
            "frete": "10.35",
        }
    ]


# --- concorrência (A-17 e A-18) -------------------------------------------------------------------


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_dois_cancelamentos_com_reembolso_gravam_um_por_pedido(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-17
    from apps.pedidos import cancelamento_da_rodada as modulo
    from apps.pedidos.cancelamento_da_rodada import CancelamentoRecusado
    from tests.apoio.corrida import Corrida

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    pagar(relogio, simulador_pagamentos, y)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "_reembolsar_os_pedidos_pagos")
    ra, rb = corrida.rodar(
        lambda: _cancelar(a), lambda: _cancelar(a), a_atomica=False, b_atomica=False
    )
    assert ra.excecao is None, ra.excecao
    assert isinstance(rb.excecao, CancelamentoRecusado), rb.excecao
    assert rb.excecao.codigo == "ja_cancelada"
    assert corrida.b_esperou
    for pedido in (x, y):
        reembolso = _do_cancelamento(pedido)
        assert reembolso.produtos + reembolso.servico + reembolso.frete == pedido.total
        assert ObrigacaoComComprador.objects.filter(pedido=pedido, motivo=MOTIVO).count() == 1
        assert ParcelaDeDevolucao.objects.filter(obrigacao__pedido=pedido).count() == 1


@pytest.mark.concorrencia
@COM_DOIS_BANCOS
def test_o_aviso_de_aprovacao_espera_a_situacao_que_o_cancelamento_travou(
    relogio: RelogioControlado, simulador_pagamentos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-18
    from apps.pedidos import cancelamento_da_rodada as modulo
    from tests.apoio.corrida import Corrida

    a, x, y = arranjo_ap(relogio)
    pagar(relogio, simulador_pagamentos, x)
    id_y = cobranca(relogio, y)
    relogio.congelar(T0 + 2 * H)

    def aprovar_e_receber() -> None:
        simulador_pagamentos.aprovar(id_y, em=T0 + 2 * H)
        simulador_pagamentos.entregar_avisos()
        processar_chamadas()

    corrida = Corrida()
    corrida.depois_de(monkeypatch, modulo, "_cancelar_os_pedidos_nao_pagos")
    ra, rb = corrida.rodar(
        lambda: _cancelar(a), aprovar_e_receber, a_atomica=False, b_atomica=False
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert corrida.b_esperou
    situacao = SituacaoDoPedido.objects.get(pedido=y)
    assert (situacao.situacao, situacao.motivo_do_cancelamento) == ("cancelado", MOTIVO)
    assert not Reembolso.objects.filter(pedido=y, motivo=MOTIVO).exists()
