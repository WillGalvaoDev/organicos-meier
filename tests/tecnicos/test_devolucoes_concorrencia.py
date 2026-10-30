"""E10-02: concorrência do cálculo do reembolso (acceptance A-15 e A-16).

As corridas pausam a operação A logo depois de ler o acumulado, e a operação B começa nesse
ponto: sem a trava do pedido, B lê o mesmo acumulado que A e as duas gravam em cima dele."""

from decimal import Decimal
from threading import Barrier
from typing import Any

import pytest
from django.db import transaction

from apps.financeiro import reembolsos as reembolsos_modulo
from apps.financeiro.models import ItemReembolsado, ObrigacaoComComprador, Reembolso
from apps.financeiro.reembolsos import (
    ReembolsoRecusado,
    acumulado_do_item,
    acumulado_do_pedido,
    reembolso_integral_do_pedido,
    reembolso_parcial,
)
from tests.apoio.concorrencia import executar_em_paralelo
from tests.apoio.corrida import Corrida
from tests.apoio.devolucoes import K, N, pedido_pago_com_itens
from tests.apoio.financeiro import chave_nova
from tests.apoio.pedidos import administrador
from tests.conftest import RelogioControlado

pytestmark = [pytest.mark.concorrencia, pytest.mark.django_db(transaction=True)]

D = Decimal
OC = "ocorrencia_de_entrega"


def test_dois_parciais_do_mesmo_item_nunca_passam_do_pago(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-15 (corrida determinística)
    _, (item,) = pedido_pago_com_itens(K)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, reembolsos_modulo, "acumulado_do_item")
    admin = administrador()

    def parcial(quantidade: str) -> Any:
        return lambda: reembolso_parcial(
            item, D(quantidade), chave=chave_nova(), motivo=OC, autor=admin
        )

    a, b = corrida.rodar(parcial("0.5"), parcial("0.75"))
    assert a.excecao is None, a.excecao
    assert isinstance(b.excecao, ReembolsoRecusado), b.excecao
    assert acumulado_do_item(item) == (D("0.500"), D("4.00"))  # 7,99 vezes 0,5, arredondado
    assert Reembolso.objects.count() == ItemReembolsado.objects.count() == 1
    assert ObrigacaoComComprador.objects.count() == 1


def test_tres_parciais_ao_mesmo_tempo_respeitam_o_pago(relogio: RelogioControlado) -> None:  # A-15
    pedido, (item,) = pedido_pago_com_itens(K)
    admin = administrador()

    def parcial(quantidade: str) -> Any:
        def executa(barreira: Barrier) -> Any:
            barreira.wait(timeout=10)
            with transaction.atomic():
                return reembolso_parcial(
                    item, D(quantidade), chave=chave_nova(), motivo=OC, autor=admin
                )

        return executa

    resultados = executar_em_paralelo(parcial("0.5"), parcial("0.5"), parcial("0.25"))
    excecoes = [r.excecao for r in resultados]
    assert all(e is None or isinstance(e, ReembolsoRecusado) for e in excecoes), excecoes
    quantidade, valor = acumulado_do_item(item)
    assert quantidade <= D("1.000")
    assert valor <= D("7.99")
    assert sum(e is None for e in excecoes) == Reembolso.objects.count()
    assert Reembolso.objects.count() == ItemReembolsado.objects.count()
    assert any(isinstance(e, ReembolsoRecusado) for e in excecoes)  # 1,25 não cabe em 1,000
    produtos, servico, frete = acumulado_do_pedido(pedido)
    assert produtos <= D("7.99")
    assert servico <= D("0.40")
    assert frete <= D("1.60")


