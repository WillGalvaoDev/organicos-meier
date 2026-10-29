"""E10-04: devolução pela plataforma (acceptance A-1 a A-22 e A-25)."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.financeiro.devolucoes import (
    DevolucaoRecusada,
    autorizar_devolucao,
    situacao_da_devolucao,
    tentar_devolucao_de_novo,
    transicionar,
)
from apps.financeiro.livro import conta_da_obrigacao, saldo
from apps.financeiro.models import (
    AlertaFinanceiro,
    DesignacaoDesfeita,
    HistoricoDaDevolucao,
    MovimentoFinanceiro,
    ObrigacaoComComprador,
    ParcelaDeDevolucao,
)
from apps.financeiro.obrigacoes import _liquidado
from apps.financeiro.reserva import (
    desfazer_designacao,
    designar_reserva,
    sem_cobertura_da_obrigacao,
)
from apps.nucleo.auditoria import SISTEMA
from apps.nucleo.models import EntradaAuditoria
from apps.nucleo.tempo import agora
from apps.pagamentos.chamadas import processar_chamadas
from apps.pagamentos.consulta import ConsultaAoProvedorFalhou
from apps.pagamentos.models import ChamadaAoProvedor
from apps.pagamentos.provedor import NovaCobranca, NovoEstorno, obter_provedor
from apps.pedidos.models import DestinoDoPagamento
from apps.simulador_pagamentos.models import EstornoSimulado
from tests.apoio.devolucoes import (
    Arranjo,
    arranjo_da_devolucao,
    parcial,
)
from tests.apoio.financeiro import chave_nova, custodia, mover, obrigacao_com
from tests.apoio.pedidos import T0, sincronizar
from tests.conftest import RelogioControlado
from tests.fabricas import ContaFactory

pytestmark = pytest.mark.django_db

D = Decimal
H = timedelta(hours=1)


@pytest.fixture
def a(relogio: RelogioControlado, simulador_pagamentos: Any) -> Arranjo:
    return arranjo_da_devolucao(simulador_pagamentos, relogio)


def _estornos_do_simulador() -> list[EstornoSimulado]:
    return list(EstornoSimulado.objects.order_by("pk"))


def _f15() -> list[MovimentoFinanceiro]:
    return list(MovimentoFinanceiro.objects.filter(tipo="devolucao").order_by("pk"))


def _alertas(tipo: str) -> list[AlertaFinanceiro]:
    return list(AlertaFinanceiro.objects.filter(tipo=tipo, resolvido_em=None))


def _parcela(a: Arranjo) -> ParcelaDeDevolucao:
    parcela: ParcelaDeDevolucao = ParcelaDeDevolucao.objects.get(obrigacao=a.o1)
    return parcela


def _autorizar(a: Arranjo) -> ParcelaDeDevolucao:
    return autorizar_devolucao(a.o1, autor=a.admin)


def _passar(a: Arranjo, minutos: int = 61) -> int:
    a.relogio.avancar(timedelta(minutes=minutos))
    return processar_chamadas()


def _nada_gravado() -> tuple[int, int, int]:
    return (
        ParcelaDeDevolucao.objects.count(),
        ChamadaAoProvedor.objects.filter(operacao="estornar").count(),
        HistoricoDaDevolucao.objects.count(),
    )


def test_autorizar_e_executar_devolve_e_liquida(a: Arranjo) -> None:  # A-1
    parcela = _autorizar(a)
    assert (parcela.situacao, parcela.valor, parcela.pagamento_id) == (
        "solicitada",
        D("31.25"),
        a.pagamento.pk,
    )
    assert parcela.chave_idempotencia
    (chamada,) = ChamadaAoProvedor.objects.filter(operacao="estornar", situacao="pendente")
    assert chamada.chave_idempotencia == parcela.chave_idempotencia
    assert chamada.alvo == f"parcela:{parcela.pk}"
    assert _estornos_do_simulador() == []
    processar_chamadas()
    parcela.refresh_from_db()
    (estorno,) = _estornos_do_simulador()
    assert estorno.valor == D("31.25")
    assert estorno.cobranca.id_externo == a.pagamento.id_externo
    assert (parcela.situacao, parcela.id_estorno) == ("concluida", estorno.id_estorno)
    (movimento,) = _f15()
    assert movimento.chave == f"devolucao:{estorno.id_estorno}"
    assert a.o1.devido - _liquidado(conta_da_obrigacao(a.o1)) == D("0.00")
    situacoes = list(parcela.historico.order_by("pk").values_list("situacao", flat=True))
    assert situacoes == ["solicitada", "concluida"]
    assert situacao_da_devolucao(a.o1) == "concluida"


def test_situacao_da_devolucao_sem_parcela_e_devida(a: Arranjo) -> None:
    assert situacao_da_devolucao(a.o1) == "devida"


def _duplicidade(a: Arranjo) -> Any:
    nova = NovaCobranca("k-dup", a.pedido.referencia_externa, a.pedido.total, "Dup", T0 + 24 * H)
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    a.sim.aprovar(id_externo)
    sincronizar(id_externo)
    destino = DestinoDoPagamento.objects.get(pagamento__id_externo=id_externo)
    assert destino.motivo == "duplicidade"
    return destino


def test_duplicidade_estorna_o_segundo_pagamento(a: Arranjo) -> None:  # A-2
    destino = _duplicidade(a)
    obrigacao = ObrigacaoComComprador.objects.get(
        origem_tipo="pedidos.destinodopagamento", origem_id=str(destino.pk)
    )
    assert _alertas("duplicidade")
    parcela = autorizar_devolucao(obrigacao, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert parcela.pagamento_id == destino.pagamento_id
    (estorno,) = _estornos_do_simulador()
    assert (estorno.valor, estorno.cobranca.id_externo) == (
        D("125.00"),
        destino.pagamento.id_externo,
    )
    assert _alertas("duplicidade") == []


def test_pagamento_sem_pedido_e_estornado(a: Arranjo) -> None:  # A-3
    nova = NovaCobranca("k-sp", "ref-desconhecida", D("40.00"), "Sem pedido", T0 + 24 * H)
    id_externo = obter_provedor().criar_cobranca(nova).pagamento.id_externo
    a.sim.aprovar(id_externo)
    sincronizar(id_externo)
    obrigacao = ObrigacaoComComprador.objects.get(pedido=None, integral=D("40.00"))
    parcela = autorizar_devolucao(obrigacao, autor=a.admin)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert [e.valor for e in _estornos_do_simulador()] == [D("40.00")]


def test_provedor_fora_do_ar_bloqueia_a_autorizacao(a: Arranjo) -> None:  # A-4
    a.sim.indisponivel()
    antes = _nada_gravado()
    with pytest.raises(ConsultaAoProvedorFalhou):
        _autorizar(a)
    assert _nada_gravado() == antes
    assert ParcelaDeDevolucao.objects.count() == 0


def test_so_o_administrador_autoriza(a: Arranjo) -> None:  # A-5
    fornecedor = ContaFactory.create(fornecedor=True)
    for autor in (a.comprador, fornecedor):
        with pytest.raises(PermissionDenied):
            autorizar_devolucao(a.o1, autor=autor)
    assert ParcelaDeDevolucao.objects.count() == 0


def test_autorizar_de_novo_devolve_a_mesma_parcela(a: Arranjo) -> None:  # A-6
    primeira = _autorizar(a)
    segunda = _autorizar(a)
    assert segunda.pk == primeira.pk
    assert ChamadaAoProvedor.objects.filter(operacao="estornar").count() == 1
    assert HistoricoDaDevolucao.objects.count() == 1


def _obrigacao_sem_cobertura(a: Arranjo) -> ObrigacaoComComprador:
    """A custódia do pedido é esvaziada antes do reembolso: a obrigação nasce sem cobertura."""
    rodada, ciclo = a.pedido.abertura.rodada, a.pedido.abertura.ciclo
    ralo = obrigacao_com(rodada, ciclo, a.comprador, numero=9999)
    for componente in ("produtos", "servico", "frete"):
        conta = custodia(rodada, ciclo, a.comprador, componente)
        mover("financiamento_de_obrigacao", conta, ralo, saldo(conta), chave=chave_nova())
    obrigacao: ObrigacaoComComprador = parcial(a.i1, "1").obrigacao
    assert sem_cobertura_da_obrigacao(obrigacao) == obrigacao.devido
    return obrigacao


def test_obrigacao_sem_cobertura_nao_e_autorizada(a: Arranjo) -> None:  # A-7
    obrigacao = _obrigacao_sem_cobertura(a)
    antes = _nada_gravado()
    with transaction.atomic():
        designar_reserva(a.admin, obrigacao, D("1.00"), "cobertura parcial")
    with pytest.raises(DevolucaoRecusada, match="cobrir"):
        autorizar_devolucao(obrigacao, autor=a.admin)
    assert _nada_gravado() == antes
    with transaction.atomic():
        designar_reserva(a.admin, obrigacao, obrigacao.devido - D("1.00"), "cobertura")
    assert autorizar_devolucao(obrigacao, autor=a.admin).situacao == "solicitada"


def test_soma_das_parcelas_nao_passa_do_pagamento(a: Arranjo) -> None:  # A-8
    from tests.apoio.financeiro import obrigacao_de_teste

    ParcelaDeDevolucao.objects.create(
        obrigacao=obrigacao_de_teste("125.00"),
        pagamento=a.pagamento,
        valor=D("125.00"),
        situacao="concluida",
        chave_idempotencia="fabrica-125",
    )
    with pytest.raises(DevolucaoRecusada, match="passaria"):
        _autorizar(a)
    assert not ChamadaAoProvedor.objects.filter(operacao="estornar").exists()


def test_falha_depois_de_executar_repete_a_mesma_chave(a: Arranjo) -> None:  # A-9
    a.sim.falhar_proximas(2, operacao="estornar", depois_de_executar=True)
    parcela = _autorizar(a)
    chave = parcela.chave_idempotencia
    processar_chamadas()
    parcela.refresh_from_db()
    chamada = ChamadaAoProvedor.objects.get(operacao="estornar")
    assert (parcela.situacao, parcela.codigo_da_falha, chamada.tentativas) == (
        "falha_temporaria",
        "indisponivel",
        1,
    )
    _passar(a)
    parcela.refresh_from_db()
    chamada.refresh_from_db()
    assert (parcela.situacao, chamada.tentativas) == ("falha_temporaria", 2)
    _passar(a)
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert len(_estornos_do_simulador()) == 1
    assert len(_f15()) == 1
    assert ChamadaAoProvedor.objects.get(operacao="estornar").chave_idempotencia == chave


def test_tres_falhas_abrem_o_alerta_e_a_quarta_conclui(a: Arranjo) -> None:  # A-10
    a.sim.falhar_proximas(3, operacao="estornar")
    parcela = _autorizar(a)
    processar_chamadas()
    _passar(a)
    assert _alertas("devolucao_com_falha") == []
    _passar(a)
    parcela.refresh_from_db()
    assert (parcela.situacao, ChamadaAoProvedor.objects.get(operacao="estornar").tentativas) == (
        "falha_temporaria",
        3,
    )
    (alerta,) = _alertas("devolucao_com_falha")
    assert alerta.chave == f"parcela:{parcela.pk}"
    _passar(a)
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert _alertas("devolucao_com_falha") == []


def test_saldo_insuficiente_avisa_logo_e_conclui_depois_do_aporte(a: Arranjo) -> None:  # A-11
    a.sim.registrar_saida(D("1100.00"), descricao="retirada")
    parcela = _autorizar(a)
    processar_chamadas()
    parcela.refresh_from_db()
    assert (parcela.situacao, parcela.codigo_da_falha) == ("falha_temporaria", "saldo_insuficiente")
    assert len(_alertas("devolucao_com_falha")) == 1
    a.sim.depositar(D("100.00"))
    _passar(a)
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert _alertas("devolucao_com_falha") == []


def _levar_a_falha_definitiva(a: Arranjo) -> ParcelaDeDevolucao:
    a.sim.recusar_estornos(a.pagamento.id_externo, "prazo_vencido")
    parcela = _autorizar(a)
    processar_chamadas(limite=1)
    parcela.refresh_from_db()
    return parcela


def test_recusa_definitiva_reconsulta_e_fica_elegivel(a: Arranjo) -> None:  # A-12
    parcela = _levar_a_falha_definitiva(a)
    assert (parcela.situacao, parcela.codigo_da_falha) == ("falha_definitiva", "prazo_vencido")
    assert parcela.evidencia["recusa"]["codigo"] == "prazo_vencido"
    assert len(_alertas("devolucao_em_falha_definitiva")) == 1
    assert ChamadaAoProvedor.objects.filter(
        operacao="verificar_estornos", alvo=f"parcela:{parcela.pk}", situacao="pendente"
    ).exists()
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"
    assert parcela.evidencia["reconsulta"]["estornos"] == []
    assert len(_alertas("devolucao_elegivel_excepcional")) == 1
    assert _alertas("devolucao_em_falha_definitiva") == []
    assert _f15() == []


def test_estorno_concluido_pelo_provedor_apos_a_recusa_e_adotado(a: Arranjo) -> None:  # A-13
    a.sim.recusar_mas_processar(a.pagamento.id_externo, "meio_nao_permite_estorno")
    parcela = _autorizar(a)
    processar_chamadas(limite=1)
    parcela.refresh_from_db()
    assert parcela.situacao == "falha_definitiva"
    (invisivel,) = _estornos_do_simulador()
    a.sim.concluir_estorno(invisivel.id_estorno)
    processar_chamadas()
    parcela.refresh_from_db()
    assert (parcela.situacao, parcela.id_estorno) == ("concluida", invisivel.id_estorno)
    assert [m.chave for m in _f15()] == [f"devolucao:{invisivel.id_estorno}"]
    assert not parcela.historico.filter(situacao="elegivel_excepcional").exists()


def test_estorno_invisivel_ainda_em_processamento_nao_e_visto(a: Arranjo) -> None:  # A-14
    a.sim.recusar_mas_processar(a.pagamento.id_externo, "meio_nao_permite_estorno")
    parcela = _autorizar(a)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"  # o risco residual que a E10-05 detecta


def test_estorno_nao_contabilizado_de_outro_valor_deixa_inconclusivo(a: Arranjo) -> None:  # A-15
    obter_provedor().estornar(NovoEstorno(a.pagamento.id_externo, D("10.00"), "avulso"))
    parcela = _levar_a_falha_definitiva(a)
    processar_chamadas()
    parcela.refresh_from_db()
    assert (parcela.situacao, parcela.codigo_da_falha) == (
        "falha_definitiva",
        "verificacao_inconclusiva",
    )
    assert len(_alertas("devolucao_em_falha_definitiva")) == 1
    assert _alertas("devolucao_elegivel_excepcional") == []


def test_estorno_em_processamento_e_acompanhado_ate_concluir(a: Arranjo) -> None:  # A-16
    a.sim.estornos_em_processamento(a.pagamento.id_externo)
    parcela = _autorizar(a)
    processar_chamadas(limite=1)
    parcela.refresh_from_db()
    (estorno,) = _estornos_do_simulador()
    assert (parcela.situacao, parcela.id_estorno) == ("em_processamento", estorno.id_estorno)
    assert ChamadaAoProvedor.objects.filter(
        operacao="acompanhar_estorno", alvo=f"parcela:{parcela.pk}", situacao="pendente"
    ).exists()
    _passar(a)
    parcela.refresh_from_db()
    assert parcela.situacao == "em_processamento"
    a.sim.concluir_estorno(estorno.id_estorno)
    _passar(a)
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"
    assert [m.chave for m in _f15()] == [f"devolucao:{estorno.id_estorno}"]


def test_estorno_recusado_depois_leva_a_falha_definitiva_e_elegivel(a: Arranjo) -> None:  # A-17
    a.sim.estornos_em_processamento(a.pagamento.id_externo)
    parcela = _autorizar(a)
    processar_chamadas(limite=1)
    (estorno,) = _estornos_do_simulador()
    a.sim.recusar_estorno(estorno.id_estorno, "estado_invalido")
    _passar(a)
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"
    assert parcela.historico.filter(situacao="falha_definitiva").exists()


def test_nova_tentativa_antecipa_a_chamada_com_a_mesma_chave(a: Arranjo) -> None:  # A-18
    a.sim.falhar_proximas(3, operacao="estornar")
    parcela = _autorizar(a)
    processar_chamadas()
    _passar(a)
    _passar(a)
    parcela.refresh_from_db()
    assert parcela.situacao == "falha_temporaria"
    chamada = ChamadaAoProvedor.objects.get(operacao="estornar")
    chave = chamada.chave_idempotencia
    assert chamada.proxima_em > agora()
    tentar_devolucao_de_novo(parcela, autor=a.admin)
    chamada.refresh_from_db()
    assert chamada.chave_idempotencia == chave
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"


def test_nova_tentativa_so_em_falha_temporaria(a: Arranjo) -> None:  # A-19
    solicitada = _autorizar(a)
    with pytest.raises(DevolucaoRecusada):
        tentar_devolucao_de_novo(solicitada, autor=a.admin)
    processar_chamadas()
    solicitada.refresh_from_db()
    with pytest.raises(DevolucaoRecusada):
        tentar_devolucao_de_novo(solicitada, autor=a.admin)  # concluída
    assert solicitada.situacao == "concluida"
    with pytest.raises(PermissionDenied):
        tentar_devolucao_de_novo(solicitada, autor=a.comprador)


def test_nova_tentativa_recusada_na_elegivel(a: Arranjo) -> None:  # A-19
    parcela = _levar_a_falha_definitiva(a)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"
    with pytest.raises(DevolucaoRecusada):
        tentar_devolucao_de_novo(parcela, autor=a.admin)
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"


def test_chamada_pendente_de_parcela_encerrada_nao_chama_o_provedor(a: Arranjo) -> None:  # A-20
    parcela = _levar_a_falha_definitiva(a)
    processar_chamadas()
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"
    ChamadaAoProvedor.objects.create(
        operacao="estornar",
        alvo=f"parcela:{parcela.pk}",
        chave_idempotencia="fabrica-pendente",
        provedor="simulador",
        ambiente="testes",
    )
    a.sim.normalizar()
    processar_chamadas()
    chamada = ChamadaAoProvedor.objects.get(chave_idempotencia="fabrica-pendente")
    assert (chamada.situacao, chamada.ultimo_erro) == ("falhou", "parcela_encerrada")
    assert _estornos_do_simulador() == []
    parcela.refresh_from_db()
    assert parcela.situacao == "elegivel_excepcional"


def test_designacao_da_obrigacao_com_parcela_aberta_nao_se_desfaz(a: Arranjo) -> None:  # A-21
    obrigacao = _obrigacao_sem_cobertura(a)
    with transaction.atomic():
        designacao = designar_reserva(a.admin, obrigacao, obrigacao.devido, "cobertura")
    autorizar_devolucao(obrigacao, autor=a.admin)
    with pytest.raises(DevolucaoRecusada), transaction.atomic():
        desfazer_designacao(a.admin, designacao, "desistência")
    assert not DesignacaoDesfeita.objects.filter(designacao=designacao).exists()


def test_parcela_concluida_nao_volta_atras(a: Arranjo) -> None:  # A-22
    parcela = _autorizar(a)
    processar_chamadas()
    parcela.refresh_from_db()
    with pytest.raises(DevolucaoRecusada):
        transicionar(parcela, "falha_temporaria", autor=SISTEMA)
    parcela.refresh_from_db()
    assert parcela.situacao == "concluida"


def test_auditoria_e_historico_da_devolucao(a: Arranjo) -> None:  # A-25
    parcela = _autorizar(a)
    processar_chamadas()
    entrada = EntradaAuditoria.objects.get(acao="financeiro.devolucao_autorizada")
    assert entrada.autor_id == str(a.admin.pk)
    assert entrada.objeto_tipo == "financeiro.parceladedevolucao"
    assert entrada.objeto_id == str(parcela.pk)
    assert entrada.alteracoes["obrigacao"] == a.o1.pk
    linhas = list(parcela.historico.order_by("pk"))
    assert [linha.situacao for linha in linhas] == ["solicitada", "concluida"]
    assert all(linha.momento is not None and linha.dados is not None for linha in linhas)
    assert saldo(conta_da_obrigacao(a.o1)) == D("0.00")