def test_parcial_e_integral_ao_mesmo_tempo_fecham_exatamente(
    relogio: RelogioControlado, monkeypatch: pytest.MonkeyPatch
) -> None:  # A-16
    pedido, (_, i2) = pedido_pago_com_itens(N)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, reembolsos_modulo, "acumulado_do_pedido")
    admin = administrador()

    def parcial() -> Any:
        return reembolso_parcial(i2, D("1"), chave=chave_nova(), motivo=OC, autor=admin)

    def integral() -> Any:
        return reembolso_integral_do_pedido(
            pedido, chave=chave_nova(), motivo="cancelamento_da_rodada", autor=admin
        )

    a, b = corrida.rodar(parcial, integral)
    assert a.excecao is None, a.excecao
    assert b.excecao is None, b.excecao
    assert acumulado_do_pedido(pedido) == (D("100.00"), D("5.00"), D("20.00"))
    obrigacoes = ObrigacaoComComprador.objects.all()
    assert len(obrigacoes) == 2
    assert sum((o.devido for o in obrigacoes), D("0.00")) == D("125.00")


# --- E10-04: autorização e acompanhamento em paralelo (A-23 e A-24) -------------------------


def test_duas_autorizacoes_da_mesma_obrigacao_geram_uma_parcela(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # E10-04, A-23
    from apps.financeiro.devolucoes import autorizar_devolucao
    from apps.financeiro.models import ParcelaDeDevolucao
    from apps.pagamentos.models import ChamadaAoProvedor
    from tests.apoio.devolucoes import arranjo_da_devolucao

    a = arranjo_da_devolucao(simulador_pagamentos, relogio)

    def autorizar(barreira: Barrier) -> Any:
        barreira.wait(timeout=10)
        return autorizar_devolucao(a.o1, autor=a.admin)

    resultados = executar_em_paralelo(autorizar, autorizar)
    assert [r.excecao for r in resultados] == [None, None]
    assert resultados[0].valor.pk == resultados[1].valor.pk
    assert ParcelaDeDevolucao.objects.count() == 1
    assert ChamadaAoProvedor.objects.filter(operacao="estornar").count() == 1


def test_acompanhar_e_verificar_ao_mesmo_tempo_liquidam_uma_vez(
    relogio: RelogioControlado, simulador_pagamentos: Any
) -> None:  # E10-04, A-24
    from apps.financeiro.devolucoes import autorizar_devolucao
    from apps.financeiro.models import MovimentoFinanceiro
    from apps.pagamentos.chamadas import processar_chamadas
    from apps.pagamentos.models import ChamadaAoProvedor
    from apps.simulador_pagamentos.models import EstornoSimulado
    from tests.apoio.devolucoes import arranjo_da_devolucao

    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    simulador_pagamentos.estornos_em_processamento(a.pagamento.id_externo)
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas(limite=1)
    parcela.refresh_from_db()
    assert parcela.situacao == "em_processamento"
    simulador_pagamentos.concluir_estorno(EstornoSimulado.objects.get().id_estorno)
    with transaction.atomic():
        ChamadaAoProvedor.objects.create(
            operacao="verificar_estornos",
            alvo=f"parcela:{parcela.pk}",
            chave_idempotencia="verificacao-a-mao",
            provedor="simulador",
            ambiente="testes",
        )

    def processar(barreira: Barrier) -> int:
        barreira.wait(timeout=10)
        return processar_chamadas()

    resultados = executar_em_paralelo(processar, processar)
    assert [r.excecao for r in resultados] == [None, None]
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert MovimentoFinanceiro.objects.filter(tipo="devolucao").count() == 1


def test_duas_confirmacoes_excepcionais_da_mesma_parcela(
    relogio: RelogioControlado, simulador_pagamentos: Any, settings: Any, tmp_path: Any
) -> None:  # E10-06, A-16
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.financeiro.devolucoes import DevolucaoRecusada, confirmar_devolucao_excepcional
    from apps.financeiro.models import ConfirmacaoDeDevolucaoExcepcional, MovimentoFinanceiro
    from tests.apoio.devolucoes import arranjo_da_devolucao, levar_a_elegivel

    settings.MEDIA_ROOT = tmp_path
    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    parcela = levar_a_elegivel(a)

    def confirmar(barreira: Barrier) -> Any:
        barreira.wait(timeout=10)
        return confirmar_devolucao_excepcional(
            parcela,
            autor=a.admin,
            meio="pix",
            identificacao="E2E-123",
            justificativa="Pix direto ao comprador",
            comprovante=SimpleUploadedFile("c.pdf", b"%PDF-1.4 conteudo"),
        )

    resultados = executar_em_paralelo(confirmar, confirmar)
    excecoes = [r.excecao for r in resultados]
    assert sum(e is None for e in excecoes) == 1, excecoes
    (recusa,) = [e for e in excecoes if e is not None]
    assert isinstance(recusa, DevolucaoRecusada)
    assert "já confirmada" in str(recusa)
    assert ConfirmacaoDeDevolucaoExcepcional.objects.count() == 1
    assert MovimentoFinanceiro.objects.filter(tipo="devolucao_excepcional").count() == 1
    assert len([p for p in (tmp_path / "comprovantes").glob("*") if p.is_file()]) == 1


# --- E10-R04: nova tentativa manual contra a tarefa (A-29 e A-30) -------------------------------


def _parcela_em_falha_temporaria(relogio: RelogioControlado, simulador_pagamentos: Any) -> Any:
    from datetime import timedelta

    from apps.financeiro.devolucoes import autorizar_devolucao
    from apps.pagamentos.chamadas import processar_chamadas
    from tests.apoio.devolucoes import arranjo_da_devolucao

    a = arranjo_da_devolucao(simulador_pagamentos, relogio)
    simulador_pagamentos.falhar_proximas(1, operacao="estornar")
    parcela = autorizar_devolucao(a.o1, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "falha_temporaria"
    relogio.avancar(timedelta(minutes=2))
    return a, parcela


def _estorno_concluido_uma_vez(parcela: Any) -> None:
    from apps.financeiro.models import MovimentoFinanceiro
    from apps.pagamentos.models import ChamadaAoProvedor
    from apps.simulador_pagamentos.models import EstornoSimulado

    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    (estorno,) = EstornoSimulado.objects.all()
    (movimento,) = MovimentoFinanceiro.objects.filter(tipo="devolucao")
    assert movimento.chave == f"devolucao:{estorno.id_estorno}"
    chamada = ChamadaAoProvedor.objects.get(operacao="estornar")
    assert chamada.chave_idempotencia == parcela.chave_idempotencia


def test_tarefa_antes_da_cadeia_contra_nova_tentativa_manual(
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:  # E10-04, A-29
    from apps.financeiro import devolucoes
    from apps.pagamentos.chamadas import processar_chamadas

    a, parcela = _parcela_em_falha_temporaria(relogio, simulador_pagamentos)
    corrida = Corrida()
    corrida.antes_de(monkeypatch, devolucoes, "_travar_cadeia")
    ra, rb = corrida.rodar(
        lambda: processar_chamadas(limite=1),
        lambda: devolucoes.tentar_devolucao_de_novo(parcela, autor=a.admin),
        b_atomica=False,  # a rota não abre transação externa: a consulta ao provedor não a segura
    )
    assert ra.excecao is None, ra.excecao
    assert isinstance(rb.excecao, devolucoes.DevolucaoRecusada), rb.excecao
    assert "OperationalError" not in caplog.text
    _estorno_concluido_uma_vez(parcela)


def test_nova_tentativa_manual_depois_da_cadeia_contra_a_tarefa(
    relogio: RelogioControlado,
    simulador_pagamentos: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:  # E10-04, A-30
    from apps.financeiro import devolucoes
    from apps.pagamentos.chamadas import processar_chamadas

    a, parcela = _parcela_em_falha_temporaria(relogio, simulador_pagamentos)
    corrida = Corrida()
    corrida.depois_de(monkeypatch, devolucoes, "_travar_cadeia")
    ra, rb = corrida.rodar(
        lambda: devolucoes.tentar_devolucao_de_novo(parcela, autor=a.admin),
        lambda: processar_chamadas(limite=1),
    )
    assert ra.excecao is None, ra.excecao
    assert rb.excecao is None, rb.excecao
    assert "OperationalError" not in caplog.text
    processar_chamadas()
    _estorno_concluido_uma_vez(parcela)
